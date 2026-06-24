"""数据转换 Panel — QGridLayout 严格分列布局.

v0.3.2 改进:
- 用 QGridLayout 强制标签列 + 输入框列分列, 不再重叠
- 去掉所有 emoji
- placeholder 精简
- 「从 Agent 导入」按钮独立一行, 不挤压其他控件
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QSplitter, QTextEdit, QVBoxLayout,
)

from .base import BasePanel
from yolo_forge_core.converter.builtins import list_builtin_templates, get_builtin_template
from yolo_forge_core.converter.engine import convert_dataset
from yolo_forge_core.converter.profiles import DatasetProfile


TEMPLATE_DESCRIPTIONS = {
    "multi_folder_mixed": (
        "多文件夹混合数据集（旗舰示例）\n\n"
        "适用场景:\n"
        "  - 6 个子文件夹、部分有标注部分纯背景\n"
        "  - class id 含义需统一\n\n"
        "典型用例: 你那份 face/line/syn/oil/no_defect/background 数据集"
    ),
    "single_folder": (
        "单文件夹 YOLO 数据集\n\n"
        "适用场景:\n"
        "  - 已经是 YOLO 格式但还没切分 train/val\n\n"
        "动作: 自动按 80/20 切分到 images/train 和 images/val"
    ),
    "voc_to_yolo": (
        "Pascal VOC → YOLO\n\n"
        "适用场景:\n"
        "  - 标签是 .xml 格式\n\n"
        "注意: VOC 按类别名匹配, 需要列出所有 <name> 字段的值"
    ),
    "coco_to_yolo": (
        "COCO JSON → YOLO\n\n"
        "适用场景:\n"
        "  - 所有标注在单个 instances.json 里\n\n"
        "注意: 需要 images_subdir 指向图片文件夹, coco_json 指向 JSON 文件"
    ),
    "raw_px_to_yolo": (
        "绝对像素坐标 → YOLO 归一化\n\n"
        "适用场景:\n"
        "  - .txt 是 class_id x1 y1 x2 y2 像素值（不是归一化）\n\n"
        "动作: 引擎用实际图片尺寸自动归一化"
    ),
}


class _ConvertWorker(QThread):
    log = Signal(str)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, profile: DatasetProfile, dry_run: bool = False):
        super().__init__()
        self.profile = profile
        self.dry_run = dry_run

    def run(self) -> None:
        try:
            self.log.emit("[*] 开始转换 ...")
            report = convert_dataset(self.profile, dry_run=self.dry_run)
            self.log.emit("[+] 转换完成")
            self.finished_ok.emit(report)
        except Exception as e:
            import traceback
            self.log.emit(f"[x] 失败: {e}")
            self.log.emit(traceback.format_exc())
            self.failed.emit(str(e))


class ConverterPanel(BasePanel):
    """数据转换 Panel."""

    panel_id = "converter"
    panel_name = "数据转换"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: _ConvertWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(14)

        # ── 标题区 ──
        title = QLabel("数据转换")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("把异构数据集（多文件夹、不同标签格式）一键转换为标准 YOLO 训练布局")
        subtitle.setObjectName("SectionSubtitle")
        layout.addWidget(subtitle)

        hint = QLabel(
            "<b>三种使用方式:</b><br>"
            "① <b>Agent 模式（推荐）</b>: 右侧 Agent 对话发「分析 + 路径」，生成 profile 后回来点「从 Agent 导入」<br>"
            "② <b>模板模式</b>: 选一个内置模板，自动导出 YAML 到本地，编辑后跑<br>"
            "③ <b>文件模式</b>: 已有 profile YAML 文件，直接选文件跑"
        )
        hint.setObjectName("PanelHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # ── Agent 一键应用 (独立一行, 突出显示) ──
        agent_row = QHBoxLayout()
        self.import_agent_btn = QPushButton("从 Agent 导入 Profile")
        self.import_agent_btn.setObjectName("SuccessButton")
        self.import_agent_btn.setMinimumWidth(200)
        self.import_agent_btn.setToolTip("把右侧 Structure Agent 刚生成的 profile YAML 应用到这里")
        self.import_agent_btn.clicked.connect(self._on_import_from_agent)
        agent_row.addWidget(self.import_agent_btn)

        self.import_status = QLabel("")
        self.import_status.setObjectName("Hint")
        agent_row.addWidget(self.import_status, 1)
        layout.addLayout(agent_row)

        # ── profile 选择组 (QGridLayout 严格分列) ──
        profile_group = QGroupBox("Profile 来源")
        gl = QGridLayout(profile_group)
        gl.setHorizontalSpacing(12)
        gl.setVerticalSpacing(10)
        gl.setColumnMinimumWidth(0, 90)    # 标签列最小宽
        gl.setColumnMinimumWidth(1, 280)   # 输入框列最小宽 (v0.10.3)
        gl.setColumnStretch(1, 1)          # 输入框列拉伸
        gl.setColumnStretch(2, 0)          # 按钮列不拉伸

        # 第 0 行: 文件路径
        file_label = QLabel("文件路径:")
        file_label.setObjectName("FieldLabel")
        gl.addWidget(file_label, 0, 0)
        self.profile_path_edit = QLineEdit()
        self.profile_path_edit.setPlaceholderText("选择已有 profile YAML")
        gl.addWidget(self.profile_path_edit, 0, 1)
        browse_btn = QPushButton("浏览")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._on_browse_profile)
        gl.addWidget(browse_btn, 0, 2)

        # 第 1 行: 模板选择
        tpl_label = QLabel("或选模板:")
        tpl_label.setObjectName("FieldLabel")
        gl.addWidget(tpl_label, 1, 0)
        self.template_combo = QComboBox()
        self.template_combo.addItem("(不使用)", "")
        for name in list_builtin_templates():
            self.template_combo.addItem(name, name)
        self.template_combo.currentIndexChanged.connect(self._on_template_selected)
        gl.addWidget(self.template_combo, 1, 1)
        tpl_info_btn = QPushButton("?")
        tpl_info_btn.setFixedWidth(32)
        tpl_info_btn.setToolTip("显示当前模板的说明")
        tpl_info_btn.clicked.connect(self._show_template_info)
        gl.addWidget(tpl_info_btn, 1, 2)

        # 第 2 行: YAML 编辑器标签 (跨 3 列)
        yaml_label = QLabel("YAML 内容（可直接编辑）:")
        yaml_label.setObjectName("FieldLabel")
        gl.addWidget(yaml_label, 2, 0, 1, 3)

        # 第 3 行: YAML 编辑器 (跨 3 列)
        self.yaml_edit = QPlainTextEdit()
        self.yaml_edit.setObjectName("LogView")
        self.yaml_edit.setPlaceholderText("YAML 内容会在这里显示。可以从 Agent 导入、从模板生成、或手动编辑。")
        self.yaml_edit.setMinimumHeight(180)
        gl.addWidget(self.yaml_edit, 3, 0, 1, 3)

        layout.addWidget(profile_group)

        # ── 输出目录 (QHBoxLayout 简单布局) ──
        out_row = QHBoxLayout()
        out_label = QLabel("输出目录:")
        out_label.setObjectName("FieldLabel")
        out_label.setFixedWidth(90)
        out_row.addWidget(out_label)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("不填则用 profile 里的默认值")
        out_row.addWidget(self.output_edit, 1)
        layout.addLayout(out_row)

        # ── 操作按钮 (统一对齐) ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.dry_run_btn = QPushButton("试运行")
        self.dry_run_btn.setFixedWidth(100)
        self.dry_run_btn.setToolTip("只扫描不写文件，验证 profile 配置正确性")
        self.dry_run_btn.clicked.connect(lambda: self._start_convert(dry_run=True))
        btn_row.addWidget(self.dry_run_btn)

        self.run_btn = QPushButton("开始转换")
        self.run_btn.setObjectName("PrimaryButton")
        self.run_btn.setFixedWidth(120)
        self.run_btn.clicked.connect(lambda: self._start_convert(dry_run=False))
        btn_row.addWidget(self.run_btn)

        btn_row.addStretch()

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setFixedWidth(80)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setObjectName("DangerButton")
        self.stop_btn.clicked.connect(self._on_stop)
        btn_row.addWidget(self.stop_btn)

        layout.addLayout(btn_row)

        # ── 进度条 ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("就绪")
        layout.addWidget(self.progress_bar)

        # ── 日志 + 报告 ──
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("运行后显示详细日志...")
        log_layout.addWidget(self.log_view)
        splitter.addWidget(log_group)

        report_group = QGroupBox("转换报告")
        report_layout = QVBoxLayout(report_group)
        self.report_view = QTextEdit()
        self.report_view.setObjectName("LogView")
        self.report_view.setReadOnly(True)
        self.report_view.setPlaceholderText("转换完成后显示统计报告...")
        report_layout.addWidget(self.report_view)
        splitter.addWidget(report_group)

        splitter.setSizes([240, 200])
        layout.addWidget(splitter, 1)

    # ────────── 事件 ──────────
    def _on_import_from_agent(self) -> None:
        main_window = self.window()
        yaml_text = getattr(main_window, "_pending_profile_yaml", "")
        if not yaml_text:
            self.import_status.setText("Agent 还没生成 profile，请先在右侧发「分析 + 路径」")
            return
        self.yaml_edit.setPlainText(yaml_text)
        self.import_status.setText("已导入 Agent 生成的 profile，可点「开始转换」")
        self.log_view.appendPlainText("[+] 已从 Agent 导入 profile YAML")
        self.status_message.emit("已导入 Agent profile")

    def _on_browse_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Profile YAML 文件", "", "YAML (*.yaml *.yml);;所有文件 (*)"
        )
        if path:
            self.profile_path_edit.setText(path)
            try:
                content = Path(path).read_text(encoding="utf-8")
                self.yaml_edit.setPlainText(content)
                self.log_view.appendPlainText(f"[i] 已加载: {path}")
            except Exception as e:
                QMessageBox.warning(self, "读取失败", f"读文件失败: {e}")

    def _on_template_selected(self, idx: int) -> None:
        name = self.template_combo.itemData(idx)
        if not name:
            return
        yaml_text = get_builtin_template(name)
        templates_dir = Path.home() / ".yolo-forge" / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)
        out_path = templates_dir / f"{name}.yaml"
        out_path.write_text(yaml_text, encoding="utf-8")
        self.profile_path_edit.setText(str(out_path))
        self.yaml_edit.setPlainText(yaml_text)
        self.log_view.appendPlainText(f"[i] 已导出模板「{name}」到: {out_path}")
        self.log_view.appendPlainText("[i] 请编辑 path / output_dir 等字段后再点「开始转换」")

    def _show_template_info(self) -> None:
        name = self.template_combo.currentData()
        if not name:
            QMessageBox.information(self, "模板说明", "请先在「或选模板」下拉框选择一个模板。")
            return
        desc = TEMPLATE_DESCRIPTIONS.get(name, "暂无说明")
        QMessageBox.information(self, f"模板: {name}", desc)

    def _start_convert(self, *, dry_run: bool) -> None:
        yaml_text = self.yaml_edit.toPlainText().strip()
        profile_path = self.profile_path_edit.text().strip()

        try:
            if yaml_text:
                import yaml
                profile_dict = yaml.safe_load(yaml_text)
                profile = DatasetProfile.from_dict(profile_dict)
            elif profile_path and Path(profile_path).is_file():
                profile = DatasetProfile.from_yaml(profile_path)
            else:
                QMessageBox.warning(self, "缺少配置", "请先从 Agent 导入、选模板、或选 profile 文件")
                return
        except Exception as e:
            QMessageBox.critical(self, "Profile 无效", f"解析 YAML 失败:\n{e}")
            return

        if self.output_edit.text().strip():
            profile.output_dir = self.output_edit.text().strip()

        self.log_view.clear()
        self.report_view.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("转换中...")
        self.run_btn.setEnabled(False)
        self.dry_run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self._worker = _ConvertWorker(profile, dry_run=dry_run)
        self._worker.log.connect(self._on_log)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_stop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(2000)
        self._reset_buttons()
        self.log_view.appendPlainText("[!] 已强制停止（可能产生半成品输出）")
        self.progress_bar.setFormat("已停止")

    def _reset_buttons(self) -> None:
        self.run_btn.setEnabled(True)
        self.dry_run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_log(self, msg: str) -> None:
        self.log_view.appendPlainText(msg)

    def _on_finished(self, report) -> None:
        self._reset_buttons()
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("完成")
        html = self._render_report_html(report)
        self.report_view.setHtml(html)
        self.status_message.emit(
            f"转换完成: 训练集 {report.train_count} / 验证集 {report.val_count}"
        )
        self.agent_message.emit("assistant",
            f"转换完成\n"
            f"输出目录: {report.output_dir}\n"
            f"训练/验证/测试: {report.train_count}/{report.val_count}/{report.test_count}\n"
            f"总标注框: {report.total_boxes}\n\n"
            f"下一步: 切到「模型训练」面板，把 {report.output_dir}/data.yaml 填进去开始训练。"
        )

    def _on_failed(self, err: str) -> None:
        self._reset_buttons()
        self.progress_bar.setFormat("失败")
        self.status_message.emit(f"转换失败: {err}")
        QMessageBox.critical(self, "失败", f"转换失败:\n{err}")

    def _render_report_html(self, report) -> str:
        rows = []
        for s in report.sources:
            dist = ", ".join(f"类{k}:{v}" for k, v in sorted(s.class_distribution.items())) or "—"
            rows.append(
                f"<tr><td>{s.name}</td><td>{s.total_images}</td>"
                f"<td>{s.converted}</td><td>{s.skipped}</td><td>{s.errors}</td>"
                f"<td>{s.total_boxes}</td><td>{dist}</td></tr>"
            )
        rows_html = "\n".join(rows)

        return f"""
        <html><body style="color:#EDEDEF; font-family: 'PingFang SC', sans-serif; font-size: 12px;">
        <h3 style="color:#5E6AD2; margin: 4px 0; font-size: 14px;">{report.profile_name}</h3>
        <p style="color:#8A8F98; margin: 4px 0;">输出: <code style="background:#0a0a0c; padding:2px 6px; border-radius:4px;">{report.output_dir}</code></p>
        <table border="1" cellpadding="6" cellspacing="0"
               style="border-color:rgba(255,255,255,0.08); border-collapse: collapse; margin-top:8px; width: 100%;">
        <tr style="background:#0a0a0c; color:#EDEDEF; font-weight:600;">
            <th>源</th><th>图片数</th><th>已转</th><th>跳过</th>
            <th>错误</th><th>框数</th><th>类别分布</th>
        </tr>
        {rows_html}
        </table>
        <p style="margin-top:10px; color:#8A8F98;">
          训练/验证/测试: <b style="color:#EDEDEF;">{report.train_count}/{report.val_count}/{report.test_count}</b>
          &nbsp;|&nbsp; 耗时: {report.elapsed_seconds:.2f}s
        </p>
        </body></html>
        """
