"""暗色 IDE 主题 (基于 ui-ux-pro-max skill 推荐的 Modern Dark Cinema 调色板).

设计参考:
- ui-ux-pro-max skill 检索结果: "Modern Dark (Cinema Mobile)" 适合 developer tools / AI tool interfaces
- 调色板: bg-deep #020203 / bg-base #050506 / bg-elevated #0a0a0c / accent #5E6AD2
- Typography: "Developer Mono" — JetBrains Mono (code) + IBM Plex Sans (UI), 中文用 PingFang SC
- 圆角: 8px (cards), 6px (buttons), 4px (inputs)
- 边框: rgba(255,255,255,0.08) hairline
- 强调色克制使用, 只在关键操作 / 选中态 / 强调文本
"""
from __future__ import annotations


# ─────────────────────────────────────────────────────────────
#  调色板 (基于 ui-ux-pro-max skill "Modern Dark Cinema")
# ─────────────────────────────────────────────────────────────
COLORS = {
    # 背景层 (从深到浅)
    "bg_deep":      "#020203",   # 最外层 (toolbar / statusbar / 画布背景)
    "bg_base":      "#050506",   # 主窗口背景
    "bg_elevated":  "#0a0a0c",   # 卡片 / 输入框 背景
    "bg_panel":     "#08080a",   # 侧栏 / 右栏 背景
    "bg_hover":     "#15151a",   # hover 态
    "bg_selected":  "#1a1a22",   # 选中态 (中性深灰)
    "bg_input":     "#0a0a0c",   # 输入框背景

    # 表面 (半透明覆盖)
    "surface":      "rgba(255, 255, 255, 0.04)",   # 卡片表面高光
    "surface_strong": "rgba(255, 255, 255, 0.08)",  # 强表面

    # 边框
    "border":         "rgba(255, 255, 255, 0.08)",   # 主边框 (hairline)
    "border_subtle":  "rgba(255, 255, 255, 0.04)",   # 更细的分隔
    "border_focus":   "#5E6AD2",                      # 焦点态

    # 文本
    "text_primary":   "#EDEDEF",   # 主要文本
    "text_secondary": "#8A8F98",   # 次要文本
    "text_muted":     "#5F636A",   # 弱化文本
    "text_inverse":   "#FFFFFF",
    "text_link":      "#7B85E8",

    # 强调 (克制使用)
    "accent":         "#5E6AD2",   # 主蓝紫 (Linear 风格)
    "accent_hover":   "#6E7AE0",
    "accent_pressed": "#4F5AC0",
    "accent_glow":    "rgba(94, 106, 210, 0.20)",
    "accent_subtle":  "rgba(94, 106, 210, 0.12)",
    "success":        "#22C55E",
    "warn":           "#F59E0B",
    "error":          "#EF4444",

    # 语法高亮
    "syntax_keyword": "#569cd6",
    "syntax_string":  "#ce9178",
    "syntax_comment": "#6a9955",
    "syntax_number":  "#b5cea8",
}


# ─────────────────────────────────────────────────────────────
#  字体配置 (基于 ui-ux-pro-max skill "Developer Mono")
# ─────────────────────────────────────────────────────────────
FONT_UI = '"PingFang SC", "Microsoft YaHei", "IBM Plex Sans", "Segoe UI", "Helvetica Neue", sans-serif'
FONT_MONO = '"JetBrains Mono", "Cascadia Code", "Consolas", "Courier New", monospace'


# ─────────────────────────────────────────────────────────────
#  全局 QSS (基于 ui-ux-pro-max "Modern Dark Cinema" 指南)
# ─────────────────────────────────────────────────────────────
GLOBAL_QSS = f"""
* {{
    font-family: {FONT_UI};
    font-size: 13px;
    color: {COLORS['text_primary']};
    outline: none;
}}

QMainWindow, QWidget {{
    background-color: {COLORS['bg_base']};
}}

/* ── 顶部 toolbar ── */
QToolBar {{
    background-color: {COLORS['bg_deep']};
    border: none;
    border-bottom: 1px solid {COLORS['border']};
    padding: 8px 14px;
    spacing: 10px;
    min-height: 40px;
}}
QToolBar QLabel {{
    color: {COLORS['text_secondary']};
    padding: 0 4px;
    font-size: 12px;
    background: transparent;
}}
QToolBar QLabel#AppName {{
    color: {COLORS['text_primary']};
    font-size: 14px;
    font-weight: 600;
    letter-spacing: -0.3px;
    padding: 0 8px 0 0;
}}

/* ── 状态栏 ── */
QStatusBar {{
    background-color: {COLORS['bg_deep']};
    border-top: 1px solid {COLORS['border']};
    color: {COLORS['text_muted']};
    font-size: 11px;
    padding: 4px 14px;
    min-height: 22px;
}}
QStatusBar QLabel {{
    color: {COLORS['text_muted']};
    background: transparent;
}}

/* ── 左侧导航栏 ── */
#LeftSidebar {{
    background-color: {COLORS['bg_panel']};
    border-right: 1px solid {COLORS['border']};
}}
#LeftSidebar QLabel#SidebarHeader {{
    color: {COLORS['text_muted']};
    font-size: 10px;
    font-weight: 600;
    padding: 18px 16px 6px 16px;
    letter-spacing: 1.5px;
    background: transparent;
}}
#LeftSidebar QPushButton {{
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    color: {COLORS['text_secondary']};
    text-align: left;
    padding: 10px 16px;
    font-size: 13px;
    min-height: 24px;
    border-radius: 0;
}}
#LeftSidebar QPushButton:hover {{
    background-color: {COLORS['bg_hover']};
    color: {COLORS['text_primary']};
}}
#LeftSidebar QPushButton:checked {{
    background-color: {COLORS['accent_subtle']};
    border-left: 2px solid {COLORS['accent']};
    color: {COLORS['text_primary']};
}}

/* ── 右侧 Agent 面板 ── */
#RightPanel {{
    background-color: {COLORS['bg_panel']};
    border-left: 1px solid {COLORS['border']};
}}
#RightPanel QLabel#PanelHeader {{
    color: {COLORS['text_primary']};
    font-size: 13px;
    font-weight: 600;
    padding: 14px 16px 12px 16px;
    border-bottom: 1px solid {COLORS['border']};
    background: transparent;
}}

/* ── 中间主区 ── */
#CenterArea, QStackedWidget {{
    background-color: {COLORS['bg_base']};
}}

/* ── 通用按钮 ── */
QPushButton {{
    background-color: {COLORS['bg_elevated']};
    border: 1px solid {COLORS['border']};
    color: {COLORS['text_primary']};
    padding: 7px 16px;
    border-radius: 6px;
    min-height: 18px;
    min-width: 60px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {COLORS['bg_hover']};
    border-color: {COLORS['surface_strong']};
}}
QPushButton:pressed {{
    background-color: {COLORS['bg_deep']};
}}
QPushButton:disabled {{
    color: {COLORS['text_muted']};
    background-color: {COLORS['bg_base']};
    border-color: {COLORS['border_subtle']};
}}
QPushButton#PrimaryButton {{
    background-color: {COLORS['accent']};
    border-color: {COLORS['accent']};
    color: {COLORS['text_inverse']};
    font-weight: 600;
}}
QPushButton#PrimaryButton:hover {{
    background-color: {COLORS['accent_hover']};
    border-color: {COLORS['accent_hover']};
}}
QPushButton#PrimaryButton:pressed {{
    background-color: {COLORS['accent_pressed']};
}}
QPushButton#PrimaryButton:disabled {{
    background-color: {COLORS['bg_elevated']};
    border-color: {COLORS['border_subtle']};
    color: {COLORS['text_muted']};
}}
QPushButton#DangerButton {{
    background-color: transparent;
    border: 1px solid {COLORS['error']};
    color: {COLORS['error']};
}}
QPushButton#DangerButton:hover {{
    background-color: {COLORS['error']};
    color: {COLORS['text_inverse']};
}}
QPushButton#DangerButton:disabled {{
    color: {COLORS['text_muted']};
    border-color: {COLORS['border_subtle']};
}}
QPushButton#GhostButton {{
    background-color: transparent;
    border: none;
    color: {COLORS['text_secondary']};
    padding: 5px 10px;
    min-width: 40px;
}}
QPushButton#GhostButton:hover {{
    color: {COLORS['text_primary']};
    background-color: {COLORS['bg_hover']};
    border-radius: 6px;
}}
QPushButton#SuccessButton {{
    background-color: {COLORS['success']};
    border-color: {COLORS['success']};
    color: {COLORS['bg_deep']};
    font-weight: 600;
}}
QPushButton#SuccessButton:hover {{
    background-color: #16a34a;
}}

/* ── 输入框 ── */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {COLORS['bg_input']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px 10px;
    color: {COLORS['text_primary']};
    selection-background-color: {COLORS['accent']};
    selection-color: {COLORS['text_inverse']};
    min-height: 20px;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {COLORS['border_focus']};
}}
QLineEdit:disabled, QSpinBox:disabled {{
    color: {COLORS['text_muted']};
    background-color: {COLORS['bg_base']};
}}
QPlainTextEdit#LogView, QTextEdit#LogView {{
    font-family: {FONT_MONO};
    font-size: 12px;
    background-color: {COLORS['bg_deep']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 10px 12px;
    line-height: 1.6;
}}
QTextEdit#ChatHistory {{
    background-color: {COLORS['bg_base']};
    border: none;
    padding: 6px;
}}

/* ── 下拉框 ── */
QComboBox::drop-down {{
    border: none;
    width: 26px;
    background: transparent;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLORS['text_muted']};
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_elevated']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    selection-background-color: {COLORS['accent']};
    selection-color: {COLORS['text_inverse']};
    outline: none;
    padding: 4px;
}}

/* ── 标签 ── */
QLabel {{
    color: {COLORS['text_primary']};
    background: transparent;
}}
QLabel#SectionTitle {{
    color: {COLORS['text_primary']};
    font-size: 18px;
    font-weight: 600;
    letter-spacing: -0.3px;
    padding: 0 0 4px 0;
}}
QLabel#SectionSubtitle {{
    color: {COLORS['text_secondary']};
    font-size: 12px;
    padding: 0 0 8px 0;
}}
QLabel#PanelHint {{
    color: {COLORS['text_secondary']};
    font-size: 12px;
    line-height: 18px;
    padding: 10px 14px;
    background-color: {COLORS['bg_elevated']};
    border-left: 2px solid {COLORS['accent']};
    border-radius: 0 6px 6px 0;
}}
QLabel#Hint {{
    color: {COLORS['text_muted']};
    font-size: 11px;
}}
QLabel#FieldLabel {{
    color: {COLORS['text_secondary']};
    font-size: 12px;
}}
QLabel#StatusBarHint {{
    color: {COLORS['text_muted']};
    font-family: {FONT_MONO};
    font-size: 11px;
    padding: 6px 14px;
    background-color: {COLORS['bg_deep']};
    border-top: 1px solid {COLORS['border']};
}}

/* ── 分组框 (用作卡片, 圆角 8px) ── */
QGroupBox {{
    background-color: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    margin-top: 16px;
    padding: 18px 16px 14px 16px;
    color: {COLORS['text_secondary']};
    font-weight: 500;
    font-size: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    background-color: {COLORS['bg_base']};
    color: {COLORS['text_secondary']};
}}

/* ── 进度条 ── */
QProgressBar {{
    background-color: {COLORS['bg_input']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    text-align: center;
    color: {COLORS['text_primary']};
    min-height: 22px;
    font-size: 11px;
}}
QProgressBar::chunk {{
    background-color: {COLORS['accent']};
    border-radius: 5px;
}}

/* ── 滚动条 (细且不显眼, 8px 宽) ── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['surface_strong']};
    min-height: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLORS['text_muted']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {COLORS['surface_strong']};
    min-width: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {COLORS['text_muted']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}

/* ── 分割线 ── */
QSplitter::handle {{
    background-color: {COLORS['border']};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}

/* ── Tab ── */
QTabWidget::pane {{
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    top: -1px;
}}
QTabBar::tab {{
    background: {COLORS['bg_panel']};
    color: {COLORS['text_secondary']};
    padding: 7px 14px;
    border: 1px solid {COLORS['border']};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {COLORS['bg_base']};
    color: {COLORS['text_primary']};
    border-color: {COLORS['accent']};
}}
QTabBar::tab:hover:!selected {{
    background: {COLORS['bg_hover']};
}}

/* ── 复选框 ── */
QCheckBox {{
    color: {COLORS['text_primary']};
    spacing: 6px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {COLORS['border']};
    background: {COLORS['bg_input']};
    border-radius: 3px;
}}
QCheckBox::indicator:checked {{
    background: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}

/* ── 拖放区 ── */
QFrame#DropZone {{
    background-color: {COLORS['bg_elevated']};
    border: 2px dashed {COLORS['border']};
    border-radius: 8px;
}}
QFrame#DropZone:hover {{
    border-color: {COLORS['accent']};
    background-color: {COLORS['bg_hover']};
}}

/* ── QMessageBox ── */
QMessageBox {{
    background-color: {COLORS['bg_base']};
}}
QMessageBox QLabel {{
    color: {COLORS['text_primary']};
    font-size: 13px;
}}
QMessageBox QPushButton {{
    min-width: 80px;
}}

/* ── ToolTip ── */
QToolTip {{
    background-color: {COLORS['bg_elevated']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
}}
"""


def apply_theme(app) -> None:
    """把主题应用到 QApplication."""
    app.setStyleSheet(GLOBAL_QSS)
    from PySide6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS["bg_base"]))
    palette.setColor(QPalette.WindowText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.Base, QColor(COLORS["bg_input"]))
    palette.setColor(QPalette.Text, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.Button, QColor(COLORS["bg_elevated"]))
    palette.setColor(QPalette.ButtonText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.Highlight, QColor(COLORS["accent"]))
    palette.setColor(QPalette.HighlightedText, QColor(COLORS["text_inverse"]))
    palette.setColor(QPalette.ToolTipBase, QColor(COLORS["bg_elevated"]))
    palette.setColor(QPalette.ToolTipText, QColor(COLORS["text_primary"]))
    app.setPalette(palette)
