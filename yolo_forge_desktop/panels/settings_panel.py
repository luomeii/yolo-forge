"""设置 Panel: 配置 LLM API key / Base URL / 模型名等."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QDoubleSpinBox, QVBoxLayout, QMessageBox,
)

from .base import BasePanel
from yolo_forge_agent.config import AppConfig, LLMConfig, save_config, get_config


class SettingsPanel(BasePanel):
    """设置页: 配 LLM API / 默认路径."""

    panel_id = "settings"
    panel_name = "设置"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_config()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        title = QLabel("设置")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("配置 LLM API 后，Agent 模块才能工作。配置文件位置: ~/.yolo-forge/config.yaml")
        subtitle.setObjectName("SectionSubtitle")
        layout.addWidget(subtitle)

        hint = QLabel(
            "<b>支持的 API:</b> OpenAI / DeepSeek / 智谱 GLM / 通义千问 / Moonshot / 本地 Ollama 等 OpenAI 兼容格式。<br>"
            "<b>注意:</b> API Key 以明文存储在配置文件，已设置 600 权限仅当前用户可读。"
        )
        hint.setObjectName("PanelHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # ── LLM 配置组 ──
        llm_group = QGroupBox("LLM API 配置")
        llm_form = QFormLayout(llm_group)
        llm_form.setSpacing(8)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("sk-...")
        llm_form.addRow("API Key:", self.api_key_edit)

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("https://api.openai.com/v1")
        self.base_url_edit.setText("https://api.openai.com/v1")
        llm_form.addRow("Base URL:", self.base_url_edit)

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("gpt-4o-mini / deepseek-chat / glm-4-flash / qwen-plus ...")
        llm_form.addRow("模型名:", self.model_edit)

        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(0.3)
        llm_form.addRow("温度 (Temperature):", self.temp_spin)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(256, 32768)
        self.max_tokens_spin.setSingleStep(256)
        self.max_tokens_spin.setValue(4096)
        llm_form.addRow("最大 Tokens:", self.max_tokens_spin)

        layout.addWidget(llm_group)

        # ── 常用配置 ──
        common_group = QGroupBox("默认路径")
        common_form = QFormLayout(common_group)
        self.default_dataset_edit = QLineEdit()
        self.default_dataset_edit.setPlaceholderText("/path/to/your/datasets")
        common_form.addRow("默认数据集目录:", self.default_dataset_edit)

        self.default_output_edit = QLineEdit()
        self.default_output_edit.setPlaceholderText("./yolo_output")
        self.default_output_edit.setText("./yolo_output")
        common_form.addRow("默认输出目录:", self.default_output_edit)
        layout.addWidget(common_group)

        # ── 操作按钮 ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self._on_test_connection)
        btn_row.addWidget(self.test_btn)

        self.save_btn = QPushButton("保存配置")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)
        layout.addStretch()

    def _load_config(self) -> None:
        cfg = get_config(reload=True)
        self.api_key_edit.setText(cfg.llm.api_key)
        self.base_url_edit.setText(cfg.llm.base_url)
        self.model_edit.setText(cfg.llm.model)
        self.temp_spin.setValue(cfg.llm.temperature)
        self.max_tokens_spin.setValue(cfg.llm.max_tokens)
        self.default_dataset_edit.setText(cfg.default_dataset_dir)
        self.default_output_edit.setText(cfg.default_output_dir)

    def _collect_config(self) -> AppConfig:
        cfg = get_config()
        cfg.llm = LLMConfig(
            api_key=self.api_key_edit.text().strip(),
            base_url=self.base_url_edit.text().strip() or "https://api.openai.com/v1",
            model=self.model_edit.text().strip() or "gpt-4o-mini",
            temperature=self.temp_spin.value(),
            max_tokens=self.max_tokens_spin.value(),
            timeout=cfg.llm.timeout,
        )
        cfg.default_dataset_dir = self.default_dataset_edit.text().strip()
        cfg.default_output_dir = self.default_output_edit.text().strip() or "./yolo_output"
        return cfg

    def _on_save(self) -> None:
        cfg = self._collect_config()
        save_config(cfg)
        self.status_message.emit("配置已保存")
        QMessageBox.information(self, "已保存", "配置已保存到 ~/.yolo-forge/config.yaml")

    def _on_test_connection(self) -> None:
        cfg = self._collect_config()
        if not cfg.is_llm_configured():
            QMessageBox.warning(self, "缺少配置", "请填入 API Key / Base URL / 模型名")
            return
        save_config(cfg)
        self.status_message.emit("正在测试 LLM 连接...")
        try:
            from yolo_forge_agent.llm_client import LLMClient, ChatMessage
            client = LLMClient(cfg.llm)
            reply = client.chat([
                ChatMessage("system", "你是连接测试器。回复: PONG"),
                ChatMessage("user", "ping"),
            ], max_tokens=16)
            QMessageBox.information(self, "连接成功", f"LLM 响应: {reply.strip()[:200]}")
            self.status_message.emit("LLM 连接正常")
        except Exception as e:
            QMessageBox.critical(self, "连接失败", f"LLM 调用失败:\n{e}")
            self.status_message.emit("LLM 连接失败")
