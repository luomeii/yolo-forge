"""渲染逻辑：在图像上画框、HUD、选中标记、新框拖拽预览.

把原脚本 _render / _draw_label / _draw_selection 抽出来,
app.py 只负责状态管理，渲染交给这里.
"""
from __future__ import annotations

from typing import List, Optional

import cv2
import numpy as np

from ..utils import yolo_to_px
from .viewport import Viewport

# 颜色常量（BGR）
COLOR_NEW_BOX = (0, 255, 255)        # 黄色：新增框
COLOR_DRAGGING = (255, 255, 0)       # 青色：正在拖拽
COLOR_SELECT_OUTER = (255, 255, 255)  # 白色：选中外框
COLOR_SELECT_CORNER = (0, 255, 0)    # 绿色：四角标记


def draw_box_label(
    vis: np.ndarray,
    text: str,
    x: int,
    y: int,
    color: tuple,
    font_scale: float = 0.4,
    thickness: int = 1,
) -> None:
    """在框上方画带背景色的文字标签."""
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    ly = max(y - th - 4, 0)
    cv2.rectangle(vis, (x, ly), (x + tw + 2, y), color, -1)
    cv2.putText(vis, text, (x + 1, y - 2), cv2.FONT_HERSHEY_SIMPLEX,
                font_scale, (255, 255, 255), thickness, cv2.LINE_AA)


def draw_selection(vis: np.ndarray, x1: int, y1: int, x2: int, y2: int, thickness: int = 1) -> None:
    """画选中状态：白色外框 + 四角绿色 L 形标记."""
    t = max(1, thickness // 2)
    # 外框
    cv2.rectangle(vis, (x1 - 3, y1 - 3), (x2 + 3, y2 + 3), COLOR_SELECT_OUTER, t)
    # 四角 L 形标记
    L = max(8, int(12 * thickness / 2))
    for cx, cy in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
        dx = L if cx == x1 else -L
        dy = L if cy == y1 else -L
        cv2.line(vis, (cx, cy), (cx + dx, cy), COLOR_SELECT_CORNER, t)
        cv2.line(vis, (cx, cy), (cx, cy + dy), COLOR_SELECT_CORNER, t)


def _try_color(cid: int) -> tuple:
    """尝试用 ultralytics 的颜色，失败则回退到固定色板."""
    try:
        from ultralytics.utils.plotting import colors
        return colors(cid, True)
    except Exception:
        palette = [
            (0, 0, 255), (0, 255, 0), (255, 0, 0), (0, 255, 255),
            (255, 0, 255), (255, 255, 0), (128, 0, 0), (0, 128, 0),
        ]
        return palette[cid % len(palette)]


def render_frame(
    img: np.ndarray,
    cur_boxes,           # List[(cid, (cx,cy,w,h))]
    new_px,              # List[[x1,y1,x2,y2,cls]]
    cls_names: List[str],
    viewport: Viewport,
    *,
    dragging_new: bool = False,
    drag_rect: Optional[tuple] = None,    # (sx, sy, ex, ey)
    sel_idx: int = -1,
    sel_is_new: bool = False,
) -> np.ndarray:
    """渲染一帧画面（图像 + 框 + 选中标记 + 拖拽预览）.

    返回缩放后的画布（不含 HUD bar）.
    """
    if img is None:
        return np.zeros((400, 600, 3), dtype=np.uint8)

    canvas = img.copy()
    H, W = canvas.shape[:2]

    # 动态线宽和字号，保证缩放后视觉一致
    lw = max(1, int(round(2 / viewport.scale)))
    fs = max(0.3, min(W, H) / 1600 / viewport.scale)

    # 1) 原始标注框
    for i, (cid, xywh) in enumerate(cur_boxes):
        x1, y1, x2, y2 = yolo_to_px(xywh, W, H)
        c = _try_color(cid)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), c, lw)
        nm = cls_names[cid] if cid < len(cls_names) else f"cls{cid}"
        draw_box_label(canvas, f"{cid}:{nm}", x1, y1, c, fs, lw)
        if not sel_is_new and sel_idx == i:
            draw_selection(canvas, x1, y1, x2, y2, lw)

    # 2) 新增框（黄色）
    for i, nb in enumerate(new_px):
        x1, y1, x2, y2, cls_id = nb
        cv2.rectangle(canvas, (x1, y1), (x2, y2), COLOR_NEW_BOX, lw)
        nm = cls_names[cls_id] if cls_id < len(cls_names) else f"cls{cls_id}"
        draw_box_label(canvas, f"+{cls_id}:{nm}", x1, y1, COLOR_NEW_BOX, fs, lw)
        if sel_is_new and sel_idx == i:
            draw_selection(canvas, x1, y1, x2, y2, lw)

    # 3) 正在拖拽的新框预览
    if dragging_new and drag_rect is not None:
        sx, sy, ex, ey = drag_rect
        cv2.rectangle(canvas, (sx, sy), (ex, ey), COLOR_DRAGGING, lw)

    # 4) 缩放 + 裁剪到视口
    if viewport.scale != 1.0:
        inter = cv2.INTER_AREA if viewport.scale < 1 else cv2.INTER_LINEAR
        scaled = cv2.resize(canvas, None, fx=viewport.scale, fy=viewport.scale, interpolation=inter)
    else:
        scaled = canvas

    sh, sw = scaled.shape[:2]
    max_w = viewport.canvas_w
    max_h = viewport.canvas_h

    vx = int(round(viewport.ox * viewport.scale))
    vy = int(round(viewport.oy * viewport.scale))

    sx1, sy1 = vx, vy
    sx2, sy2 = vx + max_w, vy + max_h

    cx1, cy1 = 0, 0
    cx2, cy2 = max_w, max_h

    if sx1 < 0: cx1 = -sx1; sx1 = 0
    if sy1 < 0: cy1 = -sy1; sy1 = 0
    if sx2 > sw: cx2 -= (sx2 - sw); sx2 = sw
    if sy2 > sh: cy2 -= (sy2 - sh); sy2 = sh

    out = np.zeros((max_h, max_w, 3), dtype=np.uint8)
    if sx1 < sx2 and sy1 < sy2 and cx1 < cx2 and cy1 < cy2:
        out[cy1:cy2, cx1:cx2] = scaled[sy1:sy2, sx1:sx2]
    return out


def render_hud(
    viewport: Viewport,
    *,
    idx: int,
    total: int,
    fname: str,
    n_orig: int,
    n_new: int,
    cur_cls: int,
    cls_names: List[str],
    draw_mode: bool,
    decision_tag: str = "---",
    cls_input_mode: bool = False,
    cls_input_text: str = "",
) -> np.ndarray:
    """渲染顶部 HUD bar."""
    max_w = viewport.canvas_w
    bar_h = viewport.bar_h
    bar = np.zeros((bar_h, max_w, 3), dtype=np.uint8)

    cls_nm = cls_names[cur_cls] if cur_cls < len(cls_names) else f"cls{cur_cls}"
    mode_str = "DRAW" if draw_mode else "REVIEW"
    zoom_pct = int(viewport.scale * 100)

    l1 = (f"[{idx + 1}/{total}] {fname}  Orig:{n_orig} New:{n_new}  "
          f"CurCls:{cur_cls}:{cls_nm}  [{mode_str}] Zoom:{zoom_pct}% {decision_tag}")
    cv2.putText(bar, l1, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1, cv2.LINE_AA)

    cls_parts = []
    for ci, nm in enumerate(cls_names):
        marker = ">" if ci == cur_cls else " "
        cls_parts.append(f"{marker}{ci}:{nm}")
    cls_line = "Cls: " + "  ".join(cls_parts)
    while len(cls_line) > 110 and len(cls_parts) > 1:
        cls_parts = cls_parts[:-1]
        cls_line = "Cls: " + "  ".join(cls_parts) + " ..."
    cv2.putText(bar, cls_line, (6, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (180, 220, 255), 1, cv2.LINE_AA)

    if draw_mode:
        l3 = "Drag=NewBox  ClickBox=Select  Move=Drag  BS=Del  0-9/[/]=Cls  n=NewCls  c=Done  ESC=ExitDraw"
    else:
        l3 = "k=OK  d=Bad  a=AddBox  j/l=Prev/Next  Click=Select  BS=Del  ~=UndoNew  n=NewCls  q=Quit"
    cv2.putText(bar, l3, (6, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.27,
                (0, 255, 255) if draw_mode else (180, 255, 180), 1, cv2.LINE_AA)

    l4 = "Scroll=Zoom  MidBtn=Pan  f=FitScreen"
    cv2.putText(bar, l4, (6, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.27, (160, 160, 160), 1, cv2.LINE_AA)

    if cls_input_mode:
        overlay = bar.copy()
        cv2.rectangle(overlay, (0, 0), (max_w, bar_h), (0, 0, 0), -1)
        bar = cv2.addWeighted(bar, 0.3, overlay, 0.7, 0)
        cv2.putText(bar, f"NEW CLASS NAME: {cls_input_text}_", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(bar, "Enter=Confirm  ESC=Cancel  Backspace=Delete", (10, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1, cv2.LINE_AA)

    return bar
