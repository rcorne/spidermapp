from __future__ import annotations

from PySide6.QtGui import QColor, QPalette

from spidermapp.core.models import IssueSeverity

# Dark is the app's only theme. Palette is Teams-inspired (compact icon
# rail + a filled accent pill for the active item) but green-leaning
# instead of Teams' purple — there is no light-mode variant to fall back to.
BG = "#101512"
BG_ELEVATED = "#171F1B"
BG_SOFT = "#1B2420"
BG_CHIP = "#212B25"
BORDER = "#28332C"

TEXT_PRIMARY = "#E7EDE9"
TEXT_SECONDARY = "#C1CCC5"
TEXT_MUTED = "#93A69C"
TEXT_FAINT = "#748076"

PRIMARY = "#2FBE81"
PRIMARY_HOVER = "#4FD59B"
PRIMARY_PRESSED = "#22995F"
PRIMARY_SOFT = "#1B3A2C"

DANGER = "#EF4444"
DANGER_HOVER = "#F87171"
DANGER_SOFT = "#3A2226"

GOOD_HEX = "#2FBE81"
CRITICAL_HEX = "#F87171"
WARNING_HEX = "#FBBF24"
INFO_HEX = "#60A5FA"

# Rail nav (left icon bar) — one shade darker than the main background,
# same green cast, with a filled pill for the active item like Teams.
RAIL_BG = "#0B0F0D"
RAIL_BORDER = "#1C2620"
RAIL_TEXT = "#8CA096"
RAIL_TEXT_ACTIVE = "#EAF5EF"
RAIL_HOVER = "#182019"
RAIL_ACTIVE_BG = PRIMARY_SOFT

SEVERITY_HEX = {
    IssueSeverity.CRITICAL: CRITICAL_HEX,
    IssueSeverity.WARNING: WARNING_HEX,
    IssueSeverity.INFO: INFO_HEX,
}

SEVERITY_COLOR = {sev: QColor(hexcode) for sev, hexcode in SEVERITY_HEX.items()}
GOOD_COLOR = QColor(GOOD_HEX)

BUTTON_PRIMARY_QSS = f"""
QPushButton {{
    background-color: {PRIMARY};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 7px 18px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: {PRIMARY_HOVER}; }}
QPushButton:pressed {{ background-color: {PRIMARY_PRESSED}; }}
QPushButton:disabled {{ background-color: #33364A; color: #6B7080; }}
"""

BUTTON_DANGER_QSS = f"""
QPushButton {{
    background-color: {DANGER};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 7px 18px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: {DANGER_HOVER}; }}
QPushButton:disabled {{ background-color: #4A2E30; color: #8A6B6C; }}
"""

BUTTON_SECONDARY_QSS = f"""
QPushButton {{
    background-color: {BG_ELEVATED};
    color: {PRIMARY_HOVER};
    border: 1.5px solid {PRIMARY};
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: {PRIMARY_SOFT}; }}
QPushButton:disabled {{ color: #565A6E; border-color: {BORDER}; background-color: {BG_ELEVATED}; }}
"""

BUTTON_SUCCESS_QSS = f"""
QPushButton {{
    background-color: {GOOD_HEX};
    color: #0B1F17;
    border: none;
    border-radius: 6px;
    padding: 7px 18px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: #34D399; }}
QPushButton:disabled {{ background-color: #274038; color: #5C7A6E; }}
"""

# Applied app-wide via QApplication.setPalette() so every native widget
# (QLineEdit, QComboBox, QScrollBar, QMenu, etc.) picks up dark colors
# without needing a hand-written QSS rule for each widget class.
def apply_dark_palette(app) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG_SOFT))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_ELEVATED))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(BG_ELEVATED))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(BG_ELEVATED))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(DANGER))
    palette.setColor(QPalette.ColorRole.Link, QColor(PRIMARY_HOVER))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(PRIMARY))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_FAINT))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(TEXT_FAINT))
    app.setPalette(palette)
    app.setStyleSheet(f"""
        QToolTip {{ color: {TEXT_PRIMARY}; background-color: {BG_ELEVATED}; border: 1px solid {BORDER}; }}
        QScrollBar:vertical, QScrollBar:horizontal {{ background: {BG}; border: none; }}
        QScrollBar::handle {{ background: {BORDER}; border-radius: 5px; }}
        QScrollBar::handle:hover {{ background: {TEXT_FAINT}; }}
        QHeaderView::section {{ background: {BG_ELEVATED}; color: {TEXT_SECONDARY}; border: 1px solid {BORDER}; padding: 4px; }}
        QTableView, QTreeView, QListView {{ background: {BG_SOFT}; alternate-background-color: {BG_ELEVATED}; gridline-color: {BORDER}; }}
        QTabWidget::pane {{ border: 1px solid {BORDER}; background: {BG}; }}
        QTabBar::tab {{ background: {BG_ELEVATED}; color: {TEXT_SECONDARY}; padding: 7px 14px; }}
        QTabBar::tab:selected {{ background: {BG}; color: {TEXT_PRIMARY}; }}
        QMenuBar, QMenu {{ background: {BG_ELEVATED}; color: {TEXT_PRIMARY}; }}
        QMenu::item:selected {{ background: {PRIMARY}; }}
    """)


def severity_hex(severity: IssueSeverity | None) -> str:
    if severity is None:
        return GOOD_HEX
    return SEVERITY_HEX[severity]
