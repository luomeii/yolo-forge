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
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget,
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
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(640, 480)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet("background-color: #020203;")

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
        if hasattr(self.parent(), 'reviewer') and self.parent().reviewer:
            r = self.parent().reviewer
            mx, my = r.viewport.disp_to_img(int(x), int(y), r.cur_img)
            factor = 1.15 if delta > 0 else 1 / 1.15
            r.viewport.zoom_around(mx, my, factor)
            self.parent()._mark_dirty()


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
        try:
            self.reviewer = YOLOReviewer(cfg)
            self.reviewer._load_current()
        except SystemExit:
            QMessageBox.critical(self, "启动失败", "初始化失败，请检查路径和图片数")
            return
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"初始化失败: {e}")
            return

        self.config_widget.hide()
        self.canvas_widget.show()
        self.setFocus()
        self._dirty = True
        # 用 50ms 间隔 (20FPS) 检查 dirty, 不像之前那样 33ms 强制重绘
        self._timer.start(50)

    def _mark_dirty(self) -> None:
        """标记需要重绘."""
        self._dirty = True

    def _refresh_if_dirty(self) -> None:
        """只在 dirty 时重绘, 减少卡顿."""
        if not self._dirty or not self.reviewer or self.reviewer.cur_img is None:
            return
        self._dirty = False
        self._refresh_frame()

    def _refresh_frame(self) -> None:
        try:
            frame = self.reviewer._render()
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
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

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self.reviewer:
            return
        key = event.key()
        char = event.text()

        if char and len(char) == 1 and ord(char) >= 32:
            cv_key = ord(char)
        elif key == Qt.Key_Escape:
            cv_key = 27
        elif key == Qt.Key_Return or key == Qt.Key_Enter:
            cv_key = 13
        elif key == Qt.Key_Backspace:
            cv_key = 8
        elif key == Qt.Key_Delete:
            cv_key = 127
        else:
            return

        if self.reviewer.cls_input_mode:
            self.reviewer._handle_cls_input(cv_key)
            self._mark_dirty()
            return

        if self.reviewer.draw_mode:
            self.reviewer._handle_draw_key(cv_key)
        else:
            self.reviewer._handle_review_key(cv_key)
        self._mark_dirty()

        if not self.reviewer.running:
            self._exit_review()

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
