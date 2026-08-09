from __future__ import annotations

from PySide6.QtGui import QColor, QPalette

from spidermapp.core.models import IssueSeverity

# Two themes, switched at startup (Preferencias → General, or the toggle
# next to the login button) via set_mode(). Every color below is a plain
# module attribute rather than a fixed constant so widget code can do
# `theme.BG` etc. and always see whichever theme is currently active —
# set_mode() just reassigns these names in place.

_DARK = {
    # Teams-inspired icon rail, green-leaning instead of Teams' purple.
    "BG": "#101512",
    "BG_ELEVATED": "#171F1B",
    "BG_SOFT": "#1B2420",
    "BG_CHIP": "#212B25",
    "BORDER": "#28332C",
    "TEXT_PRIMARY": "#E7EDE9",
    "TEXT_SECONDARY": "#C1CCC5",
    "TEXT_MUTED": "#93A69C",
    "TEXT_FAINT": "#748076",
    "PRIMARY": "#2FBE81",
    "PRIMARY_HOVER": "#4FD59B",
    "PRIMARY_PRESSED": "#22995F",
    "PRIMARY_SOFT": "#1B3A2C",
    "DANGER": "#EF4444",
    "DANGER_HOVER": "#F87171",
    "DANGER_SOFT": "#3A2226",
    "GOOD_HEX": "#2FBE81",
    "CRITICAL_HEX": "#F87171",
    "WARNING_HEX": "#FBBF24",
    "INFO_HEX": "#60A5FA",
    "RAIL_BG": "#0B0F0D",
    "RAIL_BORDER": "#1C2620",
    "RAIL_TEXT": "#8CA096",
    "RAIL_TEXT_ACTIVE": "#EAF5EF",
    "RAIL_HOVER": "#182019",
    "BUTTON_DISABLED_BG": "#33364A",
    "BUTTON_DISABLED_TEXT": "#6B7080",
    "DANGER_DISABLED_BG": "#4A2E30",
    "DANGER_DISABLED_TEXT": "#8A6B6C",
    "SECONDARY_DISABLED_TEXT": "#565A6E",
    "SUCCESS_TEXT": "#0B1F17",
    "SUCCESS_HOVER": "#34D399",
    "SUCCESS_DISABLED_BG": "#274038",
    "SUCCESS_DISABLED_TEXT": "#5C7A6E",
}

# SEMrush/HubSpot-style light SaaS dashboard: white cards on a soft gray
# canvas, a lot of whitespace, a deep green accent (same hue family as the
# dark theme, darkened for AA contrast on white) instead of copying their
# literal orange/purple.
_LIGHT = {
    "BG": "#F4F6F5",
    "BG_ELEVATED": "#FFFFFF",
    "BG_SOFT": "#FFFFFF",
    "BG_CHIP": "#EEF2F0",
    "BORDER": "#E1E6E3",
    "TEXT_PRIMARY": "#16211C",
    "TEXT_SECONDARY": "#3F4B45",
    "TEXT_MUTED": "#66756E",
    "TEXT_FAINT": "#8B9992",
    "PRIMARY": "#178A5A",
    "PRIMARY_HOVER": "#14764C",
    "PRIMARY_PRESSED": "#0F5C3C",
    "PRIMARY_SOFT": "#E4F4EC",
    "DANGER": "#DC2626",
    "DANGER_HOVER": "#B91C1C",
    "DANGER_SOFT": "#FEF2F2",
    "GOOD_HEX": "#178A5A",
    "CRITICAL_HEX": "#DC2626",
    "WARNING_HEX": "#D97706",
    "INFO_HEX": "#2563EB",
    "RAIL_BG": "#FFFFFF",
    "RAIL_BORDER": "#E1E6E3",
    "RAIL_TEXT": "#66756E",
    "RAIL_TEXT_ACTIVE": "#16211C",
    "RAIL_HOVER": "#EEF2F0",
    "BUTTON_DISABLED_BG": "#D8DEDA",
    "BUTTON_DISABLED_TEXT": "#9AA6A0",
    "DANGER_DISABLED_BG": "#F7D5D5",
    "DANGER_DISABLED_TEXT": "#B98F8F",
    "SECONDARY_DISABLED_TEXT": "#AEB8B3",
    "SUCCESS_TEXT": "#FFFFFF",
    "SUCCESS_HOVER": "#14764C",
    "SUCCESS_DISABLED_BG": "#D8ECE2",
    "SUCCESS_DISABLED_TEXT": "#9AC2AC",
}

_PALETTES = {"dark": _DARK, "light": _LIGHT}
CURRENT_MODE = "dark"


def set_mode(mode: str) -> None:
    """Switches the active theme by reassigning every color/QSS name this
    module exposes. Call once at startup, before any widget is built —
    widgets read `theme.BG` etc. live at construction time, so anything
    built after this call picks up the new theme; anything built before
    stays on the old one (which is why a runtime toggle asks for a
    restart instead of trying to re-skin live widgets)."""
    global CURRENT_MODE
    palette = _PALETTES.get(mode, _DARK)
    CURRENT_MODE = "light" if mode == "light" else "dark"
    globals().update(palette)
    _build_derived()


def _build_derived() -> None:
    global SEVERITY_HEX, SEVERITY_COLOR, GOOD_COLOR, RAIL_ACTIVE_BG
    global BUTTON_PRIMARY_QSS, BUTTON_DANGER_QSS, BUTTON_SECONDARY_QSS, BUTTON_SUCCESS_QSS

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
    QPushButton:disabled {{ background-color: {BUTTON_DISABLED_BG}; color: {BUTTON_DISABLED_TEXT}; }}
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
    QPushButton:disabled {{ background-color: {DANGER_DISABLED_BG}; color: {DANGER_DISABLED_TEXT}; }}
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
    QPushButton:disabled {{ color: {SECONDARY_DISABLED_TEXT}; border-color: {BORDER}; background-color: {BG_ELEVATED}; }}
    """

    BUTTON_SUCCESS_QSS = f"""
    QPushButton {{
        background-color: {GOOD_HEX};
        color: {SUCCESS_TEXT};
        border: none;
        border-radius: 6px;
        padding: 7px 18px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background-color: {SUCCESS_HOVER}; }}
    QPushButton:disabled {{ background-color: {SUCCESS_DISABLED_BG}; color: {SUCCESS_DISABLED_TEXT}; }}
    """


# Applied app-wide via QApplication.setPalette() so every native widget
# (QLineEdit, QComboBox, QScrollBar, QMenu, etc.) picks up the active
# theme's colors without a hand-written QSS rule for each widget class.
def apply_palette(app, mode: str = "dark") -> None:
    set_mode(mode)
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


set_mode("dark")  # module-load default; apply_palette() overrides at startup per saved settings
