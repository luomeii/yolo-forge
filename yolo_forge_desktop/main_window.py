"""主窗口: 类 Codex 三栏布局.

v0.2.1 改动:
- 默认窗口 1280x800 (从 1400x900 缩小)
- 三栏宽度平衡: 左 170 / 右 350 / 中 自适应
- 全中文化标签
- 顶部 toolbar 简洁化
- 添加状态栏快捷操作
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QSizePolicy, QStackedWidget, QStatusBar, QToolBar, QVBoxLayout, QWidget,
)

from .panels import (
    AgentChatPanel, ConverterPanel, InspectorPanel, ReviewerPanel,
    SettingsPanel, TrainerPanel,
)
from .panels.agent_chat import _AgentWorker
from .theme import apply_theme


class MainWindow(QMainWindow):
    """主窗口."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("yolo-forge · YOLO 数据集工作站")
        self.resize(1280, 800)
        self.setMinimumSize(1000, 650)

        self._panels: dict = {}
        self._pending_profile_yaml: str = ""  # Structure Agent 生成的 profile 草稿
        self._agent_worker = None
        self._unified_agent = None  # v0.3.1: 持久化的 Agent 实例, 保留对话历史
        self._build_ui()
        self._init_agent()
        self._switch_panel("converter")

    def _init_agent(self) -> None:
        """初始化持久化的 UnifiedAgent (跨多次发消息保留对话历史)."""
        try:
            from yolo_forge_agent.unified_agent import UnifiedAgent
            self._unified_agent = UnifiedAgent(
                on_progress=lambda name, status: self.status_label.setText(f"[{name}] {status}"),
                on_tool_start=lambda name, args: self._on_tool_start(name, args),
                on_tool_end=lambda name, result: self._on_tool_end(name, result),
                on_train_log=lambda line: self._on_train_log(line),
                on_train_complete=lambda bp, td: self._on_train_complete(bp, td),
            )
        except Exception as e:
            print(f"[WARN] Agent 初始化失败: {e}")
            self._unified_agent = None

    # ────────── UI 构建 ──────────
    def _build_ui(self) -> None:
        # 顶部 toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        app_name = QLabel("yolo-forge")
        app_name.setObjectName("AppName")
        toolbar.addWidget(app_name)
        subtitle = QLabel("YOLO 数据集本地工作站")
        toolbar.addWidget(subtitle)
        toolbar.addSeparator()

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toolbar.addWidget(spacer)

        about_btn = QPushButton("关于")
        about_btn.setObjectName("GhostButton")
        about_btn.clicked.connect(self._show_about)
        toolbar.addWidget(about_btn)
        self.addToolBar(toolbar)

        # 中央三栏
        central = QWidget()
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── 左侧导航 ──
        left = self._build_left_sidebar()
        outer.addWidget(left)

        # 中间分隔线
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.NoFrame)
        sep1.setFixedWidth(1)
        sep1.setStyleSheet(f"background-color: #1f1f26;")
        outer.addWidget(sep1)

        # ── 中间主区 ──
        self.center_stack = QStackedWidget()
        self.center_stack.setObjectName("CenterArea")
        self._register_panels()
        outer.addWidget(self.center_stack, 1)

        # 中间分隔线
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.NoFrame)
        sep2.setFixedWidth(1)
        sep2.setStyleSheet(f"background-color: #1f1f26;")
        outer.addWidget(sep2)

        # ── 右侧 Agent 对话 ──
        self.agent_panel = AgentChatPanel()
        self.agent_panel.submit_message.connect(self._on_agent_submit)
        outer.addWidget(self.agent_panel)

        self.setCentralWidget(central)

        # 状态栏
        sb = QStatusBar()
        sb.setSizeGripEnabled(False)
        self.status_label = QLabel("就绪")
        sb.addWidget(self.status_label)
        self.agent_status_label = QLabel("Agent 未配置")
        self.agent_status_label.setStyleSheet("color: #ef4444;")
        sb.addPermanentWidget(self.agent_status_label)
        sb.addPermanentWidget(QLabel("v0.2.1"))
        self.setStatusBar(sb)

        # 初始化时刷新 Agent 状态
        self._update_agent_status()

    def _build_left_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("LeftSidebar")
        sidebar.setFixedWidth(170)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("功能导航")
        header.setObjectName("SidebarHeader")
        layout.addWidget(header)

        self.nav_buttons: dict = {}
        # (panel_id, 显示名, 图标 emoji, 简短描述)
        nav_items = [
            ("converter", "▶  数据转换",     "把杂乱数据集转成 YOLO 格式"),
            ("inspector", "▶  结构扫描",     "确定性扫描数据集结构"),
            ("reviewer",  "▶  标签审查",     "查看/补标/修正已有标签"),
            ("trainer",   "▶  模型训练",     "用 Ultralytics 训练 YOLO"),
            ("settings",  "▶  设置",         "配置 LLM API 和默认路径"),
        ]
        for pid, label, _desc in nav_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, p=pid: self._switch_panel(p))
            layout.addWidget(btn)
            self.nav_buttons[pid] = btn

        layout.addStretch()

        # 底部: Agent 状态指示
        agent_header = QLabel("AGENT 状态")
        agent_header.setObjectName("SidebarHeader")
        layout.addWidget(agent_header)

        self.agent_indicator = QLabel("  ● 未配置")
        self.agent_indicator.setStyleSheet("color: #ef4444; padding: 4px 14px; font-size: 12px;")
        layout.addWidget(self.agent_indicator)

        return sidebar

    def _register_panels(self) -> None:
        """创建所有 panel 实例并注册到 stacked widget."""
        panel_classes = [
            ConverterPanel,
            InspectorPanel,
            ReviewerPanel,
            TrainerPanel,
            SettingsPanel,
        ]
        for cls in panel_classes:
            p = cls()
            p.status_message.connect(self._on_status_message)
            p.agent_message.connect(self._on_agent_message)
            self._panels[p.panel_id] = p
            self.center_stack.addWidget(p)

    # ────────── 切换 panel ──────────
    def _switch_panel(self, panel_id: str) -> None:
        if panel_id not in self._panels:
            return
        old_widget = self.center_stack.currentWidget()
        if old_widget is not None and hasattr(old_widget, "on_deactivated"):
            old_widget.on_deactivated()

        new_panel = self._panels[panel_id]
        self.center_stack.setCurrentWidget(new_panel)
        if hasattr(new_panel, "on_activated"):
            new_panel.on_activated()

        # 淡入动画 (窗口效果, 150ms)
        try:
            from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QPoint
            from PySide6.QtGui import QPalette, QColor
            # 简单的窗口透明度淡入
            effect = new_panel.graphicsEffect()
            if effect is None:
                from PySide6.QtWidgets import QGraphicsOpacityEffect
                effect = QGraphicsOpacityEffect(new_panel)
                new_panel.setGraphicsEffect(effect)
            effect.setOpacity(0.0)
            anim = QPropertyAnimation(effect, b"opacity", new_panel)
            anim.setDuration(180)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start(QPropertyAnimation.DeleteWhenStopped)
        except Exception:
            pass  # 动画失败不影响功能

        for pid, btn in self.nav_buttons.items():
            btn.setChecked(pid == panel_id)

        # 状态栏更新
        panel_names = {
            "converter": "数据转换",
            "inspector": "结构扫描",
            "reviewer": "标签审查",
            "trainer": "模型训练",
            "settings": "设置",
        }
        self.status_label.setText(f"当前: {panel_names.get(panel_id, panel_id)}")

    def _update_agent_status(self) -> None:
        try:
            from yolo_forge_agent.config import get_config
            cfg = get_config()
            if cfg.is_llm_configured():
                self.agent_indicator.setText(f"  ● {cfg.llm.model}")
                self.agent_indicator.setStyleSheet(
                    "color: #10b981; padding: 4px 14px; font-size: 12px;"
                )
                self.agent_status_label.setText(f"Agent: {cfg.llm.model}")
                self.agent_status_label.setStyleSheet("color: #10b981;")
            else:
                self.agent_indicator.setText("  ● 未配置")
                self.agent_indicator.setStyleSheet(
                    "color: #ef4444; padding: 4px 14px; font-size: 12px;"
                )
                self.agent_status_label.setText("Agent 未配置")
                self.agent_status_label.setStyleSheet("color: #ef4444;")
        except Exception:
            self.agent_indicator.setText("  ● 模块缺失")
            self.agent_indicator.setStyleSheet(
                "color: #f59e0b; padding: 4px 14px; font-size: 12px;"
            )

    # ────────── 信号处理 ──────────
    def _on_status_message(self, msg: str) -> None:
        self.status_label.setText(msg)

    def _on_agent_message(self, role: str, content: str) -> None:
        self.agent_panel.append_message(role, content)

    def _on_agent_submit(self, agent_name: str, text: str) -> None:
        """v0.3.1: 用持久化 UnifiedAgent, 保留对话历史."""
        from yolo_forge_agent.config import get_config
        cfg = get_config()
        if not cfg.is_llm_configured():
            self.agent_panel.append_message(
                "system", "[!] LLM 未配置。请先到「设置」面板配置 API Key / Base URL / 模型名。"
            )
            return

        if self._unified_agent is None:
            self._init_agent()
            if self._unified_agent is None:
                self.agent_panel.append_message(
                    "system", "[x] Agent 初始化失败, 请检查 agent 模块依赖是否安装"
                )
                return

        # 重置 agent 的 LLM client + 回调 (用户可能刚改了配置)
        try:
            from yolo_forge_agent.llm_client import LLMClient
            self._unified_agent.llm = LLMClient(cfg.llm)
        except Exception:
            pass

        # 启动后台 worker, 把持久化的 agent 实例传进去
        self._agent_worker = _AgentWorker(text, self._unified_agent)
        self._agent_worker.started_step.connect(
            lambda s: self.status_label.setText(s)
        )
        # tool_start / tool_end / train_log / train_complete 已经在 agent 实例的回调里连了
        self._agent_worker.finished_reply.connect(
            lambda reply, conv: self._on_agent_reply(reply)
        )
        self._agent_worker.failed.connect(
            lambda err: self._on_agent_error(err)
        )
        self.agent_panel.set_busy(True)
        self._agent_worker.start()

    def _reset_agent(self) -> None:
        """清空 Agent 对话历史 (用户点「清空」按钮时调用)."""
        if self._unified_agent is not None:
            self._unified_agent.reset_conversation()
            self.agent_panel.append_message("system", "对话历史已清空。")

    def _on_agent_step(self, step: str) -> None:
        self.status_label.setText(step)

    def _on_tool_start(self, name: str, args: dict) -> None:
        """LLM 决定调用工具时显示."""
        # 简化 args 显示
        display_args = []
        for k, v in args.items():
            v_str = str(v)
            if len(v_str) > 60:
                v_str = v_str[:60] + "..."
            display_args.append(f"{k}={v_str}")
        args_str = ", ".join(display_args) if display_args else "(无参数)"
        self.agent_panel.append_message(
            "tool",
            f"[>] 调用工具: {name}({args_str})"
        )

    def _on_tool_end(self, name: str, result: str) -> None:
        """工具执行完显示结果摘要."""
        # 只显示前 300 字符, 完整结果 LLM 会再总结
        preview = result[:300] + ("..." if len(result) > 300 else "")
        self.agent_panel.append_message(
            "tool",
            f"[ok] 工具 {name} 结果:\n{preview}"
        )

    def _on_train_log(self, line: str) -> None:
        """训练日志实时推送."""
        # 只显示关键行, 避免刷屏
        if any(kw in line for kw in ['Epoch', 'all', 'ERROR', 'WARNING', 'Done', 'train', 'val', 'mAP']):
            # 截断长行
            short = line[:120] + ("..." if len(line) > 120 else "")
            self.agent_panel.append_message("log", short)

    def _on_train_complete(self, best_pt: str, train_dir: str) -> None:
        """训练完成回调."""
        if best_pt:
            self.agent_panel.append_message(
                "assistant",
                f"训练完成!\nbest.pt: {best_pt}\n训练目录: {train_dir}\n\n"
                f"我正在自动调用 generate_report 工具生成分析报告..."
            )
        else:
            self.agent_panel.append_message("system", "[x] 训练失败或被中断")

    def _on_agent_reply(self, reply: str) -> None:
        """LLM 最终回复."""
        self.agent_panel.append_message("assistant", reply)
        self.agent_panel.set_busy(False)
        self.status_label.setText("就绪")

    def _on_agent_error(self, err: str) -> None:
        self.agent_panel.append_message("system", f"[x] Agent 错误:\n{err}")
        self.agent_panel.set_busy(False)
        self.status_label.setText("Agent 错误")

    def _run_structure_agent(self, text: str) -> None:
        """v0.3.0: 已废弃, 保留以兼容旧调用."""
        self._on_agent_submit("unified", text)

    def _run_report_agent(self, text: str) -> None:
        self._on_agent_submit("unified", text)

    def _run_train_agent(self, text: str) -> None:
        self._on_agent_submit("unified", text)

    def _show_about(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "关于 yolo-forge",
            "<h3>yolo-forge v0.3.0</h3>"
            "<p>本地优先、Python 原生的 YOLO 数据集工作站。</p>"
            "<p><b>核心模块:</b></p>"
            "<ul>"
            "<li>yolo_forge_core — 转换 / 审查 / 训练 / 扫描</li>"
            "<li>yolo_forge_agent — 统一 LLM Agent + 工具调用</li>"
            "<li>yolo_forge_desktop — PySide6 桌面 GUI</li>"
            "</ul>"
            "<p style='color:#a1a1aa'>MIT License</p>"
        )

    def closeEvent(self, event) -> None:
        for p in self._panels.values():
            if hasattr(p, "on_deactivated"):
                try:
                    p.on_deactivated()
                except Exception:
                    pass
        event.accept()
