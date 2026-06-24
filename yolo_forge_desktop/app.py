"""yolo-forge-desktop 应用入口.

启动方式:
- 终端命令: yolo-forge-desktop
- 或 python -m yolo_forge_desktop.app
"""
from __future__ import annotations

import sys
from typing import Optional


def main(argv: Optional[list] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    # 设置环境变量避免某些 Linux 上的 OpenGL 问题
    import os
    os.environ.setdefault("QT_QUICK_BACKEND", "software")

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    # High DPI 支持 (Qt6 已默认开启, 这里只是显式)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("yolo-forge")
    app.setApplicationDisplayName("yolo-forge")
    app.setOrganizationName("yolo-forge")

    # 应用暗色主题
    from .theme import apply_theme
    apply_theme(app)

    from .main_window import MainWindow
    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
