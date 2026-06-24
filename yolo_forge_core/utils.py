"""Shared utility functions for yolo-forge.

共享工具函数：坐标转换、路径处理、日志、文件遍历等。
所有子模块都应通过这里访问公共逻辑，避免重复实现。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

# 支持的图像扩展名（小写）
IMG_EXTS: frozenset = frozenset({
    ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp",
})


# ─────────────────────────────────────────────────────────────
#  YOLO 坐标 ↔ 像素坐标
# ─────────────────────────────────────────────────────────────
def yolo_to_px(xywh: Tuple[float, float, float, float], W: int, H: int) -> Tuple[int, int, int, int]:
    """YOLO 归一化 (cx, cy, w, h) → 像素 (x1, y1, x2, y2)."""
    cx, cy, w, h = xywh
    cx *= W
    cy *= H
    w *= W
    h *= H
    return int(cx - w / 2), int(cy - h / 2), int(cx + w / 2), int(cy + h / 2)


def px_to_yolo(x1: float, y1: float, x2: float, y2: float, W: int, H: int) -> Tuple[float, float, float, float]:
    """像素 (x1, y1, x2, y2) → YOLO 归一化 (cx, cy, w, h)."""
    return (
        ((x1 + x2) / 2) / W,
        ((y1 + y2) / 2) / H,
        (x2 - x1) / W,
        (y2 - y1) / H,
    )


def voc_to_yolo(xmin: float, ymin: float, xmax: float, ymax: float, W: int, H: int) -> Tuple[float, float, float, float]:
    """VOC 绝对像素坐标 → YOLO 归一化."""
    return (
        ((xmin + xmax) / 2) / W,
        ((ymin + ymax) / 2) / H,
        (xmax - xmin) / W,
        (ymax - ymin) / H,
    )


def coco_to_yolo(x: float, y: float, w: float, h: float, W: int, H: int) -> Tuple[float, float, float, float]:
    """COCO (x_top_left, y_top_left, w, h) → YOLO 归一化."""
    return (
        (x + w / 2) / W,
        (y + h / 2) / H,
        w / W,
        h / H,
    )


# ─────────────────────────────────────────────────────────────
#  几何工具
# ─────────────────────────────────────────────────────────────
def point_in_rect(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> bool:
    """判断点是否在矩形内（允许 x1>x2 的反向写法）."""
    return (
        min(x1, x2) <= px <= max(x1, x2)
        and min(y1, y2) <= py <= max(y1, y2)
    )


def clamp(v: float, lo: float, hi: float) -> float:
    """将 v 限制在 [lo, hi] 区间."""
    return max(lo, min(v, hi))


# ─────────────────────────────────────────────────────────────
#  路径 / 文件遍历
# ─────────────────────────────────────────────────────────────
def list_images(folder: str | Path, exts: Iterable[str] | None = None) -> List[str]:
    """列出文件夹下所有支持的图像文件名（仅文件名，非完整路径）.

    Parameters
    ----------
    folder : str | Path
        目标文件夹
    exts : iterable of str, optional
        自定义扩展名集合，默认 :data:`IMG_EXTS`
    """
    ext_set = set(exts) if exts else IMG_EXTS
    if not os.path.isdir(folder):
        return []
    return sorted(
        f for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in ext_set
    )


def ensure_dir(path: str | Path) -> Path:
    """确保目录存在，返回 Path 对象."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def stem_of(filename: str) -> str:
    """获取无扩展名的主干名（跨平台）."""
    return os.path.splitext(filename)[0]


# ─────────────────────────────────────────────────────────────
#  日志
# ─────────────────────────────────────────────────────────────
class _Logger:
    """轻量级彩色终端日志，避免依赖第三方库."""

    RESET = "\033[0m"
    COLORS = {
        "info": "\033[37m",     # white
        "ok": "\033[32m",       # green
        "warn": "\033[33m",     # yellow
        "err": "\033[31m",      # red
        "hl": "\033[36m",       # cyan
    }

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def _emit(self, level: str, msg: str) -> None:
        if not self.enabled:
            return
        c = self.COLORS.get(level, "")
        # 在非 TTY 环境下不输出颜色码，避免污染日志文件
        if not sys.stdout.isatty():
            c = ""
            suffix = ""
        else:
            suffix = self.RESET
        prefix = {
            "info": "[i]",
            "ok": "[+]",
            "warn": "[!]",
            "err": "[x]",
            "hl": "[*]",
        }.get(level, "[?]")
        print(f"{c}{prefix} {msg}{suffix}")

    def info(self, msg: str) -> None: self._emit("info", msg)
    def ok(self, msg: str) -> None: self._emit("ok", msg)
    def warn(self, msg: str) -> None: self._emit("warn", msg)
    def err(self, msg: str) -> None: self._emit("err", msg)
    def hl(self, msg: str) -> None: self._emit("hl", msg)


log = _Logger(enabled=True)
