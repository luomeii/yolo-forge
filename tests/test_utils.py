"""坐标转换工具的单元测试."""
from __future__ import annotations

import pytest

from yolo_forge_core.utils import (
    clamp,
    coco_to_yolo,
    point_in_rect,
    px_to_yolo,
    voc_to_yolo,
    yolo_to_px,
)


class TestYoloConversions:
    def test_yolo_to_px_basic(self):
        # 中心点 + 宽高 (归一化) → 像素坐标
        x1, y1, x2, y2 = yolo_to_px((0.5, 0.5, 0.4, 0.4), 100, 100)
        assert (x1, y1) == (30, 30)
        assert (x2, y2) == (70, 70)

    def test_yolo_to_px_full_image(self):
        x1, y1, x2, y2 = yolo_to_px((0.5, 0.5, 1.0, 1.0), 200, 100)
        assert (x1, y1) == (0, 0)
        assert (x2, y2) == (200, 100)

    def test_px_to_yolo_roundtrip(self):
        # 像素 → YOLO → 像素 应当一致 (允许 1 像素误差)
        for x1, y1, x2, y2 in [(10, 20, 30, 40), (0, 0, 100, 100), (50, 50, 150, 200)]:
            xywh = px_to_yolo(x1, y1, x2, y2, 200, 300)
            rx1, ry1, rx2, ry2 = yolo_to_px(xywh, 200, 300)
            assert abs(rx1 - x1) <= 1
            assert abs(ry1 - y1) <= 1
            assert abs(rx2 - x2) <= 1
            assert abs(ry2 - y2) <= 1


class TestVocConversion:
    def test_voc_to_yolo(self):
        # VOC (xmin=10, ymin=20, xmax=30, ymax=40) on 100x100 → YOLO
        cx, cy, w, h = voc_to_yolo(10, 20, 30, 40, 100, 100)
        assert abs(cx - 0.2) < 1e-6
        assert abs(cy - 0.3) < 1e-6
        assert abs(w - 0.2) < 1e-6
        assert abs(h - 0.2) < 1e-6


class TestCocoConversion:
    def test_coco_to_yolo(self):
        # COCO (x=10, y=20, w=20, h=20) on 100x100 → YOLO
        cx, cy, w, h = coco_to_yolo(10, 20, 20, 20, 100, 100)
        # COCO x,y 是左上角, 中心应该是 (20, 30)
        assert abs(cx - 0.2) < 1e-6
        assert abs(cy - 0.3) < 1e-6
        assert abs(w - 0.2) < 1e-6
        assert abs(h - 0.2) < 1e-6


class TestGeometry:
    def test_point_in_rect_inside(self):
        assert point_in_rect(5, 5, 0, 0, 10, 10) is True

    def test_point_in_rect_outside(self):
        assert point_in_rect(15, 5, 0, 0, 10, 10) is False

    def test_point_in_rect_reversed_coords(self):
        # 允许 x1>x2 的写法
        assert point_in_rect(5, 5, 10, 10, 0, 0) is True

    def test_clamp(self):
        assert clamp(5, 0, 10) == 5
        assert clamp(-1, 0, 10) == 0
        assert clamp(15, 0, 10) == 10
