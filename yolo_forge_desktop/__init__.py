"""yolo_forge_desktop — PySide6 桌面 GUI.

布局结构 (类 Codex / Cursor 三栏):
┌─────────────────────────────────────────────────────────────┐
│                       Top Toolbar                            │
├──────────┬──────────────────────────────────┬───────────────┤
│          │                                  │               │
│  Left    │      Center Main Area            │   Right       │
│  Nav     │  (switches by left selection)    │   Agent Chat  │
│  Sidebar │                                  │   Panel       │
│          │                                  │               │
│          │                                  │               │
│          │                                  │               │
├──────────┴──────────────────────────────────┴───────────────┤
│                    Status Bar                                │
└─────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

__version__ = "0.2.0"
__all__ = ["__version__"]
