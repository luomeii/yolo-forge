"""Reviewer 主应用：YOLOReviewer 类.

负责状态管理、鼠标/键盘事件、主循环.
渲染通过 renderer 模块完成，视口通过 Viewport 类管理,
配置通过 ReviewerConfig 传入，不再有硬编码路径.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from ..utils import clamp, list_images, point_in_rect, px_to_yolo, stem_of, yolo_to_px
from .config import ReviewerConfig
from .io import load_image, load_labels, save_labels
from .renderer import render_frame, render_hud
from .viewport import Viewport


class YOLOReviewer:
    """YOLO 标签审查与补标工具.

    工作流: 浏览 → 发现漏标/错标 → 补框/删除/拖动 → 实时保存 → 满意归档.
    """

    def __init__(self, config: ReviewerConfig):
        ok, msg = config.validate()
        if not ok:
            print(f"[ERROR] 配置无效: {msg}")
            sys.exit(1)
        self.cfg = config

        # 输出目录结构
        self.out = Path(config.output_dir)
        self.sat_img = str(self.out / "satisfied" / "images")
        self.sat_lbl = str(self.out / "satisfied" / "labels")
        self.unsat_img = str(self.out / "unsatisfied" / "images")
        for d in [self.sat_img, self.sat_lbl, self.unsat_img]:
            os.makedirs(d, exist_ok=True)

        # 进度
        self.prog_path = str(self.out / "progress.json")
        self.prog = self._load_progress()

        # 文件列表
        self.img_dir = config.image_dir
        self.lbl_dir = config.label_dir
        self.flist = list_images(self.img_dir, config.img_exts)
        self.N = len(self.flist)
        if self.N == 0:
            print(f"[ERROR] {self.img_dir} 中没有图片")
            sys.exit(1)

        # 类别
        self.cls_names = list(config.classes)
        saved = self.prog.get("classes")
        if saved and len(saved) >= len(self.cls_names):
            self.cls_names = list(saved)

        # 状态
        self.idx = clamp(self.prog.get("last_idx", 0), 0, self.N - 1)
        self.cur_cls = 0
        self.draw_mode = False
        self.new_px: List[list] = []  # [x1,y1,x2,y2,cls]
        self.decisions = self.prog.get("decisions", {})
        self.auto_save_cnt = 0
        self.running = True

        # 视口
        self.viewport = Viewport(
            bar_h=90,
            canvas_w=config.max_w,
            canvas_h=config.max_h - 90,
        )

        # 鼠标交互状态
        self.dragging_new = False
        self.drag_sx = self.drag_sy = self.drag_ex = self.drag_ey = 0
        self.sel_idx = -1
        self.sel_is_new = False
        self.moving_box = False
        self.move_ox = self.move_oy = 0
        self.panning = False
        self.pan_sx = self.pan_sy = 0
        self.pan_ox_start = self.pan_oy_start = 0.0

        # 类别输入模式
        self.cls_input_mode = False
        self.cls_input_text = ""

        # 当前图片数据
        self.cur_img: Optional[np.ndarray] = None
        self.cur_boxes = []
        self.cur_img_path = ""
        self.cur_lbl_path = ""
        self.cur_stem = ""

        self.WIN = "yolo-forge review"

    # ────────── 进度持久化 ──────────
    def _load_progress(self) -> dict:
        if os.path.exists(self.prog_path):
            try:
                with open(self.prog_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"last_idx": 0, "decisions": {}, "classes": list(self.cfg.classes)}

    def _save_progress(self) -> None:
        os.makedirs(os.path.dirname(self.prog_path) or ".", exist_ok=True)
        data = {
            "last_idx": self.idx + 1,
            "decisions": self.decisions,
            "last_saved": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "classes": self.cls_names,
        }
        tmp = self.prog_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            shutil.move(tmp, self.prog_path)
        except Exception as e:
            print(f"  [WARN] 保存进度失败: {e}")

    # ────────── 加载 / 保存 ──────────
    def _load_current(self) -> None:
        if self.idx < 0 or self.idx >= self.N:
            self.cur_img = None
            return
        fname = self.flist[self.idx]
        self.cur_stem = stem_of(fname)
        self.cur_img_path = os.path.join(self.img_dir, fname)
        self.cur_lbl_path = os.path.join(self.lbl_dir, self.cur_stem + ".txt")
        self.cur_img = load_image(self.cur_img_path)
        self.cur_boxes = load_labels(self.cur_lbl_path)
        self.new_px = []
        self.sel_idx = -1
        self.moving_box = False
        self.dragging_new = False
        self.viewport.fit_to_screen(self.cur_img)
        if self.cur_img is None:
            print(f"  [WARN] 无法读取: {fname}")

    def _save_current(self) -> None:
        if self.cur_img is None:
            return
        H, W = self.cur_img.shape[:2]
        merged = list(self.cur_boxes)
        for nb in self.new_px:
            xywh = px_to_yolo(nb[0], nb[1], nb[2], nb[3], W, H)
            merged.append((nb[4], xywh))
        save_labels(self.cur_lbl_path, merged)

    # ────────── 框查找 / 坐标 ──────────
    def _find_box_at(self, px: int, py: int) -> Optional[tuple]:
        # 优先命中新增框（在最上层）
        for i in range(len(self.new_px) - 1, -1, -1):
            b = self.new_px[i]
            if point_in_rect(px, py, b[0], b[1], b[2], b[3]):
                return i, True
        for i in range(len(self.cur_boxes) - 1, -1, -1):
            cid, xywh = self.cur_boxes[i]
            if self.cur_img is not None:
                H, W = self.cur_img.shape[:2]
                x1, y1, x2, y2 = yolo_to_px(xywh, W, H)
                if point_in_rect(px, py, x1, y1, x2, y2):
                    return i, False
        return None

    def _box_coords_px(self, idx: int, is_new: bool) -> tuple:
        if is_new:
            b = self.new_px[idx]
            return b[0], b[1], b[2], b[3]
        cid, xywh = self.cur_boxes[idx]
        H, W = self.cur_img.shape[:2]
        return yolo_to_px(xywh, W, H)

    def _set_box_coords_px(self, idx: int, is_new: bool, x1: int, y1: int, x2: int, y2: int) -> None:
        if self.cur_img is None:
            return
        iH, iW = self.cur_img.shape[:2]
        x1, y1 = clamp(x1, 0, iW - 1), clamp(y1, 0, iH - 1)
        x2, y2 = clamp(x2, 0, iW - 1), clamp(y2, 0, iH - 1)
        if is_new:
            self.new_px[idx][0], self.new_px[idx][1] = x1, y1
            self.new_px[idx][2], self.new_px[idx][3] = x2, y2
        else:
            self.cur_boxes[idx] = (self.cur_boxes[idx][0], px_to_yolo(x1, y1, x2, y2, iW, iH))

    # ────────── 删除 / 撤销 ──────────
    def _delete_selected(self) -> None:
        if self.sel_idx < 0:
            return
        if self.sel_is_new:
            removed = self.new_px.pop(self.sel_idx)
            nm = self.cls_names[removed[4]] if removed[4] < len(self.cls_names) else f"cls{removed[4]}"
            print(f"  [DEL] 删除新增框 #{self.sel_idx} cls={removed[4]}:{nm}")
        else:
            cid, _ = self.cur_boxes.pop(self.sel_idx)
            nm = self.cls_names[cid] if cid < len(self.cls_names) else f"cls{cid}"
            print(f"  [DEL] 删除原始框 #{self.sel_idx} cls={cid}:{nm}")
        self.sel_idx = -1
        self.moving_box = False
        self._save_current()

    def _undo_last_new(self) -> None:
        if self.new_px:
            removed = self.new_px.pop()
            nm = self.cls_names[removed[4]] if removed[4] < len(self.cls_names) else f"cls{removed[4]}"
            print(f"  [UNDO] 撤销新增框 cls={removed[4]}:{nm}  (剩余{len(self.new_px)}个)")
            self._save_current()
        else:
            print("  [UNDO] 无新增框可撤销")

    # ────────── 归档 ──────────
    def _archive_satisfied(self) -> None:
        if self.cur_img is None:
            return
        fname = self.flist[self.idx]
        try:
            shutil.copy2(self.cur_img_path, os.path.join(self.sat_img, fname))
        except Exception as e:
            print(f"  [WARN] 复制图片失败: {e}")
        try:
            shutil.copy2(self.cur_lbl_path, os.path.join(self.sat_lbl, self.cur_stem + ".txt"))
        except Exception as e:
            print(f"  [WARN] 复制标签失败: {e}")

    def _archive_unsatisfied(self) -> None:
        if self.cur_img is None:
            return
        fname = self.flist[self.idx]
        try:
            shutil.copy2(self.cur_img_path, os.path.join(self.unsat_img, fname))
        except Exception as e:
            print(f"  [WARN] 复制图片失败: {e}")

    # ────────── 翻页 / 决策 ──────────
    def _go_next(self) -> None:
        self.idx += 1
        self._load_current()
        self.auto_save_cnt += 1

    def _do_satisfied(self) -> None:
        action = "edited_and_satisfied" if self.new_px else "satisfied"
        self._archive_satisfied()
        fname = self.flist[self.idx]
        self.decisions[fname] = action
        ba = f" +{len(self.new_px)}box" if self.new_px else ""
        tag = "EDIT+OK" if self.new_px else "OK"
        print(f"  [{self.idx + 1}/{self.N}] {tag} {fname} -> satisfied/{ba}")
        self._go_next()

    def _do_unsatisfied(self) -> None:
        self._archive_unsatisfied()
        fname = self.flist[self.idx]
        self.decisions[fname] = "unsatisfied"
        print(f"  [{self.idx + 1}/{self.N}] BAD {fname} -> unsatisfied/")
        self._go_next()

    # ────────── 类别 ──────────
    def _select_class(self, cid: int) -> None:
        if 0 <= cid < len(self.cls_names):
            self.cur_cls = cid
            print(f"  [CLS] → {cid}:{self.cls_names[cid]}")

    def _next_class(self) -> None:
        if self.cls_names:
            self.cur_cls = (self.cur_cls + 1) % len(self.cls_names)
            print(f"  [CLS] → {self.cur_cls}:{self.cls_names[self.cur_cls]}")

    def _prev_class(self) -> None:
        if self.cls_names:
            self.cur_cls = (self.cur_cls - 1) % len(self.cls_names)
            print(f"  [CLS] → {self.cur_cls}:{self.cls_names[self.cur_cls]}")

    def _handle_cls_input(self, key: int) -> None:
        if key == 13:  # Enter
            name = self.cls_input_text.strip()
            self.cls_input_mode = False
            self.cls_input_text = ""
            if not name:
                print("  [CLS] 已取消（空名称）")
                return
            if name in self.cls_names:
                new_id = self.cls_names.index(name)
                self.cur_cls = new_id
                print(f"  [CLS] 类别 '{name}' 已存在 (id={new_id})，已切换")
            else:
                self.cls_names.append(name)
                new_id = len(self.cls_names) - 1
                self.cur_cls = new_id
                print(f"  [CLS] 已添加类别: {new_id}:{name}")
        elif key == 27:  # ESC
            self.cls_input_mode = False
            self.cls_input_text = ""
            print("  [CLS] 已取消添加类别")
        elif key == 8:  # Backspace
            self.cls_input_text = self.cls_input_text[:-1]
        elif 32 <= key <= 126:
            self.cls_input_text += chr(key)

    # ────────── 补框模式 ──────────
    def _enter_draw(self) -> None:
        self.draw_mode = True
        print("  [DRAW] 补框模式 | 拖拽空白=画框 | 点击框=选中 | 拖拽框=移动 | BS=删除 | c=确认退出")

    def _exit_draw(self) -> None:
        self.draw_mode = False
        self.sel_idx = -1
        self.moving_box = False
        self.dragging_new = False

    # ────────── 鼠标回调 ──────────
    def _on_mouse(self, event: int, x: int, y: int, flags: int, param) -> None:
        if self.cls_input_mode or self.cur_img is None:
            return

        # 滚轮缩放
        if event == cv2.EVENT_MOUSEWHEEL:
            mx, my = self.viewport.disp_to_img(x, y, self.cur_img)
            delta = cv2.getMouseWheelDelta(flags)
            factor = 1.15 if delta > 0 else 1 / 1.15
            self.viewport.zoom_around(mx, my, factor)
            return

        # 中键平移
        if event == cv2.EVENT_MBUTTONDOWN:
            self.panning = True
            self.pan_sx, self.pan_sy = x, y
            self.pan_ox_start, self.pan_oy_start = self.viewport.ox, self.viewport.oy
            return
        if event == cv2.EVENT_MBUTTONUP:
            self.panning = False
            return
        if event == cv2.EVENT_MOUSEMOVE and self.panning:
            dx = x - self.pan_sx
            dy = y - self.pan_sy
            self.viewport.ox = self.pan_ox_start - dx / self.viewport.scale
            self.viewport.oy = self.pan_oy_start - dy / self.viewport.scale
            return

        ix, iy = self.viewport.disp_to_img(x, y, self.cur_img)

        if event == cv2.EVENT_LBUTTONDOWN:
            clicked = self._find_box_at(ix, iy)
            if clicked is not None:
                bidx, is_new = clicked
                self.sel_idx = bidx
                self.sel_is_new = is_new
                self.dragging_new = False
                if self.draw_mode:
                    self.moving_box = True
                    bx1, by1, _, _ = self._box_coords_px(bidx, is_new)
                    self.move_ox = ix - bx1
                    self.move_oy = iy - by1
            else:
                self.sel_idx = -1
                self.moving_box = False
                if self.draw_mode:
                    self.dragging_new = True
                    self.drag_sx = self.drag_ex = ix
                    self.drag_sy = self.drag_ey = iy

        elif event == cv2.EVENT_MOUSEMOVE:
            if self.dragging_new:
                self.drag_ex, self.drag_ey = ix, iy
            elif self.moving_box and self.sel_idx >= 0:
                bx1, by1, bx2, by2 = self._box_coords_px(self.sel_idx, self.sel_is_new)
                bw, bh = bx2 - bx1, by2 - by1
                nx1, ny1 = ix - self.move_ox, iy - self.move_oy
                iH, iW = self.cur_img.shape[:2]
                nx1 = clamp(nx1, 0, iW - bw)
                ny1 = clamp(ny1, 0, iH - bh)
                self._set_box_coords_px(self.sel_idx, self.sel_is_new,
                                        nx1, ny1, nx1 + bw, ny1 + bh)

        elif event == cv2.EVENT_LBUTTONUP:
            if self.dragging_new:
                self.dragging_new = False
                sx, sy, ex, ey = self.drag_sx, self.drag_sy, self.drag_ex, self.drag_ey
                if abs(ex - sx) >= 5 and abs(ey - sy) >= 5:
                    x1, y1 = min(sx, ex), min(sy, ey)
                    x2, y2 = max(sx, ex), max(sy, ey)
                    self.new_px.append([x1, y1, x2, y2, self.cur_cls])
                    nm = self.cls_names[self.cur_cls] if self.cur_cls < len(self.cls_names) else f"cls{self.cur_cls}"
                    print(f"  [ADD] 新增框 cls={self.cur_cls}:{nm}  (共{len(self.new_px)}个新框)")
                    self._save_current()
            elif self.moving_box:
                self.moving_box = False
                self._save_current()

        elif event == cv2.EVENT_RBUTTONDOWN:
            self.dragging_new = False
            self.moving_box = False
            self.sel_idx = -1

    # ────────── 键盘 ──────────
    def _handle_review_key(self, key: int) -> None:
        if key in (ord('q'), ord('Q'), 27):
            self._save_progress()
            print(f"\n[EXIT] 进度已保存。下次从第 {self.idx + 1}/{self.N} 张继续")
            self.running = False
        elif key in (ord('k'), ord('K')):
            self._do_satisfied()
        elif key in (ord('d'), ord('D')):
            self._do_unsatisfied()
        elif key in (ord('a'), ord('A')):
            self._enter_draw()
        elif key in (ord('j'), ord('J')):
            if self.idx > 0:
                self.idx -= 1
                self._load_current()
            else:
                print("  已是第一张")
        elif key in (ord('l'), ord('L')):
            fname = self.flist[self.idx]
            self.decisions[fname] = "skipped"
            self._go_next()
        elif key in (ord('n'), ord('N')):
            self.cls_input_mode = True
            self.cls_input_text = ""
        elif key in (ord('~'), ord('`')):
            self._undo_last_new()
        elif key in (8, 127):
            self._delete_selected()
        elif key in (ord('i'), ord('I')):
            self._show_stats()
        elif key in (ord('r'), ord('R')):
            self.idx = 0
            self._load_current()
            print("  [RESET] 从第1张开始")
        elif key in (ord('f'), ord('F')):
            self.viewport.fit_to_screen(self.cur_img)
        elif key in (ord('['), ord('{')):
            self._prev_class()
        elif key in (ord(']'), ord('}')):
            self._next_class()
        elif ord('0') <= key <= ord('9'):
            self._select_class(key - ord('0'))

    def _handle_draw_key(self, key: int) -> None:
        if key == 27:
            self._exit_draw()
        elif key == 13 or key in (ord('c'), ord('C')):
            self._exit_draw()
        elif key in (ord('k'), ord('K')):
            self._exit_draw()
            self._do_satisfied()
        elif key in (ord('d'), ord('D')):
            self._exit_draw()
            self._do_unsatisfied()
        elif key in (8, 127):
            self._delete_selected()
        elif key in (ord('~'), ord('`')):
            self._undo_last_new()
        elif key in (ord('n'), ord('N')):
            self.cls_input_mode = True
            self.cls_input_text = ""
        elif key in (ord('f'), ord('F')):
            self.viewport.fit_to_screen(self.cur_img)
        elif key in (ord('['), ord('{')):
            self._prev_class()
        elif key in (ord(']'), ord('}')):
            self._next_class()
        elif ord('0') <= key <= ord('9'):
            self._select_class(key - ord('0'))

    # ────────── 统计 ──────────
    def _show_stats(self) -> None:
        ds = self.decisions
        ok = sum(1 for v in ds.values() if v in ("satisfied", "edited_and_satisfied"))
        bad = sum(1 for v in ds.values() if v == "unsatisfied")
        edit = sum(1 for v in ds.values() if v == "edited_and_satisfied")
        print(f"\n  ═══════════ Statistics ═══════════")
        print(f"    Reviewed:    {len(ds)}")
        print(f"    Satisfied:   {ok}")
        print(f"    Unsatisfied: {bad}")
        print(f"    Edited+OK:   {edit}")
        print(f"    Remaining:   {max(0, self.N - self.idx - 1)}")
        print(f"  ══════════════════════════════════\n")

    # ────────── 渲染（委托 renderer）──────────
    def _render(self) -> np.ndarray:
        fname = self.flist[self.idx] if self.idx < self.N else "?"
        tag = self.decisions.get(fname, "---")
        canvas = render_frame(
            self.cur_img,
            self.cur_boxes,
            self.new_px,
            self.cls_names,
            self.viewport,
            dragging_new=self.dragging_new,
            drag_rect=(self.drag_sx, self.drag_sy, self.drag_ex, self.drag_ey),
            sel_idx=self.sel_idx,
            sel_is_new=self.sel_is_new,
        )
        bar = render_hud(
            self.viewport,
            idx=self.idx,
            total=self.N,
            fname=fname,
            n_orig=len(self.cur_boxes),
            n_new=len(self.new_px),
            cur_cls=self.cur_cls,
            cls_names=self.cls_names,
            draw_mode=self.draw_mode,
            decision_tag=tag,
            cls_input_mode=self.cls_input_mode,
            cls_input_text=self.cls_input_text,
        )
        return np.vstack([bar, canvas])

    # ────────── 主循环 ──────────
    def run(self) -> None:
        cv2.namedWindow(self.WIN, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.WIN, min(self.cfg.max_w, 1280), min(self.cfg.max_h, 900))
        cv2.setMouseCallback(self.WIN, self._on_mouse)

        self._load_current()
        self._print_help()

        while self.running:
            if self.cur_img is None:
                if self.idx >= self.N:
                    print("\n[DONE] 所有图片审查完毕！")
                    break
                self.idx += 1
                self._load_current()
                continue

            vis = self._render()
            cv2.imshow(self.WIN, vis)

            key = cv2.waitKey(20) & 0xFF

            if self.cls_input_mode:
                if key not in (0, 255):
                    self._handle_cls_input(key)
                continue

            if key in (0, 255):
                continue

            if self.draw_mode:
                self._handle_draw_key(key)
            else:
                self._handle_review_key(key)

            if self.auto_save_cnt >= 10:
                self._save_progress()
                self.auto_save_cnt = 0

        self._save_progress()
        cv2.destroyAllWindows()
        self._print_final()

    def _print_help(self) -> None:
        print("=" * 60)
        print("  yolo-forge review  |  YOLO Label Review & Patch Tool")
        print("=" * 60)
        print(f"  图片: {self.img_dir}")
        print(f"  标签: {self.lbl_dir}")
        print(f"  输出: {self.out}")
        print(f"  类别: {self.cls_names}")
        print(f"  共 {self.N} 张图片，从第 {self.idx + 1} 张开始")
        print("-" * 60)
        print("  视口: 滚轮=缩放  中键=平移  f=适配全图")
        print("  通用: 点击框=选中  拖拽=移动  右键=取消  BS=删除  0-9/[/]=类别  n=新类别")
        print("  浏览: k=满意  d=不满意  a=补框  j/l=翻页  ~=撤销  i=统计  q=退出")
        print("  补框: 拖拽空白=画框  c/Enter=确认退出  ESC=退出补框")
        print("=" * 60)

    def _print_final(self) -> None:
        ds = self.decisions
        ok = sum(1 for v in ds.values() if v in ("satisfied", "edited_and_satisfied"))
        bad = sum(1 for v in ds.values() if v == "unsatisfied")
        edit = sum(1 for v in ds.values() if v == "edited_and_satisfied")
        print("\n" + "=" * 60)
        print("  完成！最终统计:")
        print(f"    审查总数:    {len(ds)}")
        print(f"    满意:       {ok}")
        print(f"    不满意:     {bad}")
        print(f"    补标后满意:  {edit}")
        print(f"    类别列表:    {self.cls_names}")
        print(f"    输出目录:    {self.cfg.output_dir}")
        print("=" * 60)


def run_reviewer(config: ReviewerConfig) -> None:
    """便捷入口：从配置启动 reviewer."""
    reviewer = YOLOReviewer(config)
    reviewer.run()
