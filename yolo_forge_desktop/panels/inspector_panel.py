"""结构扫描 Panel: 确定性扫描数据集结构, 显示结构化报告."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QTextEdit,
    QVBoxLayout,
)

from .base import BasePanel
from yolo_forge_core.inspector import inspect_dataset


class _InspectWorker(QThread):
    log = Signal(str)
    finished_ok = Signal(str, str)
    failed = Signal(str)

    def __init__(self, path: str, sample_size: int):
        super().__init__()
        self.path = path
        self.sample_size = sample_size

    def run(self) -> None:
        try:
            self.log.emit(f"[*] 扫描中: {self.path}")
            report = inspect_dataset(self.path, sample_size=self.sample_size)
            self.log.emit(
                f"[+] 完成: {len(report.folders)} 个子文件夹, "
                f"{report.total_images} 张图, {report.total_labels} 个标签"
            )
            self.finished_ok.emit(report.to_markdown(), report.to_llm_prompt())
        except Exception as e:
            self.failed.emit(str(e))


class InspectorPanel(BasePanel):
    """数据集结构扫描 Panel."""

    panel_id = "inspector"
    panel_name = "结构扫描"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: _InspectWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        title = QLabel("数据集结构扫描")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("不依赖 LLM，纯确定性扫描任意目录结构，输出报告")
        subtitle.setObjectName("SectionSubtitle")
        layout.addWidget(subtitle)

        hint = QLabel(
            "<b>用法:</b> ① 选数据集根目录 → ② 点「开始扫描」 → "
            "③ 查看下方 Markdown 报告。LLM Prompt 文本可复制给 Structure Agent 使用。"
        )
        hint.setObjectName("PanelHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # 路径选择
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("数据集路径:"))
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("/path/to/dataset_root")
        path_row.addWidget(self.path_edit, 1)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._on_browse)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # sample size
        sample_row = QHBoxLayout()
        sample_row.addWidget(QLabel("每文件夹抽样数:"))
        self.sample_spin = QSpinBox()
        self.sample_spin.setRange(1, 50)
        self.sample_spin.setValue(5)
        sample_row.addWidget(self.sample_spin)
        sample_row.addStretch()
        layout.addLayout(sample_row)

        # 按钮
        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("开始扫描")
        self.run_btn.setObjectName("PrimaryButton")
        self.run_btn.clicked.connect(self._on_run)
        btn_row.addWidget(self.run_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 报告显示
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        md_group = QGroupBox("Markdown 报告（给用户看）")
        mdl = QVBoxLayout(md_group)
        self.markdown_view = QTextEdit()
        self.markdown_view.setObjectName("LogView")
        self.markdown_view.setReadOnly(True)
        self.markdown_view.setPlaceholderText("扫描后显示结构化报告...")
        mdl.addWidget(self.markdown_view)
        splitter.addWidget(md_group)

        llm_group = QGroupBox("LLM Prompt（复制给 Structure Agent）")
        llml = QVBoxLayout(llm_group)
        self.llm_view = QPlainTextEdit()
        self.llm_view.setObjectName("LogView")
        self.llm_view.setReadOnly(True)
        self.llm_view.setPlaceholderText("扫描后显示可喂给 LLM 的紧凑文本...")
        llml.addWidget(self.llm_view)
        splitter.addWidget(llm_group)

        splitter.setSizes([280, 220])
        layout.addWidget(splitter, 1)

    def _on_browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择数据集根目录")
        if path:
            self.path_edit.setText(path)

    def _on_run(self) -> None:
        path = self.path_edit.text().strip()
        if not path or not Path(path).is_dir():
            QMessageBox.warning(self, "路径无效", "请选择有效的数据集目录")
            return

        self.markdown_view.clear()
        self.llm_view.clear()
        self.run_btn.setEnabled(False)

        self._worker = _InspectWorker(path, self.sample_spin.value())
        self._worker.log.connect(lambda s: self.status_message.emit(s))
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_finished(self, markdown: str, llm_prompt: str) -> None:
        self.run_btn.setEnabled(True)
        self.markdown_view.setMarkdown(markdown)
        self.llm_view.setPlainText(llm_prompt)
        self.status_message.emit("扫描完成")

    def _on_failed(self, err: str) -> None:
        self.run_btn.setEnabled(True)
        QMessageBox.critical(self, "失败", f"扫描失败:\n{err}")
