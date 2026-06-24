"""渲染逻辑 — v0.10.4 用 PIL 画文字, 彻底避免 cv2.putText 崩溃.

cv2.putText 在非连续 numpy 数组上会报错:
  "Layout of the output array img is incompatible with cv::Mat"
修复: 所有文字用 PIL 画, cv2 只画矩形/线条.
"""
from __future__ import annotations

from typing import List, Optional

import cv2
import numpy as np

from ..utils import yolo_to_px
from .viewport import Viewport

COLOR_NEW_BOX = (0, 255, 255)
COLOR_DRAGGING = (255, 255, 0)
COLOR_SELECT_OUTER = (255, 255, 255)
COLOR_SELECT_CORNER = (0, 255, 0)

_PIL_FONT_CACHE = {}

def _get_pil_font(size: int):
    if size in _PIL_FONT_CACHE:
        return _PIL_FONT_CACHE[size]
    from PIL import ImageFont
    font = None
    for fp in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
               "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/msyh.ttc"]:
        try:
            font = ImageFont.truetype(fp, size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    _PIL_FONT_CACHE[size] = font
    return font

_PENDING_TEXTS = []

def draw_box_label(vis, text, x, y, color, font_scale=0.4, thickness=1):
    global _PENDING_TEXTS
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    ly = max(y - th - 4, 0)
    cv2.rectangle(vis, (x, ly), (x + tw + 2, y), color, -1)
    _PENDING_TEXTS.append((text, x + 1, y - th - 2, font_scale))

def _flush_texts_with_pil(img):
    global _PENDING_TEXTS
    if not _PENDING_TEXTS:
        return img
    from PIL import Image, ImageDraw
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil_img)
    for text, x, y, font_scale in _PENDING_TEXTS:
        font_size = max(10, int(font_scale * 30))
        font = _get_pil_font(font_size)
        draw.text((x, y), text, fill=(255, 255, 255), font=font)
    _PENDING_TEXTS = []
    return np.ascontiguousarray(cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR))

def draw_selection(vis, x1, y1, x2, y2, thickness=1):
    t = max(1, thickness // 2)
    cv2.rectangle(vis, (x1 - 3, y1 - 3), (x2 + 3, y2 + 3), COLOR_SELECT_OUTER, t)
    L = max(8, int(12 * thickness / 2))
    for cx, cy in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
        dx = L if cx == x1 else -L
        dy = L if cy == y1 else -L
        cv2.line(vis, (cx, cy), (cx + dx, cy), COLOR_SELECT_CORNER, t)
        cv2.line(vis, (cx, cy), (cx, cy + dy), COLOR_SELECT_CORNER, t)

def _try_color(cid):
    try:
        from ultralytics.utils.plotting import colors
        return colors(cid, True)
    except Exception:
        palette = [(0,0,255),(0,255,0),(255,0,0),(0,255,255),(255,0,255),(255,255,0),(128,0,0),(0,128,0)]
        return palette[cid % len(palette)]

def render_frame(img, cur_boxes, new_px, cls_names, viewport, *,
                 dragging_new=False, drag_rect=None, sel_idx=-1, sel_is_new=False):
    global _PENDING_TEXTS
    _PENDING_TEXTS = []
    if img is None:
        return np.zeros((400, 600, 3), dtype=np.uint8)
    canvas = np.ascontiguousarray(img.copy())
    H, W = canvas.shape[:2]
    lw = max(1, int(round(2 / viewport.scale)))
    fs = max(0.3, min(W, H) / 1600 / viewport.scale)
    for i, (cid, xywh) in enumerate(cur_boxes):
        x1, y1, x2, y2 = yolo_to_px(xywh, W, H)
        c = _try_color(cid)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), c, lw)
        nm = cls_names[cid] if cid < len(cls_names) else f"cls{cid}"
        draw_box_label(canvas, f"{cid}:{nm}", x1, y1, c, fs, lw)
        if not sel_is_new and sel_idx == i:
            draw_selection(canvas, x1, y1, x2, y2, lw)
    for i, nb in enumerate(new_px):
        x1, y1, x2, y2, cls_id = nb
        cv2.rectangle(canvas, (x1, y1), (x2, y2), COLOR_NEW_BOX, lw)
        nm = cls_names[cls_id] if cls_id < len(cls_names) else f"cls{cls_id}"
        draw_box_label(canvas, f"+{cls_id}:{nm}", x1, y1, COLOR_NEW_BOX, fs, lw)
        if sel_is_new and sel_idx == i:
            draw_selection(canvas, x1, y1, x2, y2, lw)
    if dragging_new and drag_rect is not None:
        sx, sy, ex, ey = drag_rect
        cv2.rectangle(canvas, (sx, sy), (ex, ey), COLOR_DRAGGING, lw)
    canvas = _flush_texts_with_pil(canvas)
    if viewport.scale != 1.0:
        inter = cv2.INTER_AREA if viewport.scale < 1 else cv2.INTER_LINEAR
        scaled = np.ascontiguousarray(cv2.resize(canvas, None, fx=viewport.scale, fy=viewport.scale, interpolation=inter))
    else:
        scaled = canvas
    sh, sw = scaled.shape[:2]
    max_w, max_h = viewport.canvas_w, viewport.canvas_h
    vx, vy = int(round(viewport.ox * viewport.scale)), int(round(viewport.oy * viewport.scale))
    sx1, sy1, sx2, sy2 = vx, vy, vx + max_w, vy + max_h
    cx1, cy1, cx2, cy2 = 0, 0, max_w, max_h
    if sx1 < 0: cx1 = -sx1; sx1 = 0
    if sy1 < 0: cy1 = -sy1; sy1 = 0
    if sx2 > sw: cx2 -= (sx2 - sw); sx2 = sw
    if sy2 > sh: cy2 -= (sy2 - sh); sy2 = sh
    out = np.zeros((max_h, max_w, 3), dtype=np.uint8)
    if sx1 < sx2 and sy1 < sy2 and cx1 < cx2 and cy1 < cy2:
        out[cy1:cy2, cx1:cx2] = np.ascontiguousarray(scaled[sy1:sy2, sx1:sx2])
    return out

def render_hud(viewport, *, idx, total, fname, n_orig, n_new, cur_cls, cls_names,
               draw_mode, decision_tag="---", cls_input_mode=False, cls_input_text=""):
    max_w = viewport.canvas_w
    bar_h = viewport.bar_h
    bar = np.zeros((max(1, bar_h), max_w, 3), dtype=np.uint8)
    return bar
