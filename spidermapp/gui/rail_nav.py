from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QSizePolicy, QVBoxLayout, QWidget

from spidermapp.gui import theme

# Icon-rail navigation modeled on Microsoft Teams' left-edge app bar: a
# narrow vertical strip of glyph+label buttons, the active one picked out
# with a filled rounded highlight rather than a plain underline/border.
RAIL_ITEMS = [
    ("hoy", "◆", "Hoy"),
    ("auditoria", "▤", "Auditoría"),
    ("tablero", "▦", "Tablero"),
    ("chat", "◈", "Chat"),
]

_INACTIVE_QSS = f"""
QPushButton {{
    background: transparent;
    color: {theme.RAIL_TEXT};
    border: none;
    border-radius: 10px;
    padding: 10px 4px 8px 4px;
    font-weight: 600;
    font-size: 10px;
    text-align: center;
}}
QPushButton:hover {{ background: {theme.RAIL_HOVER}; color: {theme.RAIL_TEXT_ACTIVE}; }}
"""

_ACTIVE_QSS = f"""
QPushButton {{
    background: {theme.RAIL_ACTIVE_BG};
    color: {theme.RAIL_TEXT_ACTIVE};
    border: none;
    border-radius: 10px;
    padding: 10px 4px 8px 4px;
    font-weight: 700;
    font-size: 10px;
    text-align: center;
}}
"""


class RailNav(QWidget):
    """The left-edge, icon-rail-style navigation from the UX redesign:
    task-first views (Hoy / Auditoría / Tablero / Chat) instead of a flat
    row of equal-weight tabs. "Auditoría" hosts every existing crawl view
    (Vista general, Mapa, Estructura, Tabla, Visibilidad IA, Noticias)
    unchanged — this only changes what sits above them."""

    view_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(72)
        self.setStyleSheet(f"background: {theme.RAIL_BG}; border-right: 1px solid {theme.RAIL_BORDER};")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 12)
        layout.setSpacing(6)

        self._buttons: dict[str, QPushButton] = {}
        for key, glyph, label in RAIL_ITEMS:
            button = QPushButton(f"{glyph}\n{label}")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(_INACTIVE_QSS)
            button.setToolTip(label)
            button.clicked.connect(lambda _checked=False, k=key: self.set_active(k))
            layout.addWidget(button)
            self._buttons[key] = button

        layout.addStretch(1)
        self._active = RAIL_ITEMS[0][0]
        self.set_active(self._active, emit=False)

    def set_active(self, key: str, emit: bool = True) -> None:
        if key not in self._buttons:
            return
        self._active = key
        for k, button in self._buttons.items():
            button.setStyleSheet(_ACTIVE_QSS if k == key else _INACTIVE_QSS)
        if emit:
            self.view_changed.emit(key)

    @property
    def active(self) -> str:
        return self._active
