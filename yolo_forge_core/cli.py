"""yolo-forge 命令行入口.

子命令
------
- ``yolo-forge review``     启动标签审查 GUI (OpenCV)
- ``yolo-forge convert``    按 profile 转换数据集
- ``yolo-forge inspect``    确定性扫描数据集结构 (无 LLM)
- ``yolo-forge train``      用 Ultralytics 训练
- ``yolo-forge templates``  列出/导出内置 profile 模板
- ``yolo-forge info``       打印包信息和环境

启动桌面应用: ``yolo-forge-desktop``
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .converter.builtins import get_builtin_template, list_builtin_templates
from .converter.engine import convert_dataset
from .converter.profiles import DatasetProfile
from .reviewer.app import run_reviewer
from .reviewer.config import ReviewerConfig
from .utils import log


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yolo-forge",
        description="yolo-forge CLI — review / convert / inspect / train YOLO datasets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-V", "--version", action="version", version=f"yolo-forge {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    # ── review ──
    p_review = sub.add_parser("review", help="Start the OpenCV label review & patch GUI")
    p_review.add_argument("--images", required=True, help="Image directory")
    p_review.add_argument("--labels", required=True, help="Label directory (YOLO .txt)")
    p_review.add_argument("--output", default="./yolo_forge_output")
    p_review.add_argument("--classes", default="object", help="Comma-separated class names")
    p_review.add_argument("--max-w", type=int, default=1280)
    p_review.add_argument("--max-h", type=int, default=900)

    # ── convert ──
    p_conv = sub.add_parser("convert", help="Convert a dataset to YOLO format using a profile")
    p_conv.add_argument("--profile", required=True, help="Path to a YAML profile file")
    p_conv.add_argument("--dry-run", action="store_true")
    p_conv.add_argument("--output", default=None, help="Override output_dir in profile")

    # ── inspect ──
    p_insp = sub.add_parser("inspect", help="Deterministic dataset structure scanner (no LLM)")
    p_insp.add_argument("path", help="Dataset root path to inspect")
    p_insp.add_argument("--markdown", action="store_true", help="Output markdown report instead of plain text")
    p_insp.add_argument("--sample-size", type=int, default=5, help="How many label files to sample per folder")

    # ── train ──
    p_train = sub.add_parser("train", help="Train a YOLO model using Ultralytics")
    p_train.add_argument("--data", required=True, help="Path to data.yaml")
    p_train.add_argument("--model", default="yolo11n.pt", help="Pretrained weights (default: yolo11n.pt)")
    p_train.add_argument("--epochs", type=int, default=100)
    p_train.add_argument("--imgsz", type=int, default=640)
    p_train.add_argument("--batch", type=int, default=16)
    p_train.add_argument("--device", default="", help='e.g. "0" for GPU0, "cpu" for CPU, empty=auto')
    p_train.add_argument("--workers", type=int, default=4)
    p_train.add_argument("--project", default="./runs")
    p_train.add_argument("--name", default="exp")
    p_train.add_argument("--patience", type=int, default=50)

    # ── templates ──
    p_tpl = sub.add_parser("templates", help="List or export builtin profile templates")
    p_tpl.add_argument("--list", action="store_true")
    p_tpl.add_argument("--export", metavar="NAME")
    p_tpl.add_argument("-o", "--output", default=None)

    # ── info ──
    p_info = sub.add_parser("info", help="Print package and environment info")

    return parser


# ─────────────────────────────────────────────────────────────
def _cmd_review(args: argparse.Namespace) -> int:
    classes = [c.strip() for c in args.classes.split(",") if c.strip()]
    cfg = ReviewerConfig(
        image_dir=args.images,
        label_dir=args.labels,
        output_dir=args.output,
        classes=classes,
        max_w=args.max_w,
        max_h=args.max_h,
    )
    try:
        run_reviewer(cfg)
        return 0
    except KeyboardInterrupt:
        log.warn("Interrupted")
        return 130
    except Exception as e:
        log.err(f"Reviewer crashed: {e}")
        return 1


def _cmd_convert(args: argparse.Namespace) -> int:
    try:
        profile = DatasetProfile.from_yaml(args.profile)
        if args.output:
            profile.output_dir = args.output
        convert_dataset(profile, dry_run=args.dry_run)
        return 0
    except (FileNotFoundError, ValueError) as e:
        log.err(str(e))
        return 2
    except Exception as e:
        log.err(f"Conversion failed: {e}")
        return 1


def _cmd_inspect(args: argparse.Namespace) -> int:
    from .inspector import inspect_dataset
    try:
        report = inspect_dataset(args.path, sample_size=args.sample_size)
        if args.markdown:
            print(report.to_markdown())
        else:
            log.hl(f"═══ Inspection: {args.path} ═══")
            log.info(f"Total images: {report.total_images}")
            log.info(f"Total labels: {report.total_labels}")
            log.info(f"Folders:      {len(report.folders)}")
            log.info(f"Suggested classes: {report.suggested_class_count}")
            print()
            for f in report.folders:
                log.info("  " + f.summary_line())
        return 0
    except Exception as e:
        log.err(f"Inspect failed: {e}")
        return 1


def _cmd_train(args: argparse.Namespace) -> int:
    from .trainer import TrainConfig, Trainer, TrainCallbacks

    cfg = TrainConfig(
        data_yaml=args.data,
        model=args.model,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        project=args.project,
        name=args.name,
        patience=args.patience,
    )

    # CLI 模式: 同步等训练结束
    import threading
    done = threading.Event()
    result = {"best_pt": "", "error": ""}

    def _on_complete(p):
        result["best_pt"] = p
        done.set()

    def _on_error(e):
        result["error"] = e
        done.set()

    cbs = TrainCallbacks(
        on_log=lambda s: print(s, flush=True),
        on_progress=lambda p, s: None,  # CLI 不显示进度条
        on_metrics=lambda m: None,
        on_complete=_on_complete,
        on_error=_on_error,
    )

    trainer = Trainer(cfg, cbs)
    trainer.start()
    done.wait()

    if result["error"]:
        log.err(result["error"])
        return 1
    log.ok(f"训练完成. best.pt: {result['best_pt']}")
    return 0


def _cmd_templates(args: argparse.Namespace) -> int:
    if args.list or not args.export:
        log.hl("Available builtin templates:")
        for name in list_builtin_templates():
            log.info(f"  - {name}")
        print("\nUse --export <name> -o <file> to save one to disk.")
        return 0

    try:
        yaml_text = get_builtin_template(args.export)
    except KeyError as e:
        log.err(str(e))
        return 2

    out = args.output or f"{args.export}.yaml"
    with open(out, "w", encoding="utf-8") as f:
        f.write(yaml_text)
    log.ok(f"Exported template '{args.export}' to {out}")
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    import platform
    log.hl(f"yolo-forge {__version__}")
    log.info(f"Python:    {sys.version.split()[0]} ({platform.python_implementation()})")
    log.info(f"Platform:  {platform.platform()}")
    log.info("Modules:")
    log.info("  - yolo_forge_core    (installed)")
    try:
        import yolo_forge_desktop
        log.info("  - yolo_forge_desktop (installed)")
    except ImportError:
        log.warn("  - yolo_forge_desktop (NOT installed, run: pip install yolo-forge[desktop])")
    try:
        import yolo_forge_agent
        log.info("  - yolo_forge_agent   (installed)")
    except ImportError:
        log.warn("  - yolo_forge_agent   (NOT installed, run: pip install yolo-forge[agent])")

    log.info(f"Builtin templates: {list_builtin_templates()}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "review": _cmd_review,
        "convert": _cmd_convert,
        "inspect": _cmd_inspect,
        "train": _cmd_train,
        "templates": _cmd_templates,
        "info": _cmd_info,
    }
    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
