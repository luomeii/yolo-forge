"""各功能 Panel 的统一基类."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget


class BasePanel(QWidget):
    """所有中间区 panel 的基.

    Subclass 应实现:
    - panel_id: 唯一标识 (用于左侧导航切换)
    - panel_name: 显示在侧栏的名字
    """

    panel_id: str = "base"
    panel_name: str = "Base"

    # 当 panel 需要往右侧 Agent 对话面板追加消息时, 发这个信号
    # 参数: (role, content) — role: "user" | "assistant" | "system"
    agent_message = Signal(str, str)

    # 当 panel 需要往状态栏写消息时
    status_message = Signal(str)

    def on_activated(self) -> None:
        """panel 被切到时调用, 子类可重写以刷新状态."""
        pass

    def on_deactivated(self) -> None:
        """panel 被切走时调用, 子类可重写以暂停后台任务."""
        pass
