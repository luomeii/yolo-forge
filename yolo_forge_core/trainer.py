"""训练封装：薄包装 Ultralytics 官方 API, 不自研训练逻辑.

设计原则:
- 只暴露 yolo-forge 需要的字段, 不重新发明 YOLO 参数体系
- 训练在独立子进程跑, 主 GUI 线程不被阻塞
- 通过回调把日志/进度传出去, GUI 决定怎么显示
- 失败/取消/完成三种状态都要明确回调
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from .utils import ensure_dir, log


# ─────────────────────────────────────────────────────────────
#  训练配置
# ─────────────────────────────────────────────────────────────
@dataclass
class TrainConfig:
    """Ultralytics YOLO 训练配置.

    只列最常用的字段, 其余高级参数走 ultralytics 原生 API 二次设置.
    """

    # 必填
    data_yaml: str                 # data.yaml 路径
    model: str = "yolo11n.pt"      # 预训练权重 / 模型规模

    # 训练超参
    epochs: int = 100
    imgsz: int = 640
    batch: int = 16
    device: str = ""               # ""=auto, "0"=gpu0, "cpu"
    workers: int = 4

    # 输出
    project: str = "./runs"
    name: str = "exp"

    # 增强 / 早停
    patience: int = 50             # 早停耐心值
    augment: bool = True

    # 其他
    seed: int = 42
    verbose: bool = True

    def to_ultralytics_kwargs(self) -> dict:
        """转成 ultralytics YOLO.train() 接受的 kwargs."""
        return dict(
            data=self.data_yaml,
            model=self.model,
            epochs=self.epochs,
            imgsz=self.imgsz,
            batch=self.batch,
            device=self.device or None,
            workers=self.workers,
            project=self.project,
            name=self.name,
            patience=self.patience,
            augment=self.augment,
            seed=self.seed,
            verbose=self.verbose,
        )


# ─────────────────────────────────────────────────────────────
#  训练回调
# ─────────────────────────────────────────────────────────────
@dataclass
class TrainCallbacks:
    """训练过程的回调钩子集合, GUI 通过这些更新界面."""

    on_log: Callable[[str], None] = lambda s: None       # 每行 stdout
    on_progress: Callable[[float, str], None] = lambda p, s: None  # 0.0~1.0 + 状态
    on_metrics: Callable[[dict], None] = lambda m: None  # 解析出的指标
    on_complete: Callable[[str], None] = lambda p: None  # 完成时调用, 传 best.pt 路径
    on_error: Callable[[str], None] = lambda e: None     # 失败时调用, 传错误信息


# ─────────────────────────────────────────────────────────────
#  训练器
# ─────────────────────────────────────────────────────────────
# 解析 ultralytics 训练日志里的关键指标
_EPOCH_RE = re.compile(
    r"\s+(\d+)/(\d+)\s+.*?box_loss:([\d.]+).*?cls_loss:([\d.]+).*?dfl_loss:([\d.]+)"
)
_METRIC_RE = re.compile(
    r"(all|names)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"
)


class Trainer:
    """训练执行器: 子进程跑 ultralytics CLI, 主线程通过回调拿状态.

    为什么用子进程而不是 in-process ultralytics:
    - ultralytics 训练会占满 GPU, 子进程崩了不影响 GUI
    - 子进程能干净地被 terminate, in-process 训练中途取消很麻烦
    - 子进程的 stdout 直接是训练日志, 解析方便
    """

    def __init__(self, config: TrainConfig, callbacks: Optional[TrainCallbacks] = None):
        self.config = config
        self.callbacks = callbacks or TrainCallbacks()
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._last_epoch = 0
        self._total_epochs = config.epochs

    # ────────── 公共 API ──────────
    def start(self) -> None:
        """异步启动训练. 立即返回, 通过 callbacks 推送状态."""
        if self._thread and self._thread.is_alive():
            log.warn("训练已在运行中")
            return
        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """请求停止训练. 等子进程退出."""
        self._stop_flag.set()
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ────────── 内部 ──────────
    def _build_command(self) -> List[str]:
        """构造 yolo train CLI 命令."""
        cmd = [
            sys.executable, "-m", "ultralytics",
            "train",
            "model=" + self.config.model,
            "data=" + self.config.data_yaml,
            f"epochs={self.config.epochs}",
            f"imgsz={self.config.imgsz}",
            f"batch={self.config.batch}",
            f"workers={self.config.workers}",
            f"project={self.config.project}",
            f"name={self.config.name}",
            f"patience={self.config.patience}",
            f"seed={self.config.seed}",
        ]
        if self.config.device:
            cmd.append("device=" + self.config.device)
        if not self.config.augment:
            cmd.append("augment=False")
        return cmd

    def _run(self) -> None:
        cmd = self._build_command()
        log.info(f"启动训练: {' '.join(shlex.quote(c) for c in cmd)}")
        self.callbacks.on_progress(0.0, "Starting training...")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as e:
            self.callbacks.on_error(f"启动训练失败: {e}")
            return

        assert self._process.stdout is not None
        for line in self._process.stdout:
            if self._stop_flag.is_set():
                break
            line = line.rstrip()
            if not line:
                continue
            self.callbacks.on_log(line)
            self._parse_line(line)

        self._process.wait()
        rc = self._process.returncode

        if self._stop_flag.is_set():
            self.callbacks.on_error("训练被用户取消")
            return
        if rc != 0:
            self.callbacks.on_error(f"训练进程异常退出 (code={rc})")
            return

        # 找 best.pt
        best_pt = Path(self.config.project) / self.config.name / "weights" / "best.pt"
        self.callbacks.on_progress(1.0, "Done")
        self.callbacks.on_complete(str(best_pt) if best_pt.exists() else "")

    def _parse_line(self, line: str) -> None:
        """从训练日志解析 epoch 进度和关键指标."""
        m = _EPOCH_RE.search(line)
        if m:
            cur = int(m.group(1))
            total = int(m.group(2))
            self._last_epoch = cur
            self._total_epochs = total
            progress = cur / max(total, 1)
            metrics = {
                "epoch": cur,
                "total_epochs": total,
                "box_loss": float(m.group(3)),
                "cls_loss": float(m.group(4)),
                "dfl_loss": float(m.group(5)),
            }
            self.callbacks.on_metrics(metrics)
            self.callbacks.on_progress(progress, f"Epoch {cur}/{total}")
            return

        m = _METRIC_RE.search(line)
        if m and m.group(1) == "all":
            metrics = {
                "images": int(m.group(2)),
                "precision": float(m.group(3)),
                "recall": float(m.group(4)),
                "mAP50": float(m.group(5)),
                "mAP50_95": float(m.group(6)),
            }
            self.callbacks.on_metrics(metrics)


# ─────────────────────────────────────────────────────────────
#  便捷函数
# ─────────────────────────────────────────────────────────────
def quick_train(
    data_yaml: str,
    model: str = "yolo11n.pt",
    epochs: int = 100,
    on_log: Optional[Callable[[str], None]] = None,
) -> str:
    """同步便捷训练函数. 返回 best.pt 路径. 阻塞调用方.

    用于脚本场景. GUI 场景请用 Trainer 类 + start() 异步执行.
    """
    result: dict = {"best_pt": "", "error": ""}

    def _on_complete(p: str) -> None:
        result["best_pt"] = p

    def _on_error(e: str) -> None:
        result["error"] = e

    cfg = TrainConfig(data_yaml=data_yaml, model=model, epochs=epochs)
    cbs = TrainCallbacks(
        on_log=on_log or (lambda s: None),
        on_complete=_on_complete,
        on_error=_on_error,
    )
    trainer = Trainer(cfg, cbs)
    trainer.start()
    # 等待线程结束
    if trainer._thread:
        trainer._thread.join()

    if result["error"]:
        raise RuntimeError(result["error"])
    return result["best_pt"]
