"""视口逻辑：缩放/平移/坐标转换.

把原脚本里 _fit_to_screen / _disp2img 等视口相关方法抽成独立类,
便于单元测试和未来支持多视口.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

from ..utils import clamp


@dataclass
class Viewport:
    """图像视口状态：保存当前缩放比和偏移.

    Attributes
    ----------
    scale : float
        缩放比（>1 放大，<1 缩小）
    ox, oy : float
        视口原点在原始图像坐标系下的偏移（图像坐标）
    bar_h : int
        顶部 HUD 高度（像素）
    canvas_w, canvas_h : int
        画布尺寸（窗口宽高减去 bar_h）
    """

    scale: float = 1.0
    ox: float = 0.0
    oy: float = 0.0
    bar_h: int = 90
    canvas_w: int = 1280
    canvas_h: int = 810

    def fit_to_screen(self, img: np.ndarray) -> None:
        """缩放并平移视口使图片完整居中显示."""
        if img is None:
            return
        iH, iW = img.shape[:2]
        max_w = self.canvas_w
        max_h = self.canvas_h

        self.scale = min(max_w / iW, max_h / iH)
        scaled_w = iW * self.scale
        scaled_h = iH * self.scale

        # 居中：如果图片比画布小则负偏移（外移），如果大则正偏移（内移）
        if scaled_w < max_w:
            self.ox = - (max_w - scaled_w) / (2 * self.scale)
        else:
            self.ox = (scaled_w - max_w) / (2 * self.scale)
        if scaled_h < max_h:
            self.oy = - (max_h - scaled_h) / (2 * self.scale)
        else:
            self.oy = (scaled_h - max_h) / (2 * self.scale)

    def disp_to_img(self, dx: float, dy: float, img: np.ndarray | None) -> Tuple[int, int]:
        """窗口显示坐标 → 原始图像坐标."""
        canvas_y = dy - self.bar_h
        canvas_x = dx

        scaled_x = canvas_x + self.ox * self.scale
        scaled_y = canvas_y + self.oy * self.scale

        if self.scale > 0:
            img_x = scaled_x / self.scale
            img_y = scaled_y / self.scale
        else:
            img_x, img_y = 0.0, 0.0

        if img is not None:
            iH, iW = img.shape[:2]
            img_x = clamp(int(round(img_x)), 0, iW - 1)
            img_y = clamp(int(round(img_y)), 0, iH - 1)
        return int(img_x), int(img_y)

    def zoom_around(self, img_x: float, img_y: float, factor: float) -> None:
        """以图像中某点为中心缩放.

        保持鼠标下的图像点不变，调整 ox/oy.
        """
        old_scale = self.scale
        new_scale = clamp(old_scale * factor, 0.05, 10.0)
        if new_scale == old_scale:
            return
        ratio = old_scale / new_scale
        self.ox = img_x - (img_x - self.ox) * ratio
        self.oy = img_y - (img_y - self.oy) * ratio
        self.scale = new_scale

    def pan_by(self, dx_disp: float, dy_disp: float) -> None:
        """按显示像素偏移量平移视口."""
        if self.scale > 0:
            self.ox -= dx_disp / self.scale
            self.oy -= dy_disp / self.scale
