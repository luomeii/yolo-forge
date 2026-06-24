"""右侧 Agent 对话面板 — v0.10.6 完整版.

包含: 会话列表 + Markdown 渲染 + 旋转动画 + 停止按钮 + 工具调用美化.
"""
from __future__ import annotations

import re
from datetime import datetime

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QInputDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QMessageBox, QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from .agent_worker import _AgentWorker

SPINNER_CHARS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class AgentChatPanel(QWidget):
    submit_message = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RightPanel")
        self.setMinimumWidth(320)
        self.setMaximumWidth(500)
        self._worker = None
        self._current_conv_id = None
        self._spinner_idx = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._update_spinner)
        self._build_ui()
        self._welcome()

    def _update_spinner(self):
        self._spinner_idx = (self._spinner_idx + 1) % len(SPINNER_CHARS)
        self.send_btn.setText(f"{SPINNER_CHARS[self._spinner_idx]} 运行中")

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QLabel("  YOLO 助手")
        header.setObjectName("PanelHeader")
        outer.addWidget(header)

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(2)

        # ── 上: 会话列表 ──
        conv_widget = QWidget()
        cl = QVBoxLayout(conv_widget)
        cl.setContentsMargins(8, 8, 8, 4)
        cl.setSpacing(6)

        hdr_row = QHBoxLayout()
        hdr = QLabel("对话历史")
        hdr.setStyleSheet("color: #8A8F98; font-size: 11px; font-weight: 600; padding: 2px 4px;")
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()

        new_btn = QPushButton("+ 新建")
        new_btn.setObjectName("GhostButton")
        new_btn.setFixedHeight(22)
        new_btn.setStyleSheet("padding: 0 8px; font-size: 11px;")
        new_btn.clicked.connect(self._on_new_conversation)
        hdr_row.addWidget(new_btn)

        del_btn = QPushButton("删除")
        del_btn.setObjectName("GhostButton")
        del_btn.setFixedHeight(22)
        del_btn.setStyleSheet("padding: 0 8px; font-size: 11px;")
        del_btn.clicked.connect(self._on_delete_conversation)
        hdr_row.addWidget(del_btn)
        cl.addLayout(hdr_row)

        self.conv_list = QListWidget()
        self.conv_list.setStyleSheet("""
            QListWidget { background-color: #050506; border: 1px solid rgba(255,255,255,0.04); border-radius: 6px; padding: 2px; font-size: 12px; }
            QListWidget::item { padding: 6px 8px; border-radius: 4px; color: #8A8F98; }
            QListWidget::item:selected { background-color: rgba(94, 106, 210, 0.12); color: #EDEDEF; border-left: 2px solid #5E6AD2; }
            QListWidget::item:hover:!selected { background-color: rgba(255,255,255,0.04); }
        """)
        self.conv_list.setMaximumHeight(120)
        self.conv_list.itemClicked.connect(self._on_select_conversation)
        self.conv_list.itemDoubleClicked.connect(self._on_rename_conversation)
        self.conv_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.conv_list.customContextMenuRequested.connect(self._on_conv_context_menu)
        cl.addWidget(self.conv_list)
        splitter.addWidget(conv_widget)

        # ── 下: 对话区 ──
        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        chat_layout.setContentsMargins(0, 4, 0, 0)
        chat_layout.setSpacing(0)

        self.history_view = QTextEdit()
        self.history_view.setObjectName("ChatHistory")
        self.history_view.setReadOnly(True)
        chat_layout.addWidget(self.history_view, 1)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(12, 8, 12, 12)
        input_row.setSpacing(8)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("问 YOLO 助手...")
        self.input_edit.returnPressed.connect(self._on_submit)
        input_row.addWidget(self.input_edit, 1)

        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("PrimaryButton")
        self.send_btn.clicked.connect(self._on_submit)
        input_row.addWidget(self.send_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("DangerButton")
        self.stop_btn.setFixedWidth(60)
        self.stop_btn.hide()
        self.stop_btn.clicked.connect(self._on_stop)
        input_row.addWidget(self.stop_btn)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setObjectName("GhostButton")
        self.clear_btn.setToolTip("清空当前会话")
        self.clear_btn.clicked.connect(self._on_clear)
        input_row.addWidget(self.clear_btn)
        chat_layout.addLayout(input_row)
        splitter.addWidget(chat_widget)

        splitter.setSizes([120, 500])
        outer.addWidget(splitter, 1)

    # ─── 会话列表 ───
    def _refresh_conversation_list(self):
        try:
            from yolo_forge_agent.conversation_store import get_store
            store = get_store()
            self.conv_list.clear()
            current_row = -1
            for i, meta in enumerate(store.list_conversations()):
                item_text = f"{meta.title}\n  {meta.updated_at}  ({meta.message_count} 条)"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, meta.id)
                self.conv_list.addItem(item)
                if meta.id == self._current_conv_id:
                    self.conv_list.setCurrentItem(item)
                    current_row = i
            if current_row >= 0:
                self.conv_list.setCurrentRow(current_row)
        except Exception as e:
            print(f"[WARN] 刷新会话列表失败: {e}")

    def _on_new_conversation(self):
        try:
            from yolo_forge_agent.conversation_store import get_store
            store = get_store()
            meta = store.create_conversation()
            self._current_conv_id = meta.id
            self._refresh_conversation_list()
            self.history_view.clear()
            self._welcome()
            mw = self.window()
            if hasattr(mw, "_switch_conversation"):
                mw._switch_conversation(meta.id)
        except Exception as e:
            print(f"[WARN] 新建会话失败: {e}")

    def _on_delete_conversation(self):
        item = self.conv_list.currentItem()
        if not item:
            return
        conv_id = item.data(Qt.UserRole)
        reply = QMessageBox.question(self, "确认删除", "确定删除这个会话吗?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            from yolo_forge_agent.conversation_store import get_store
            store = get_store()
            store.delete_conversation(conv_id)
            if self._current_conv_id == conv_id:
                self._current_conv_id = None
            self._refresh_conversation_list()
            self.history_view.clear()
            self._welcome()
            if self.conv_list.count() > 0:
                self.conv_list.setCurrentRow(0)
                self._on_select_conversation(self.conv_list.currentItem())
            else:
                self._on_new_conversation()
        except Exception as e:
            print(f"[WARN] 删除会话失败: {e}")

    def _on_rename_conversation(self, item):
        if not item:
            return
        conv_id = item.data(Qt.UserRole)
        try:
            from yolo_forge_agent.conversation_store import get_store
            store = get_store()
            meta = store.get_meta(conv_id)
            if not meta:
                return
            new_title, ok = QInputDialog.getText(self, "重命名会话", "新名称:", text=meta.title)
            if ok and new_title.strip():
                store.rename_conversation(conv_id, new_title.strip())
                self._refresh_conversation_list()
        except Exception as e:
            print(f"[WARN] 重命名会话失败: {e}")

    def _on_conv_context_menu(self, pos):
        item = self.conv_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        menu.addAction("重命名")
        menu.addAction("删除")
        action = menu.exec(self.conv_list.mapToGlobal(pos))
        if action and action.text() == "重命名":
            self._on_rename_conversation(item)
        elif action and action.text() == "删除":
            self._on_delete_conversation()

    def _on_select_conversation(self, item):
        if not item:
            return
        conv_id = item.data(Qt.UserRole)
        self._current_conv_id = conv_id
        self._load_conversation_messages(conv_id)
        mw = self.window()
        if hasattr(mw, "_switch_conversation"):
            mw._switch_conversation(conv_id)

    def _load_conversation_messages(self, conv_id):
        try:
            from yolo_forge_agent.conversation_store import get_store
            store = get_store()
            messages = store.load_messages(conv_id)
            self.history_view.clear()
            if not messages:
                self._welcome()
                return
            for m in messages:
                self.append_message(m.role, m.content, m.timestamp)
        except Exception as e:
            print(f"[WARN] 加载会话消息失败: {e}")
            self._welcome()

    # ─── 提交 ───
    def _on_submit(self):
        text = self.input_edit.text().strip()
        if not text:
            return
        self.input_edit.clear()
        self.append_message("user", text)
        self.submit_message.emit("unified", text)
        self.set_busy(True)

    def _on_stop(self):
        mw = self.window()
        if hasattr(mw, '_agent_worker') and mw._agent_worker:
            mw._agent_worker.terminate()
            mw._agent_worker.wait(2000)
            mw._agent_worker = None
        self.append_message("system", "[!] 用户已停止当前操作")
        self.set_busy(False)

    def _on_clear(self):
        if not self._current_conv_id:
            self.history_view.clear()
            self._welcome()
            return
        try:
            from yolo_forge_agent.conversation_store import get_store, CONVERSATIONS_DIR
            import json
            from pathlib import Path
            msg_file = CONVERSATIONS_DIR / f"{self._current_conv_id}.json"
            if msg_file.exists():
                with open(msg_file, "w", encoding="utf-8") as f:
                    json.dump({"conv_id": self._current_conv_id, "messages": []}, f, ensure_ascii=False, indent=2)
                store = get_store()
                for c in store.conversations:
                    if c.id == self._current_conv_id:
                        c.message_count = 0
                        break
                store._save_index()
            self.history_view.clear()
            self._welcome()
            self._refresh_conversation_list()
        except Exception as e:
            print(f"[WARN] 清空会话失败: {e}")

    # ─── 消息显示 ───
    def append_message(self, role, content, timestamp=""):
        colors = {"user": "#5E6AD2", "assistant": "#22C55E", "system": "#F59E0B", "tool": "#8A8F98", "log": "#5F636A"}
        labels = {"user": "你", "assistant": "Agent", "system": "系统", "tool": "工具", "log": "日志"}
        bgs = {"user": "rgba(94,106,210,0.08)", "assistant": "rgba(34,197,94,0.08)", "system": "rgba(245,158,11,0.08)", "tool": "rgba(255,255,255,0.04)", "log": "rgba(0,0,0,0.2)"}
        color = colors.get(role, "#EDEDEF")
        label = labels.get(role, role)
        bg = bgs.get(role, "rgba(255,255,255,0.04)")
        if not timestamp:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if role == "assistant":
            body = self._markdown_to_html(content)
        elif role == "tool":
            # v0.10.6: 工具调用用紧凑样式, 不显示标签头, 只显示内容
            safe = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            html = (f'<div style="margin:1px 0;padding:3px 10px 3px 16px;'
                    f'border-left:2px solid {color};'
                    f'font-size:11px;color:#8A8F98;font-family:monospace;">{safe}</div>')
            self.history_view.append(html)
            self.history_view.verticalScrollBar().setValue(self.history_view.verticalScrollBar().maximum())
            return
        else:
            safe = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            safe = re.sub(r"```(\w*)<br>(.*?)```", r'<pre style="background:#020203;padding:10px;border-radius:6px;overflow-x:auto;font-family:monospace;font-size:11px;color:#EDEDEF;border:1px solid rgba(255,255,255,0.08);margin:6px 0;">\2</pre>', safe, flags=re.DOTALL)
            body = safe

        html = (f'<div style="margin:8px 0;padding:10px 12px;background:{bg};border-radius:8px;border-left:2px solid {color};">'
                f'<div style="display:flex;justify-content:space-between;margin-bottom:4px;">'
                f'<span style="color:{color};font-size:11px;font-weight:600;">{label}</span>'
                f'<span style="color:#5F636A;font-size:10px;font-family:monospace;">{timestamp}</span>'
                f'</div><div style="color:#EDEDEF;font-size:13px;line-height:1.55;">{body}</div></div>')
        self.history_view.append(html)
        self.history_view.verticalScrollBar().setValue(self.history_view.verticalScrollBar().maximum())

    def _markdown_to_html(self, md):
        import re as _re
        text = md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = _re.sub(r"```(\w*)\n(.*?)```", r'<pre style="background:#020203;padding:10px;border-radius:6px;overflow-x:auto;font-family:monospace;font-size:11px;color:#EDEDEF;border:1px solid rgba(255,255,255,0.08);margin:6px 0;">\2</pre>', text, flags=_re.DOTALL)
        text = _re.sub(r"`([^`]+)`", r'<code style="background:#020203;padding:2px 4px;border-radius:3px;font-family:monospace;font-size:12px;">\1</code>', text)
        text = _re.sub(r"^### (.+)$", r'<h4 style="color:#EDEDEF;margin:8px 0 4px 0;">\1</h4>', text, flags=_re.MULTILINE)
        text = _re.sub(r"^## (.+)$", r'<h3 style="color:#EDEDEF;margin:10px 0 6px 0;">\1</h3>', text, flags=_re.MULTILINE)
        text = _re.sub(r"^# (.+)$", r'<h2 style="color:#EDEDEF;margin:12px 0 8px 0;">\1</h2>', text, flags=_re.MULTILINE)
        text = _re.sub(r"\*\*([^*]+)\*\*", r'<b style="color:#EDEDEF;">\1</b>', text)
        text = _re.sub(r"^[\-\*] (.+)$", r'<div style="padding-left:16px;color:#EDEDEF;">• \1</div>', text, flags=_re.MULTILINE)
        text = _re.sub(r"^(\d+)\. (.+)$", r'<div style="padding-left:20px;color:#EDEDEF;">\1. \2</div>', text, flags=_re.MULTILINE)
        text = _re.sub(r"^---+$", r'<hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:8px 0;">', text, flags=_re.MULTILINE)
        text = _re.sub(r"\n(?!</)", "<br>\n", text)
        return text

    def set_busy(self, busy):
        self.send_btn.setEnabled(not busy)
        self.input_edit.setEnabled(not busy)
        if busy:
            self.input_edit.setPlaceholderText("Agent 运行中...")
            self.send_btn.setText("⠋ 运行中")
            self._spinner_timer.start(120)
            self.stop_btn.show()
        else:
            self._spinner_timer.stop()
            self.send_btn.setText("发送")
            self.input_edit.setPlaceholderText("问 YOLO 助手...")
            self.stop_btn.hide()

    def _welcome(self):
        self.history_view.setHtml(
            '<div style="padding:16px;color:#8A8F98;font-size:12px;line-height:1.65;">'
            '<div style="color:#EDEDEF;font-size:15px;font-weight:600;margin-bottom:10px;">你好，我是 YOLO 助手</div>'
            '我能做两类事:<br><br>'
            '<div style="padding:8px 10px;background:rgba(94,106,210,0.08);border-radius:6px;border-left:2px solid #5E6AD2;margin-bottom:8px;">'
            '<b style="color:#5E6AD2;">[i] 咨询对话</b><br>'
            '<span style="color:#8A8F98;">YOLO 模型选型、超参建议、训练技巧、问题诊断...</span></div>'
            '<div style="padding:8px 10px;background:rgba(34,197,94,0.08);border-radius:6px;border-left:2px solid #22C55E;margin-bottom:8px;">'
            '<b style="color:#22C55E;">[+] 调用工具</b><br>'
            '<span style="color:#8A8F98;">扫描数据集、转换格式、训练模型、生成报告</span></div>'
            '<div style="padding:8px 0 0 0;"><b style="color:#EDEDEF;">试试:</b><br>'
            '• "你好"<br>• "扫描 D:\\\\数据集\\\\datasets"<br>• "训练 D:\\\\out\\\\data.yaml 30 epochs"</div></div>'
        )
