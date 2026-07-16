from __future__ import annotations

from PySide6.QtGui import QColor

from spidermapp.core.models import IssueSeverity

PRIMARY = "#4F46E5"
PRIMARY_HOVER = "#4338CA"
PRIMARY_PRESSED = "#3730A3"
PRIMARY_SOFT = "#EEF2FF"

DANGER = "#DC2626"
DANGER_HOVER = "#B91C1C"
DANGER_SOFT = "#FEF2F2"

GOOD_HEX = "#059669"
CRITICAL_HEX = "#DC2626"
WARNING_HEX = "#D97706"
INFO_HEX = "#2563EB"

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
QPushButton:disabled {{ background-color: #B7B6E8; color: #F1F1FB; }}
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
QPushButton:disabled {{ background-color: #F0B4B4; color: #FFF5F5; }}
"""

BUTTON_SECONDARY_QSS = f"""
QPushButton {{
    background-color: white;
    color: {PRIMARY};
    border: 1.5px solid {PRIMARY};
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: {PRIMARY_SOFT}; }}
QPushButton:disabled {{ color: #B7B6E8; border-color: #D8D9EC; background-color: white; }}
"""

BUTTON_SUCCESS_QSS = f"""
QPushButton {{
    background-color: {GOOD_HEX};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 7px 18px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: #047857; }}
QPushButton:disabled {{ background-color: #A7D9C7; color: #F0FDF9; }}
"""


def severity_hex(severity: IssueSeverity | None) -> str:
    if severity is None:
        return GOOD_HEX
    return SEVERITY_HEX[severity]
