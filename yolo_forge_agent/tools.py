"""Agent 工具集: 把 yolo_forge_core 的能力包装成 LLM 可调用的工具.

每个工具包含:
- schema: OpenAI function calling 格式的 JSON schema
- executor: 实际执行函数, 接收参数 dict, 返回字符串结果

设计原则:
- 严格参数校验, 失败返回错误信息给 LLM, 让它自己修正
- 长任务 (训练/转换) 通过 callback 推进度, 不阻塞对话
- 安全边界: 工具不直接修改源数据 (除了 reviewer 那边, 但 reviewer 不在工具集里)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import get_config


# 工具执行进度回调: (tool_name, status_text)
ProgressCallback = Callable[[str, str], None]


# ─────────────────────────────────────────────────────────────
#  工具 Schema 定义 (OpenAI function calling 格式)
# ─────────────────────────────────────────────────────────────
TOOL_SCHEMAS: List[dict] = [
    {
        "type": "function",
        "function": {
            "name": "inspect_dataset",
            "description": (
                "扫描数据集根目录, 返回结构化报告 (子文件夹列表、图片数、标签格式、"
                "class id 分布等). 不修改任何文件, 只读. "
                "当用户想了解数据集结构、或者要转换数据集前先用这个看清楚结构."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "数据集根目录的绝对路径, 例如 D:\\\\数据集\\\\datasets 或 /home/user/datasets",
                    },
                    "sample_size": {
                        "type": "integer",
                        "description": "每个子文件夹抽样标签文件数, 默认 5",
                        "default": 5,
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert_dataset",
            "description": (
                "用 YAML profile 把异构数据集转换为标准 YOLO 训练布局 "
                "(images/train, images/val, labels/train, labels/val, data.yaml). "
                "需要先有 profile YAML — 可以由你 (LLM) 根据 inspect_dataset 结果生成, "
                "也可以用户提供文件路径. 转换是复制操作, 不修改源文件."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_yaml": {
                        "type": "string",
                        "description": "完整的 profile YAML 内容 (字符串). 包含 name, output_dir, classes, sources 等字段.",
                    },
                    "profile_path": {
                        "type": "string",
                        "description": "或者直接给 profile YAML 文件路径. 优先用 profile_yaml.",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "true=只扫描不写文件 (验证 profile), false=实际转换. 默认 false.",
                        "default": False,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "train_model",
            "description": (
                "用 Ultralytics 训练 YOLO 模型. 训练在后台子进程跑, 不阻塞对话. "
                "训练完返回 best.pt 路径和实验目录路径, 可以接着用 generate_report 分析. "
                "注意: 训练耗时较长 (小数据集 10-30 分钟, 大数据集几小时)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "data_yaml": {
                        "type": "string",
                        "description": "data.yaml 文件路径 (Ultralytics 格式, 通常由 convert_dataset 生成)",
                    },
                    "model": {
                        "type": "string",
                        "description": "预训练模型, 默认 yolo11n.pt. 可选 yolo11n/s/m/l/x.pt",
                        "default": "yolo11n.pt",
                    },
                    "epochs": {
                        "type": "integer",
                        "description": "训练轮数, 默认 100. 小数据集 50-100, 大数据集 200-500.",
                        "default": 100,
                    },
                    "imgsz": {
                        "type": "integer",
                        "description": "图像尺寸, 默认 640",
                        "default": 640,
                    },
                    "batch": {
                        "type": "integer",
                        "description": "batch size, 默认 16",
                        "default": 16,
                    },
                    "device": {
                        "type": "string",
                        "description": "设备, 空字符串=自动, '0'=GPU0, 'cpu'=CPU",
                        "default": "",
                    },
                },
                "required": ["data_yaml"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": (
                "分析训练输出目录的 results.csv 和混淆矩阵, 生成 markdown 训练报告. "
                "报告包含: 整体表现 (mAP/precision/recall), 类别级表现, 训练曲线观察, 改进建议. "
                "训练完用这个看效果."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "training_output_dir": {
                        "type": "string",
                        "description": "Ultralytics 训练输出目录路径 (含 results.csv), 例如 runs/exp 或 runs/train/exp",
                    },
                },
                "required": ["training_output_dir"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_builtin_templates",
            "description": (
                "列出 yolo-forge 内置的数据集转换 profile 模板, 返回每个模板的名称和说明. "
                "当用户不知道怎么写 profile 时, 先用这个看有哪些现成模板."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_builtin_template",
            "description": (
                "获取一个内置模板的完整 YAML 内容. 用户选好模板后用这个拿 YAML, "
                "再根据实际数据集路径修改 path 字段就能用."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "模板名 (用 list_builtin_templates 拿到的)",
                    },
                },
                "required": ["name"],
            },
        },
    },
]


# ─────────────────────────────────────────────────────────────
#  工具执行器
# ─────────────────────────────────────────────────────────────
class ToolExecutor:
    """工具执行器: 接收 (tool_name, args) → 返回字符串结果.

    Parameters
    ----------
    on_progress : callable(tool_name, status_text), optional
        进度回调, 用于 UI 实时显示
    train_started_callback : callable(train_dir), optional
        训练启动时的回调, 让 UI 知道训练目录 (训练是长任务, 不能等它跑完才返回)
    """

    def __init__(
        self,
        on_progress: Optional[ProgressCallback] = None,
        on_train_start: Optional[Callable[[str], None]] = None,
        on_train_log: Optional[Callable[[str], None]] = None,
        on_train_complete: Optional[Callable[[str, str], None]] = None,  # (best_pt, train_dir)
    ):
        self.on_progress = on_progress or (lambda name, status: None)
        self.on_train_start = on_train_start or (lambda train_dir: None)
        self.on_train_log = on_train_log or (lambda line: None)
        self.on_train_complete = on_train_complete or (lambda best_pt, train_dir: None)
        self._active_trainer = None  # 用于支持取消

    def execute(self, tool_name: str, args: dict) -> str:
        """执行一个工具, 返回结果字符串."""
        try:
            handler = getattr(self, f"_tool_{tool_name}", None)
            if handler is None:
                return f"[x] 未知工具: {tool_name}"
            return handler(args)
        except Exception as e:
            import traceback
            return f"[x] 工具 {tool_name} 执行失败: {e}\n{traceback.format_exc()}"

    # ─── 工具: inspect_dataset ───
    def _tool_inspect_dataset(self, args: dict) -> str:
        from yolo_forge_core.inspector import inspect_dataset

        path = args.get("path", "").strip()
        if not path:
            return "[x] 缺少必要参数: path"
        if not Path(path).is_dir():
            return f"[x] 目录不存在: {path}"

        sample_size = int(args.get("sample_size", 5))
        self.on_progress("inspect_dataset", f"扫描中: {path}")

        report = inspect_dataset(path, sample_size=sample_size)
        self.on_progress("inspect_dataset", "扫描完成")

        # 返回紧凑文本给 LLM, 让 LLM 自己组织自然语言回复
        return report.to_llm_prompt()

    # ─── 工具: convert_dataset ───
    def _tool_convert_dataset(self, args: dict) -> str:
        from yolo_forge_core.converter.profiles import DatasetProfile
        from yolo_forge_core.converter.engine import convert_dataset

        yaml_text = args.get("profile_yaml", "").strip()
        profile_path = args.get("profile_path", "").strip()
        dry_run = bool(args.get("dry_run", False))

        if not yaml_text and not profile_path:
            return "[x] 必须提供 profile_yaml (YAML 内容) 或 profile_path (文件路径) 之一"

        try:
            if yaml_text:
                import yaml
                profile_dict = yaml.safe_load(yaml_text)
                profile = DatasetProfile.from_dict(profile_dict)
            else:
                if not Path(profile_path).is_file():
                    return f"[x] profile 文件不存在: {profile_path}"
                profile = DatasetProfile.from_yaml(profile_path)
        except Exception as e:
            return f"[x] profile 解析失败: {e}\n\n请检查 YAML 格式是否正确, 必须有 name, output_dir, classes, sources 字段."

        ok, errors = profile.validate()
        if not ok:
            return "[x] profile 校验失败:\n" + "\n".join(f"  - {e}" for e in errors)

        self.on_progress("convert_dataset", f"开始转换 (dry_run={dry_run})")
        try:
            report = convert_dataset(profile, dry_run=dry_run)
        except Exception as e:
            return f"[x] 转换失败: {e}"

        return (
            f"[ok] 转换完成\n"
            f"输出目录: {report.output_dir}\n"
            f"训练/验证/测试图片数: {report.train_count}/{report.val_count}/{report.test_count}\n"
            f"总标注框: {report.total_boxes}\n"
            f"耗时: {report.elapsed_seconds:.2f}s\n"
            f"data.yaml 位置: {Path(report.output_dir) / 'data.yaml'}\n\n"
            f"下一步: 用 train_model 工具训练, 或用 inspect_dataset 工具验证输出结构。"
        )

    # ─── 工具: train_model (长任务, 后台跑) ───
    def _tool_train_model(self, args: dict) -> str:
        from yolo_forge_core.trainer import TrainConfig, Trainer, TrainCallbacks

        data_yaml = args.get("data_yaml", "").strip()
        if not data_yaml:
            return "[x] 缺少必要参数: data_yaml"
        if not Path(data_yaml).is_file():
            return f"[x] data.yaml 不存在: {data_yaml}"

        cfg = TrainConfig(
            data_yaml=data_yaml,
            model=args.get("model", "yolo11n.pt"),
            epochs=int(args.get("epochs", 100)),
            imgsz=int(args.get("imgsz", 640)),
            batch=int(args.get("batch", 16)),
            device=args.get("device", ""),
        )

        train_dir = str(Path(cfg.project) / cfg.name)
        self.on_progress("train_model", f"启动训练: {cfg.model}, {cfg.epochs} epochs")
        self.on_train_start(train_dir)

        # 训练在后台线程跑, 立即返回提示, 完成后通过 on_train_complete 回调
        import threading
        result_holder = {"best_pt": "", "error": ""}

        def run_in_background():
            try:
                cbs = TrainCallbacks(
                    on_log=lambda s: self.on_train_log(s),
                    on_progress=lambda p, status: self.on_progress("train_model", status),
                    on_metrics=lambda m: None,
                    on_complete=lambda bp: result_holder.__setitem__("best_pt", bp),
                    on_error=lambda e: result_holder.__setitem__("error", e),
                )
                trainer = Trainer(cfg, cbs)
                self._active_trainer = trainer
                trainer.start()
                if trainer._thread:
                    trainer._thread.join()

                best_pt = result_holder["best_pt"]
                error = result_holder["error"]
                if error:
                    self.on_train_complete("", "")
                else:
                    self.on_train_complete(best_pt, train_dir)
            except Exception as e:
                result_holder["error"] = str(e)
                self.on_train_complete("", "")

        thread = threading.Thread(target=run_in_background, daemon=True)
        thread.start()

        return (
            f"[>] 训练已启动 (后台运行, 不阻塞对话)\n"
            f"  data: {data_yaml}\n"
            f"  model: {cfg.model}\n"
            f"  epochs: {cfg.epochs}, imgsz: {cfg.imgsz}, batch: {cfg.batch}\n"
            f"  输出目录: {train_dir}\n\n"
            f"训练日志会实时推送到对话区。训练完成后会自动调用 generate_report 工具生成分析报告。\n"
            f"你可以继续问其他问题, 不需要等训练完。"
        )

    # ─── 工具: generate_report ───
    def _tool_generate_report(self, args: dict) -> str:
        from yolo_forge_agent.report_agent import ReportAgent

        train_dir = args.get("training_output_dir", "").strip()
        if not train_dir:
            return "[x] 缺少必要参数: training_output_dir"
        if not Path(train_dir).is_dir():
            return f"[x] 训练输出目录不存在: {train_dir}"

        results_csv = Path(train_dir) / "results.csv"
        if not results_csv.exists():
            return f"[x] 目录下没有 results.csv, 不是有效的训练输出目录: {train_dir}"

        self.on_progress("generate_report", f"分析训练结果: {train_dir}")

        agent = ReportAgent()
        result = agent.run(train_dir)

        if result.ok:
            return result.content
        else:
            return f"[x] 报告生成失败: {result.error}"

    # ─── 工具: list_builtin_templates ───
    def _tool_list_builtin_templates(self, args: dict) -> str:
        from yolo_forge_core.converter.builtins import BUILTIN_TEMPLATES

        lines = ["可用模板列表:"]
        for name, yaml_text in BUILTIN_TEMPLATES.items():
            # 提取 description 行
            desc = ""
            for line in yaml_text.split("\n"):
                if line.startswith("description:"):
                    desc = line.split("description:", 1)[1].strip().strip('"').strip("'")
                    break
            lines.append(f"\n• {name}: {desc}")
        lines.append("\n用 get_builtin_template 工具拿具体模板的 YAML 内容。")
        return "\n".join(lines)

    # ─── 工具: get_builtin_template ───
    def _tool_get_builtin_template(self, args: dict) -> str:
        from yolo_forge_core.converter.builtins import get_builtin_template

        name = args.get("name", "").strip()
        if not name:
            return "[x] 缺少必要参数: name"
        try:
            yaml_text = get_builtin_template(name)
            return f"模板「{name}」的 YAML 内容:\n\n```yaml\n{yaml_text}\n```\n\n用户需要修改 path 字段为实际数据集路径, 修改 output_dir 为想要的输出位置, 然后用 convert_dataset 工具执行转换。"
        except KeyError:
            return f"[x] 未知模板: {name}"
