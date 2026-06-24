"""模型训练 Panel — QGridLayout 严格分列布局.

v0.3.2 改进:
- 用 QGridLayout 强制标签列固定宽度 + 输入框列拉伸
- 所有字段 tooltip 详细说明, 但 placeholder 精简
- 去掉所有 emoji
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QSpinBox, QSplitter, QTextEdit, QVBoxLayout,
)

from .base import BasePanel
from yolo_forge_core.trainer import TrainCallbacks, TrainConfig, Trainer


class _TrainWorker(QThread):
    log = Signal(str)
    progress = Signal(float, str)
    metrics = Signal(dict)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, config: TrainConfig):
        super().__init__()
        self.config = config
        self._trainer: Trainer | None = None

    def run(self) -> None:
        cbs = TrainCallbacks(
            on_log=lambda s: self.log.emit(s),
            on_progress=lambda p, s: self.progress.emit(p, s),
            on_metrics=lambda m: self.metrics.emit(m),
            on_complete=lambda p: self.finished_ok.emit(p),
            on_error=lambda e: self.failed.emit(e),
        )
        self._trainer = Trainer(self.config, cbs)
        self._trainer.start()
        if self._trainer._thread:
            self._trainer._thread.join()

    def stop(self) -> None:
        if self._trainer:
            self._trainer.stop()


class TrainerPanel(BasePanel):
    """训练 Panel."""

    panel_id = "trainer"
    panel_name = "模型训练"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: _TrainWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(14)

        title = QLabel("YOLO 模型训练")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("基于 Ultralytics 原生训练。训练在子进程跑，不阻塞界面")
        subtitle.setObjectName("SectionSubtitle")
        layout.addWidget(subtitle)

        hint = QLabel(
            "<b>用法:</b> ① 选 data.yaml（用「数据转换」面板生成的那个） → "
            "② 调整超参 → ③ 点「开始训练」 → ④ 训练完点「生成报告」让 Agent 自动分析。<br>"
            "<b>提示:</b> 也可以直接在右侧对话框发「训练 + data.yaml 路径」让 Agent 自动跑+分析"
        )
        hint.setObjectName("PanelHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # ── 训练配置组 (QGridLayout) ──
        cfg_group = QGroupBox("训练配置")
        form = QGridLayout(cfg_group)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setColumnMinimumWidth(0, 110)   # 标签列固定宽
        form.setColumnStretch(1, 1)          # 输入框列拉伸

        row = 0

        # data.yaml
        lbl = QLabel("data.yaml:")
        lbl.setObjectName("FieldLabel")
        form.addWidget(lbl, row, 0)
        self.data_edit = QLineEdit()
        self.data_edit.setPlaceholderText("data.yaml 路径")
        self.data_edit.setToolTip(
            "Ultralytics data.yaml 文件路径。\n\n"
            "通常由「数据转换」面板生成, 位于输出目录下。\n\n"
            "内容示例:\n"
            "  path: /your/output_dir\n"
            "  train: images/train\n"
            "  val: images/val\n"
            "  names:\n"
            "    0: class_name"
        )
        form.addWidget(self.data_edit, row, 1)
        data_browse = QPushButton("浏览")
        data_browse.setFixedWidth(80)
        data_browse.clicked.connect(self._on_browse_data)
        form.addWidget(data_browse, row, 2)
        row += 1

        # 预训练模型
        lbl = QLabel("预训练模型:")
        lbl.setObjectName("FieldLabel")
        form.addWidget(lbl, row, 0)
        self.model_edit = QLineEdit("yolo11n.pt")
        self.model_edit.setToolTip(
            "预训练模型权重。\n\n"
            "可选:\n"
            "  yolo11n.pt  - nano, 最快, 精度最低\n"
            "  yolo11s.pt  - small\n"
            "  yolo11m.pt  - medium\n"
            "  yolo11l.pt  - large\n"
            "  yolo11x.pt  - extra large, 最慢, 精度最高\n\n"
            "首次使用会自动从 Ultralytics 下载。"
        )
        form.addWidget(self.model_edit, row, 1)
        row += 1

        # 训练轮数
        lbl = QLabel("训练轮数:")
        lbl.setObjectName("FieldLabel")
        form.addWidget(lbl, row, 0)
        self.epochs_spin = QSpinBox()
        self.epochs_spin.setRange(1, 10000)
        self.epochs_spin.setValue(100)
        self.epochs_spin.setToolTip(
            "训练轮数 (epochs)。\n\n"
            "小数据集 (几百张): 50-100 足够\n"
            "中等数据集 (几千张): 100-300\n"
            "大数据集 (几万张+): 300-500\n\n"
            "配合早停 (patience) 使用, 过拟合会自动停。"
        )
        form.addWidget(self.epochs_spin, row, 1)
        row += 1

        # 图像尺寸
        lbl = QLabel("图像尺寸:")
        lbl.setObjectName("FieldLabel")
        form.addWidget(lbl, row, 0)
        self.imgsz_spin = QSpinBox()
        self.imgsz_spin.setRange(64, 4096)
        self.imgsz_spin.setSingleStep(32)
        self.imgsz_spin.setValue(640)
        self.imgsz_spin.setToolTip(
            "训练图像尺寸 (像素)。\n\n"
            "小目标多: 用 640 或 832\n"
            "大目标多: 512 也够\n"
            "越大越准但越慢, 显存占用越高"
        )
        form.addWidget(self.imgsz_spin, row, 1)
        row += 1

        # 批大小
        lbl = QLabel("批大小:")
        lbl.setObjectName("FieldLabel")
        form.addWidget(lbl, row, 0)
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 1024)
        self.batch_spin.setValue(16)
        self.batch_spin.setToolTip(
            "batch size。\n\n"
            "GPU 显存 8GB: batch=8-16\n"
            "GPU 显存 16GB+: batch=16-32\n"
            "CPU 训练: batch=4-8\n\n"
            "OOM 时调小, 不够用时调大。"
        )
        form.addWidget(self.batch_spin, row, 1)
        row += 1

        # 设备
        lbl = QLabel("设备:")
        lbl.setObjectName("FieldLabel")
        form.addWidget(lbl, row, 0)
        self.device_edit = QLineEdit()
        self.device_edit.setPlaceholderText("空=自动")
        self.device_edit.setToolTip(
            "训练设备。\n\n"
            "空: 自动选 GPU\n"
            "0: 用第 0 号 GPU\n"
            "0,1: 多卡训练\n"
            "cpu: 强制 CPU (慢)"
        )
        form.addWidget(self.device_edit, row, 1)
        row += 1

        # 数据加载进程
        lbl = QLabel("数据加载进程:")
        lbl.setObjectName("FieldLabel")
        form.addWidget(lbl, row, 0)
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 64)
        self.workers_spin.setValue(4)
        self.workers_spin.setToolTip(
            "数据加载进程数。\n\n"
            "SSD: 4-8\n"
            "HDD: 2-4\n"
            "网络存储: 1-2\n\n"
            "太多反而慢 (竞争 CPU)"
        )
        form.addWidget(self.workers_spin, row, 1)
        row += 1

        # 输出项目
        lbl = QLabel("输出项目:")
        lbl.setObjectName("FieldLabel")
        form.addWidget(lbl, row, 0)
        self.project_edit = QLineEdit("./runs")
        self.project_edit.setToolTip("训练输出根目录, Ultralytics 会在其下创建 name 子目录")
        form.addWidget(self.project_edit, row, 1)
        row += 1

        # 实验名
        lbl = QLabel("实验名:")
        lbl.setObjectName("FieldLabel")
        form.addWidget(lbl, row, 0)
        self.name_edit = QLineEdit("exp")
        self.name_edit.setToolTip("本次实验名, 输出会保存到 project/name/")
        form.addWidget(self.name_edit, row, 1)

        layout.addWidget(cfg_group)

        # ── 按钮行 ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.run_btn = QPushButton("开始训练")
        self.run_btn.setObjectName("PrimaryButton")
        self.run_btn.setFixedWidth(120)
        self.run_btn.setToolTip("启动训练。会自动调用 Ultralytics 在子进程跑")
        self.run_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self.run_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("DangerButton")
        self.stop_btn.setFixedWidth(80)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setToolTip("强制停止训练 (会产生半成品 weights)")
        self.stop_btn.clicked.connect(self._on_stop)
        btn_row.addWidget(self.stop_btn)

        btn_row.addStretch()

        self.report_btn = QPushButton("生成报告 (Agent)")
        self.report_btn.setFixedWidth(160)
        self.report_btn.setEnabled(False)
        self.report_btn.setToolTip("训练完成后, 让 Report Agent 自动读 results.csv + 混淆矩阵, 写 markdown 分析")
        self.report_btn.clicked.connect(self._on_generate_report)
        btn_row.addWidget(self.report_btn)

        layout.addLayout(btn_row)

        # ── 进度条 ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFormat("就绪")
        layout.addWidget(self.progress_bar)

        # ── 日志 + 指标 ──
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        log_group = QGroupBox("训练日志")
        ll = QVBoxLayout(log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("训练开始后显示实时日志...")
        ll.addWidget(self.log_view)
        splitter.addWidget(log_group)

        metrics_group = QGroupBox("最新指标")
        ml = QVBoxLayout(metrics_group)
        self.metrics_view = QTextEdit()
        self.metrics_view.setObjectName("LogView")
        self.metrics_view.setReadOnly(True)
        self.metrics_view.setPlaceholderText("训练过程中显示解析出的指标...")
        ml.addWidget(self.metrics_view)
        splitter.addWidget(metrics_group)

        splitter.setSizes([350, 150])
        layout.addWidget(splitter, 1)

    # ────────── 事件 ──────────
    def _on_browse_data(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 data.yaml", "", "YAML (*.yaml *.yml)"
        )
        if path:
            self.data_edit.setText(path)

    def _on_start(self) -> None:
        data_yaml = self.data_edit.text().strip()
        if not data_yaml or not Path(data_yaml).is_file():
            QMessageBox.warning(self, "缺少文件", "请选择有效的 data.yaml")
            return

        cfg = TrainConfig(
            data_yaml=data_yaml,
            model=self.model_edit.text().strip() or "yolo11n.pt",
            epochs=self.epochs_spin.value(),
            imgsz=self.imgsz_spin.value(),
            batch=self.batch_spin.value(),
            device=self.device_edit.text().strip(),
            workers=self.workers_spin.value(),
            project=self.project_edit.text().strip() or "./runs",
            name=self.name_edit.text().strip() or "exp",
        )

        self.log_view.clear()
        self.metrics_view.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("训练中...")
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.report_btn.setEnabled(False)

        self._worker = _TrainWorker(cfg)
        self._worker.log.connect(self._on_log)
        self._worker.progress.connect(self._on_progress)
        self._worker.metrics.connect(self._on_metrics)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_stop(self) -> None:
        if self._worker:
            self._worker.stop()
        self._reset_buttons()
        self.progress_bar.setFormat("已停止")

    def _reset_buttons(self) -> None:
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_log(self, msg: str) -> None:
        self.log_view.appendPlainText(msg)

    def _on_progress(self, ratio: float, status: str) -> None:
        self.progress_bar.setValue(int(ratio * 100))
        self.progress_bar.setFormat(f"{status} ({int(ratio*100)}%)")
        self.status_message.emit(f"训练: {status}")

    def _on_metrics(self, m: dict) -> None:
        html = "<br>".join(
            f"<b style='color:#5E6AD2'>{k}</b>: <span style='color:#EDEDEF'>{v}</span>"
            for k, v in m.items()
        )
        self.metrics_view.setHtml(html)

    def _on_finished(self, best_pt: str) -> None:
        self._reset_buttons()
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("训练完成")
        self.report_btn.setEnabled(True)
        self.status_message.emit("训练完成")
        if best_pt:
            self.agent_message.emit("assistant",
                f"训练完成\nbest.pt: {best_pt}\n\n"
                f"可点击「生成报告 (Agent)」让 Agent 写分析报告, "
                f"或切到右侧 Agent 对话发「分析 {Path(self.project_edit.text()).as_posix()}/{self.name_edit.text()}」")

    def _on_failed(self, err: str) -> None:
        self._reset_buttons()
        self.progress_bar.setFormat("训练失败")
        QMessageBox.critical(self, "训练失败", f"训练失败:\n{err}")

    def _on_generate_report(self) -> None:
        project = self.project_edit.text().strip() or "./runs"
        name = self.name_edit.text().strip() or "exp"
        train_dir = Path(project) / name
        if not train_dir.is_dir():
            QMessageBox.warning(self, "目录不存在", f"训练目录不存在: {train_dir}")
            return

        self.agent_message.emit("user", f"请分析训练结果: {train_dir}")
        self.status_message.emit("Agent 正在生成报告 ...")

        try:
            from yolo_forge_agent.report_agent import ReportAgent
            agent = ReportAgent()
            result = agent.run(str(train_dir))
            if result.ok:
                self.agent_message.emit("assistant", result.content)
                self.status_message.emit("报告已生成")
            else:
                self.agent_message.emit("system", f"报告生成失败: {result.error}")
        except Exception as e:
            self.agent_message.emit("system", f"Agent 调用失败: {e}")
