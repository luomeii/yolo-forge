"""标签审查 Panel: 把 OpenCV 图像画布嵌入 Qt 控件.

v0.2.2 改进:
- 启动后顶部固定操作提示条 (始终可见)
- 「退出审查」按钮返回配置页 (不直接关窗口)
- 定时器从 30FPS 改为按需刷新 (减少卡顿)
- 加 dirty flag, 状态没变就不重绘
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QMouseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from .base import BasePanel
from yolo_forge_core.reviewer.app import YOLOReviewer
from yolo_forge_core.reviewer.config import ReviewerConfig
import cv2
import numpy as np


class _CVCanvas(QLabel):
    """显示 OpenCV numpy 帧的 Qt 控件."""

    mouse_event = Signal(int, int, int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(640, 480)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet("background-color: #020203;")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """把键盘事件直接交给父 panel 处理 (不再转 cv_key)."""
        if self.parent_panel is not None and hasattr(self.parent_panel, "_handle_key"):
            self.parent_panel._handle_key(event)
            # 保持焦点在画布上, 否则下一次按键就丢了
            self.parent_panel.canvas.setFocus()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        x, y = event.position().x(), event.position().y()
        if event.button() == Qt.LeftButton:
            self.mouse_event.emit(cv2.EVENT_LBUTTONDOWN, int(x), int(y), 0, None)
        elif event.button() == Qt.RightButton:
            self.mouse_event.emit(cv2.EVENT_RBUTTONDOWN, int(x), int(y), 0, None)
        elif event.button() == Qt.MiddleButton:
            self.mouse_event.emit(cv2.EVENT_MBUTTONDOWN, int(x), int(y), 0, None)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        x, y = event.position().x(), event.position().y()
        if event.button() == Qt.LeftButton:
            self.mouse_event.emit(cv2.EVENT_LBUTTONUP, int(x), int(y), 0, None)
        elif event.button() == Qt.MiddleButton:
            self.mouse_event.emit(cv2.EVENT_MBUTTONUP, int(x), int(y), 0, None)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        x, y = event.position().x(), event.position().y()
        flags = cv2.EVENT_FLAG_LBUTTON if event.buttons() & Qt.LeftButton else 0
        if event.buttons() & Qt.MiddleButton:
            flags |= cv2.EVENT_FLAG_MBUTTON
        self.mouse_event.emit(cv2.EVENT_MOUSEMOVE, int(x), int(y), flags, None)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        x, y = event.position().x(), event.position().y()
        if self.parent_panel is not None and getattr(self.parent_panel, 'reviewer', None):
            r = self.parent_panel.reviewer
            mx, my = r.viewport.disp_to_img(int(x), int(y), r.cur_img)
            factor = 1.15 if delta > 0 else 1 / 1.15
            r.viewport.zoom_around(mx, my, factor)
            self.parent_panel._mark_dirty()


class ReviewerPanel(BasePanel):
    """标签审查 Panel — Qt 嵌入 OpenCV."""

    panel_id = "reviewer"
    panel_name = "标签审查"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.reviewer: YOLOReviewer | None = None
        self._dirty = True  # 是否需要重绘
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_if_dirty)
        # 用于短暂显示 top_status 后自动隐藏
        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.timeout.connect(self._hide_top_status)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部配置区 (启动前显示)
        self.config_widget = QWidget()
        cl = QVBoxLayout(self.config_widget)
        cl.setContentsMargins(28, 20, 28, 20)
        cl.setSpacing(14)

        title = QLabel("标签审查与补标")
        title.setObjectName("SectionTitle")
        cl.addWidget(title)

        subtitle = QLabel("基于 OpenCV 画布，支持查看 / 补标 / 删除 / 拖动标注框，并归档满意 / 不满意图片")
        subtitle.setObjectName("SectionSubtitle")
        cl.addWidget(subtitle)

        hint = QLabel(
            "<b>工作流:</b> 配置路径 → 进入审查 → 翻页/补标/删除 → 满意归档<br>"
            "<b>核心:</b> 这是你 yolo_review 脚本的 Qt 嵌入版，所有原快捷键都保留"
        )
        hint.setObjectName("PanelHint")
        hint.setWordWrap(True)
        cl.addWidget(hint)

        cfg_group = QGroupBox("审查配置")
        form = QFormLayout(cfg_group)
        form.setSpacing(8)

        self.images_edit = QLineEdit()
        self.images_edit.setPlaceholderText("图片目录路径")
        form.addRow("图片目录:", self.images_edit)

        img_browse = QPushButton("浏览")
        img_browse.clicked.connect(lambda: self._pick_dir(self.images_edit))
        form.addRow("", img_browse)

        self.labels_edit = QLineEdit()
        self.labels_edit.setPlaceholderText("标签目录（YOLO .txt）")
        form.addRow("标签目录:", self.labels_edit)

        lbl_browse = QPushButton("浏览")
        lbl_browse.clicked.connect(lambda: self._pick_dir(self.labels_edit))
        form.addRow("", lbl_browse)

        self.output_edit = QLineEdit("./yolo_forge_output")
        form.addRow("输出目录:", self.output_edit)

        self.classes_edit = QLineEdit("object")
        self.classes_edit.setPlaceholderText("逗号分隔，例如: pit,scratch,car")
        form.addRow("类别列表:", self.classes_edit)

        cl.addWidget(cfg_group)

        self.start_btn = QPushButton("开始审查")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.clicked.connect(self._on_start)
        cl.addWidget(self.start_btn)
        cl.addStretch()

        # 画布区 (启动后显示)
        self.canvas_widget = QWidget()
        cl2 = QVBoxLayout(self.canvas_widget)
        cl2.setContentsMargins(0, 0, 0, 0)
        cl2.setSpacing(0)

        # 操作提示条 (固定在画布上方)
        hint_bar = QLabel(
            "  <b>j/l</b> 翻页 &nbsp;|&nbsp; "
            "<b>k</b> 满意 &nbsp;|&nbsp; "
            "<b>d</b> 不满意 &nbsp;|&nbsp; "
            "<b>a</b> 补框 &nbsp;|&nbsp; "
            "<b>0-9/[/]</b> 切类别 &nbsp;|&nbsp; "
            "<b>n</b> 新类别 &nbsp;|&nbsp; "
            "<b>BS</b> 删框 &nbsp;|&nbsp; "
            "<b>~</b> 撤销 &nbsp;|&nbsp; "
            "<b>滚轮</b> 缩放 &nbsp;|&nbsp; "
            "<b>中键</b> 平移 &nbsp;|&nbsp; "
            "<b>f</b> 适配 &nbsp;|&nbsp; "
            "<b>q/ESC</b> 退出"
        )
        hint_bar.setObjectName("StatusBarHint")
        hint_bar.setTextFormat(Qt.RichText)
        cl2.addWidget(hint_bar)

        # 顶部反馈状态条 (归档/撤销/删框等操作反馈, 默认隐藏)
        self.top_status = QLabel("")
        self.top_status.setObjectName("TopStatusFeedback")
        self.top_status.setStyleSheet(
            "background-color: #1a1a20; color: #10b981; "
            "padding: 4px 14px; font-family: 'JetBrains Mono', monospace; "
            "font-size: 12px; border-bottom: 1px solid rgba(255,255,255,0.05);"
        )
        self.top_status.hide()
        cl2.addWidget(self.top_status)

        # 画布
        self.canvas = _CVCanvas(self)
        self.canvas.mouse_event.connect(self._on_mouse_event)
        cl2.addWidget(self.canvas, 1)

        # 底部状态条 + 退出按钮
        bottom_bar = QWidget()
        bottom_bar.setStyleSheet("background-color: #020203; border-top: 1px solid rgba(255,255,255,0.08);")
        bl = QHBoxLayout(bottom_bar)
        bl.setContentsMargins(14, 6, 14, 6)
        self.status_label = QLabel("未启动")
        self.status_label.setStyleSheet("color: #8A8F98; font-family: 'JetBrains Mono', monospace; font-size: 11px; background: transparent;")
        bl.addWidget(self.status_label, 1)

        exit_btn = QPushButton("退出审查")
        exit_btn.setObjectName("GhostButton")
        exit_btn.clicked.connect(self._exit_review)
        bl.addWidget(exit_btn)
        cl2.addWidget(bottom_bar)

        layout.addWidget(self.config_widget, 1)
        self.canvas_widget.hide()

    def _pick_dir(self, edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择目录")
        if path:
            edit.setText(path)

    def _on_start(self) -> None:
        images = self.images_edit.text().strip()
        labels = self.labels_edit.text().strip()
        if not images or not Path(images).is_dir():
            QMessageBox.warning(self, "缺少路径", "请选择有效的图片目录")
            return
        if not labels:
            QMessageBox.warning(self, "缺少路径", "请填标签目录")
            return

        classes = [c.strip() for c in self.classes_edit.text().split(",") if c.strip()]
        if not classes:
            classes = ["object"]

        cfg = ReviewerConfig(
            image_dir=images,
            label_dir=labels,
            output_dir=self.output_edit.text().strip() or "./yolo_forge_output",
            classes=classes,
        )
        # v0.10.5: 先显示画布, 等 Qt 布局完成后再初始化 reviewer
        self.config_widget.hide()
        self.canvas_widget.show()
        self.canvas.setFocus()

        # 延迟 100ms 等 canvas 显示后取实际尺寸
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._init_reviewer_after_show)

    def _mark_dirty(self) -> None:
        """标记需要重绘."""
        self._dirty = True

    def _init_reviewer_after_show(self) -> None:
        """v0.10.5: canvas 显示后初始化 reviewer, 用 canvas 的实际尺寸."""
        cfg = ReviewerConfig(
            image_dir=self.images_edit.text().strip(),
            label_dir=self.labels_edit.text().strip(),
            output_dir=self.output_edit.text().strip() or "./yolo_forge_output",
            classes=[c.strip() for c in self.classes_edit.text().split(",") if c.strip()] or ["object"],
        )
        try:
            self.reviewer = YOLOReviewer(cfg)
            self.reviewer._load_current()
            # v0.10.5: bar_h=0 + 用 canvas 实际尺寸
            self.reviewer.viewport.bar_h = 0
            self.reviewer.viewport.canvas_w = max(self.canvas.width(), 100)
            self.reviewer.viewport.canvas_h = max(self.canvas.height(), 100)
            if self.reviewer.cur_img is not None:
                self.reviewer.viewport.fit_to_screen(self.reviewer.cur_img)
        except SystemExit:
            QMessageBox.critical(self, "启动失败", "初始化失败，请检查路径和图片数")
            self.canvas_widget.hide()
            self.config_widget.show()
            return
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"初始化失败: {e}")
            self.canvas_widget.hide()
            self.config_widget.show()
            return

        self.canvas.reviewer = self.reviewer
        self.canvas.parent_panel = self
        self._dirty = True
        self._timer.start(50)

    def _refresh_if_dirty(self) -> None:
        """只在 dirty 时重绘, 减少卡顿."""
        if not self._dirty or not self.reviewer or self.reviewer.cur_img is None:
            return
        self._dirty = False
        self._refresh_frame()

    def _refresh_frame(self) -> None:
        try:
            if not self.reviewer or self.reviewer.cur_img is None:
                return
            # v0.10.5: 每帧用 canvas 实际尺寸更新视口
            self.reviewer.viewport.canvas_w = max(self.canvas.width(), 100)
            self.reviewer.viewport.canvas_h = max(self.canvas.height(), 100)
            frame = self.reviewer._render()
            if frame is None:
                return
            h, w = frame.shape[:2]
            if h == 0 or w == 0:
                return
            ch = frame.shape[2] if frame.ndim == 3 else 1
            qimg = QImage(frame.data, w, h, ch * w, QImage.Format_RGB888).rgbSwapped()
            self.canvas.setPixmap(QPixmap.fromImage(qimg))

            r = self.reviewer
            fname = r.flist[r.idx] if r.idx < r.N else "?"
            tag = r.decisions.get(fname, "---")
            mode_str = "补框" if r.draw_mode else "审查"
            cls_name = r.cls_names[r.cur_cls] if r.cur_cls < len(r.cls_names) else "?"
            self.status_label.setText(
                f"[{r.idx + 1}/{r.N}] {fname}  "
                f"原始:{len(r.cur_boxes)} 新增:{len(r.new_px)}  "
                f"当前类:{r.cur_cls}:{cls_name}  [{mode_str}]  {tag}"
            )
        except Exception as e:
            self.status_label.setText(f"渲染错误: {e}")

    def _on_mouse_event(self, event: int, x: int, y: int, flags: int, param) -> None:
        if self.reviewer:
            self.reviewer._on_mouse(event, x, y, flags, param)
            self._mark_dirty()

    def _handle_key(self, event: QKeyEvent) -> None:
        """直接用 Qt.Key 处理键盘事件 (不再转 cv_key).

        映射规则 (参考 reviewer 原生 OpenCV 版):
        - a/c: 切换补框模式 (在补框中→退出, 不在→进入)
        - j/Left 上一张, l/Right 下一张 (补框中先退出补框)
        - k: 归档为满意
        - d: 归档为不满意
        - 0-9: 切类别
        - [/]: 上/下一类别
        - n: 弹 QInputDialog 添加新类别
        - ~/`/Ctrl+Z: 撤销最后一个新框
        - Backspace/Delete: 删除选中框
        - f: 适配全图
        - q: 退出审查
        - ESC: 补框中→退出补框, 否则退出审查
        - i: 显示统计
        - R: 重置到第一张
        """
        if not self.reviewer:
            return
        r = self.reviewer
        if r.cur_img is None:
            return

        key = event.key()
        modifiers = event.modifiers()
        text = event.text()

        # 优先处理: Ctrl+Z 撤销 (与 ~ / ` 等价)
        if (modifiers & Qt.ControlModifier) and key == Qt.Key_Z:
            r._undo_last_new()
            self._show_archive_feedback(
                f"[UNDO] 撤销最后一个新增框 (剩 {len(r.new_px)} 个)"
            )
            self._mark_dirty()
            return

        # ── a/c: 切换补框模式 ──
        if key in (Qt.Key_A, Qt.Key_C):
            if r.draw_mode:
                r._exit_draw()
                self._show_archive_feedback("[DRAW] 已退出补框模式")
            else:
                r._enter_draw()
                self._show_archive_feedback("[DRAW] 进入补框模式 | 拖拽空白=画框")
            self._mark_dirty()
            return

        # ── 翻页 (j/Left 上一张, l/Right 下一张) ──
        if key in (Qt.Key_J, Qt.Key_Left):
            if r.draw_mode:
                r._exit_draw()
            if r.idx > 0:
                r.idx -= 1
                r._load_current()
                self._show_archive_feedback(f"[<] 上一张  ({r.idx + 1}/{r.N})")
            else:
                self._show_archive_feedback("[<] 已是第一张")
            self._mark_dirty()
            return
        if key in (Qt.Key_L, Qt.Key_Right):
            if r.draw_mode:
                r._exit_draw()
            # v0.10.6: 检查是否是最后一张
            if r.idx >= r.N - 1:
                # 最后一张, 审查完毕
                self._show_archive_feedback("[DONE] 所有图片审查完毕！")
                r.running = False
                self._exit_review()
                return
            fname = r.flist[r.idx]
            r.decisions[fname] = "skipped"
            r._go_next()
            self._show_archive_feedback(f"[>] 跳过 → 下一张  ({r.idx + 1}/{r.N})")
            self._mark_dirty()
            return

        # ── k: 归档为满意 ──
        if key == Qt.Key_K:
            if r.draw_mode:
                r._exit_draw()
            fname = r.flist[r.idx]
            tag = "EDIT+OK" if r.new_px else "OK"
            ba = f" +{len(r.new_px)}box" if r.new_px else ""
            r._do_satisfied()
            self._show_archive_feedback(f"[{tag}] {fname} → satisfied/{ba}")
            self._mark_dirty()
            return

        # ── d: 归档为不满意 ──
        if key == Qt.Key_D:
            if r.draw_mode:
                r._exit_draw()
            fname = r.flist[r.idx]
            r._do_unsatisfied()
            self._show_archive_feedback(f"[BAD] {fname} → unsatisfied/")
            self._mark_dirty()
            return

        # ── 0-9: 切类别 ──
        if Qt.Key_0 <= key <= Qt.Key_9:
            cid = key - Qt.Key_0
            r._select_class(cid)
            cls_name = r.cls_names[cid] if cid < len(r.cls_names) else f"cls{cid}"
            self._show_archive_feedback(f"[CLS] → {cid}:{cls_name}")
            self._mark_dirty()
            return

        # ── [ / ]: 上一/下一类别 ──
        if key == Qt.Key_BracketLeft:
            r._prev_class()
            cls_name = r.cls_names[r.cur_cls] if r.cur_cls < len(r.cls_names) else "?"
            self._show_archive_feedback(f"[CLS] ← {r.cur_cls}:{cls_name}")
            self._mark_dirty()
            return
        if key == Qt.Key_BracketRight:
            r._next_class()
            cls_name = r.cls_names[r.cur_cls] if r.cur_cls < len(r.cls_names) else "?"
            self._show_archive_feedback(f"[CLS] → {r.cur_cls}:{cls_name}")
            self._mark_dirty()
            return

        # ── n: 添加新类别 (QInputDialog) ──
        if key == Qt.Key_N:
            name, ok = QInputDialog.getText(
                self, "添加新类别", "类别名称:", text=""
            )
            if ok and name.strip():
                name = name.strip()
                if name in r.cls_names:
                    new_id = r.cls_names.index(name)
                    r.cur_cls = new_id
                    self._show_archive_feedback(
                        f"[CLS] 类别 '{name}' 已存在 (id={new_id}), 已切换"
                    )
                else:
                    r.cls_names.append(name)
                    new_id = len(r.cls_names) - 1
                    r.cur_cls = new_id
                    self._show_archive_feedback(
                        f"[CLS] 已添加类别: {new_id}:{name}"
                    )
            else:
                self._show_archive_feedback("[CLS] 已取消添加类别")
            self._mark_dirty()
            return

        # ── ~ / `: 撤销最后一个新框 ──
        if key == Qt.Key_AsciiTilde or key == Qt.Key_QuoteLeft or text in ("~", "`"):
            before = len(r.new_px)
            r._undo_last_new()
            after = len(r.new_px)
            if before > after:
                self._show_archive_feedback(
                    f"[UNDO] 撤销最后一个新增框 (剩 {after} 个)"
                )
            else:
                self._show_archive_feedback("[UNDO] 无新增框可撤销")
            self._mark_dirty()
            return

        # ── Backspace / Delete: 删除选中框 ──
        if key == Qt.Key_Backspace or key == Qt.Key_Delete:
            if r.sel_idx < 0:
                self._show_archive_feedback("[DEL] 没有选中的框")
            else:
                r._delete_selected()
                self._show_archive_feedback("[DEL] 已删除选中框")
            self._mark_dirty()
            return

        # ── f: 适配全图 ──
        if key == Qt.Key_F:
            r.viewport.fit_to_screen(r.cur_img)
            self._show_archive_feedback("[FIT] 已适配全图")
            self._mark_dirty()
            return

        # ── q: 退出审查 ──
        if key == Qt.Key_Q:
            self._exit_review()
            return

        # ── ESC: 补框中→退出补框, 否则退出审查 ──
        if key == Qt.Key_Escape:
            if r.draw_mode:
                r._exit_draw()
                self._show_archive_feedback("[ESC] 已退出补框模式")
                self._mark_dirty()
            else:
                self._exit_review()
            return

        # ── i: 显示统计 ──
        if key == Qt.Key_I:
            r._show_stats()
            ds = r.decisions
            ok = sum(1 for v in ds.values() if v in ("satisfied", "edited_and_satisfied"))
            bad = sum(1 for v in ds.values() if v == "unsatisfied")
            edit = sum(1 for v in ds.values() if v == "edited_and_satisfied")
            self._show_archive_feedback(
                f"[STATS] 已审 {len(ds)} | 满意 {ok} | 不满意 {bad} | 补标+满意 {edit} | 剩 {max(0, r.N - r.idx - 1)}"
            )
            self._mark_dirty()
            return

        # ── R: 重置到第一张 ──
        if key == Qt.Key_R:
            if r.draw_mode:
                r._exit_draw()
            r.idx = 0
            r._load_current()
            self._show_archive_feedback("[RESET] 已重置到第 1 张")
            self._mark_dirty()
            return

        # 未识别的按键交给父类处理
        super().keyPressEvent(event)

    def _show_archive_feedback(self, msg: str) -> None:
        """在 top_status 标签上显示一条反馈信息 (3 秒后自动隐藏)."""
        if not hasattr(self, "top_status"):
            return
        self.top_status.setText("  " + msg)
        self.top_status.show()
        # 重启自动隐藏计时器
        if self._feedback_timer.isActive():
            self._feedback_timer.stop()
        self._feedback_timer.start(3000)

    def _hide_top_status(self) -> None:
        if hasattr(self, "top_status"):
            self.top_status.hide()

    def showEvent(self, event) -> None:
        """panel 被切到显示时, 启动刷新定时器."""
        super().showEvent(event)
        if self.reviewer is not None and not self._timer.isActive():
            self._timer.start(50)
        # 确保画布拿到焦点, 否则键盘事件不响应
        if hasattr(self, "canvas") and self.canvas.isVisible():
            self.canvas.setFocus()

    def hideEvent(self, event) -> None:
        """v0.10.3: panel 被隐藏时退出审查, 确保下次显示时恢复正常."""
        super().hideEvent(event)
        if self._timer.isActive():
            self._timer.stop()
        if self._feedback_timer.isActive():
            self._feedback_timer.stop()
        # 如果正在审查, 保存进度并退出
        if self.reviewer and self.reviewer.running:
            try:
                self.reviewer._save_progress()
            except Exception:
                pass
            self.reviewer.running = False
            self.canvas.reviewer = None

    def showEvent(self, event) -> None:
        """v0.10.3: panel 重新显示时, 如果不在审查中, 确保配置页可见."""
        super().showEvent(event)
        if not self.reviewer or not self.reviewer.running:
            if not self.config_widget.isVisible():
                self.canvas_widget.hide()
                self.config_widget.show()

    def _exit_review(self) -> None:
        """退出审查, 返回配置页 (不关窗口)."""
        self._timer.stop()
        if self.reviewer:
            try:
                self.reviewer._save_progress()
            except Exception:
                pass
        self.canvas_widget.hide()
        self.config_widget.show()
        self.status_message.emit("已退出审查，进度已保存")

    def on_deactivated(self) -> None:
        """切到其他面板时暂停定时器."""
        self._timer.stop()
