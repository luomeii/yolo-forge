"""右侧 Agent 对话面板 — 统一 YOLO 助手.

v0.3.0 改动:
- 移除 3 个独立 Agent 选项, 改为 1 个统一助手
- 支持多轮对话上下文
- 工具调用过程实时显示 (调用中 / 结果)
- 训练日志实时推送
- 欢迎引导更友好
"""
from __future__ import annotations

import re
from datetime import datetime

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QVBoxLayout, QWidget,
)


class _AgentWorker(QThread):
    """后台跑 Agent chat, 避免 LLM 调用阻塞 UI.

    v0.3.1 关键改动:
    - 不再自己 new UnifiedAgent, 而是接收主窗口传入的 agent 实例
    - 这样 agent.conversation 才能跨多次调用持久化
    - worker 跑完后通过 finished_reply 信号把最终回复告诉主窗口, 由主窗口负责把回复 append 到 agent.conversation
    """

    started_step = Signal(str)
    tool_start = Signal(str, dict)
    tool_end = Signal(str, str)
    train_log = Signal(str)
    train_complete = Signal(str, str)
    finished_reply = Signal(str, object)  # (reply_text, updated_conversation_list)
    failed = Signal(str)

    def __init__(self, user_text: str, agent):
        super().__init__()
        self.user_text = user_text
        self.agent = agent  # 持有主窗口的 UnifiedAgent 实例, 共享 conversation

    def run(self) -> None:
        try:
            reply = self.agent.chat(self.user_text)
            self.finished_reply.emit(reply, list(self.agent.conversation))
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[ERROR] Agent worker failed: {e}\n{tb}")
            self.failed.emit(f"{e}")
        # 即使失败也要保证 worker 自然退出, 不要 hang 住


class AgentChatPanel(QWidget):
    """右侧 Agent 对话面板."""

    submit_message = Signal(str, str)  # (agent_name, text) — 兼容主窗口接口

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RightPanel")
        self.setFixedWidth(380)
        self._worker: _AgentWorker | None = None
        self._build_ui()
        self._welcome()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部标题
        header = QLabel("  [~] YOLO 助手")
        header.setObjectName("PanelHeader")
        layout.addWidget(header)

        # 状态描述
        desc_label = QLabel(
            "智能助手: 可咨询 YOLO 问题，也可调用工具执行任务。\n"
            "  • 咨询: \"yolo11n 和 yolo11s 怎么选?\"\n"
            "  • 执行: \"扫描并转换 D:\\\\数据集\\\\datasets\"\n"
            "  • 训练: \"训练 D:\\\\yolo_output\\\\data.yaml 100 epochs\""
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(
            "color: #8A8F98; font-size: 11px; padding: 12px 16px 10px 16px; "
            "background: transparent; line-height: 18px;"
        )
        layout.addWidget(desc_label)

        # 历史对话
        self.history_view = QTextEdit()
        self.history_view.setObjectName("ChatHistory")
        self.history_view.setReadOnly(True)
        layout.addWidget(self.history_view, 1)

        # 输入区
        input_row = QHBoxLayout()
        input_row.setContentsMargins(12, 12, 12, 14)
        input_row.setSpacing(8)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("问 YOLO 助手...")
        self.input_edit.returnPressed.connect(self._on_submit)
        input_row.addWidget(self.input_edit, 1)

        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("PrimaryButton")
        self.send_btn.clicked.connect(self._on_submit)
        input_row.addWidget(self.send_btn)

        # 清空对话按钮
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setObjectName("GhostButton")
        self.clear_btn.setToolTip("清空对话历史")
        self.clear_btn.clicked.connect(self._on_clear)
        input_row.addWidget(self.clear_btn)

        layout.addLayout(input_row)

    def _welcome(self) -> None:
        self.history_view.setHtml(
            '<div style="padding: 16px; color: #8A8F98; font-size: 12px; line-height: 1.65;">'
            '<div style="color: #EDEDEF; font-size: 15px; font-weight: 600; margin-bottom: 10px;">'
            '你好，我是 YOLO 助手</div>'
            '我能做两类事:<br><br>'
            '<div style="padding: 8px 10px; background: rgba(94, 106, 210, 0.08); '
            'border-radius: 6px; border-left: 2px solid #5E6AD2; margin-bottom: 8px;">'
            '<b style="color: #5E6AD2;">[i] 咨询对话</b><br>'
            '<span style="color: #8A8F98;">YOLO 模型选型、超参建议、训练技巧、数据集准备、问题诊断...</span>'
            '</div>'
            '<div style="padding: 8px 10px; background: rgba(34, 197, 94, 0.08); '
            'border-radius: 6px; border-left: 2px solid #22C55E; margin-bottom: 8px;">'
            '<b style="color: #22C55E;">[+] 调用工具</b><br>'
            '<span style="color: #8A8F98;">扫描数据集、转换格式、训练模型、生成报告</span>'
            '</div>'
            '<div style="padding: 8px 0 0 0;">'
            '<b style="color: #EDEDEF;">试试这些:</b><br>'
            '• "你好" / "怎么用"<br>'
            '• "yolo11n 和 yolo11s 怎么选?"<br>'
            '• "扫描 D:\\\\数据集\\\\datasets"<br>'
            '• "训练 D:\\\\yolo_output\\\\data.yaml 50 epochs"'
            '</div>'
            '</div>'
        )

    def _on_clear(self) -> None:
        """清空对话历史 (本地 + 主窗口)."""
        self.history_view.clear()
        self._welcome()
        # 通知主窗口清空 UnifiedAgent 的对话历史
        main_window = self.window()
        if hasattr(main_window, "_reset_agent"):
            main_window._reset_agent()

    def _on_submit(self) -> None:
        text = self.input_edit.text().strip()
        if not text:
            return
        self.input_edit.clear()
        # 显示用户消息
        self.append_message("user", text)
        # 发信号给主窗口 (主窗口持有 UnifiedAgent 和对话历史)
        self.submit_message.emit("unified", text)
        self.set_busy(True)

    # ────── 公共 API: 主窗口调用 ──────
    def append_message(self, role: str, content: str) -> None:
        color_map = {
            "user": "#5E6AD2",
            "assistant": "#22C55E",
            "system": "#F59E0B",
            "tool": "#8A8F98",
            "log": "#5F636A",
        }
        label_map = {
            "user": "你",
            "assistant": "Agent",
            "system": "系统",
            "tool": "工具",
            "log": "日志",
        }
        bg_map = {
            "user": "rgba(94, 106, 210, 0.08)",
            "assistant": "rgba(34, 197, 94, 0.08)",
            "system": "rgba(245, 158, 11, 0.08)",
            "tool": "rgba(255, 255, 255, 0.04)",
            "log": "rgba(0, 0, 0, 0.2)",
        }
        color = color_map.get(role, "#EDEDEF")
        label = label_map.get(role, role)
        bg = bg_map.get(role, "rgba(255,255,255,0.04)")
        ts = datetime.now().strftime("%H:%M:%S")
        safe = (content.replace("&", "&amp;")
                       .replace("<", "&lt;")
                       .replace(">", "&gt;")
                       .replace("\n", "<br>"))
        # 代码块
        safe = re.sub(
            r"```(\w*)<br>(.*?)```",
            r'<pre style="background:#020203; padding:10px; border-radius:6px; '
            r'overflow-x:auto; font-family: \'JetBrains Mono\', monospace; '
            r'font-size:11px; color:#EDEDEF; border: 1px solid rgba(255,255,255,0.08); '
            r'margin: 6px 0;">\2</pre>',
            safe, flags=re.DOTALL
        )
        html = (
            f'<div style="margin: 8px 0; padding: 10px 12px; '
            f'background: {bg}; border-radius: 8px; '
            f'border-left: 2px solid {color};">'
            f'<div style="color: {color}; font-size: 11px; margin-bottom: 4px; font-weight:600;">'
            f'{label} · {ts}</div>'
            f'<div style="color: #EDEDEF; font-size: 13px; line-height: 1.55;">{safe}</div>'
            f'</div>'
        )
        self.history_view.append(html)
        self.history_view.verticalScrollBar().setValue(
            self.history_view.verticalScrollBar().maximum()
        )

    def set_busy(self, busy: bool) -> None:
        self.send_btn.setEnabled(not busy)
        self.input_edit.setEnabled(not busy)
        if busy:
            self.input_edit.setPlaceholderText("Agent 思考中...")
        else:
            self.input_edit.setPlaceholderText("问 YOLO 助手...")
