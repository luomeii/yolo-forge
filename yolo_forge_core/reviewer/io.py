"""标签 I/O：YOLO .txt 格式读写.

支持中文路径（np.fromfile + cv2.imdecode 规避 OpenCV 在 Windows 下的中文路径问题）.
"""
from __future__ import annotations

import os
from typing import List, Tuple

import cv2
import numpy as np

from ..utils import ensure_dir


Box = Tuple[int, Tuple[float, float, float, float]]  # (class_id, (cx, cy, w, h))


def load_image(path: str) -> np.ndarray | None:
    """读取图片，兼容中文路径. 失败返回 None."""
    try:
        buf = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return img
    except Exception:
        try:
            return cv2.imread(path, cv2.IMREAD_COLOR)
        except Exception:
            return None


def load_labels(path: str) -> List[Box]:
    """读取 YOLO 标签文件.

    格式: ``class_id cx cy w h``（归一化坐标），每行一个框.
    空文件 / 不存在 → 返回空列表.
    """
    boxes: List[Box] = []
    if not os.path.exists(path):
        return boxes
    try:
        with open(path, "r", encoding="utf-8") as f:
            for ln in f:
                parts = ln.strip().split()
                if len(parts) < 5:
                    continue
                try:
                    cid = int(parts[0])
                    xywh = tuple(float(x) for x in parts[1:5])
                    boxes.append((cid, xywh))
                except ValueError:
                    continue
    except Exception:
        pass
    return boxes


def save_labels(path: str, boxes: List[Box]) -> None:
    """保存 YOLO 标签文件（覆盖写入）."""
    ensure_dir(os.path.dirname(path))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for cid, xywh in boxes:
            f.write(f"{cid} {xywh[0]:.10f} {xywh[1]:.10f} {xywh[2]:.10f} {xywh[3]:.10f}\n")
    os.replace(tmp, path)


def has_label_file(path: str) -> bool:
    return os.path.exists(path) and os.path.getsize(path) >= 0
