from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QSizePolicy, QVBoxLayout, QWidget

from spidermapp.gui import theme

RAIL_ITEMS = [
    ("hoy", "Hoy"),
    ("auditoria", "Auditoría"),
    ("tablero", "Tablero"),
]

_INACTIVE_QSS = f"""
QPushButton {{
    background: transparent;
    color: #C7CCD8;
    border: none;
    border-radius: 8px;
    padding: 10px 6px;
    font-weight: 600;
    font-size: 11px;
    text-align: center;
}}
QPushButton:hover {{ background: #232A33; color: #E7EAEE; }}
"""

_ACTIVE_QSS = f"""
QPushButton {{
    background: #232A33;
    color: #E7EAEE;
    border: none;
    border-left: 3px solid {theme.PRIMARY};
    border-radius: 8px;
    padding: 10px 6px 10px 3px;
    font-weight: 700;
    font-size: 11px;
    text-align: center;
}}
"""


class RailNav(QWidget):
    """The left-edge, icon-rail-style navigation from the UX redesign:
    task-first views (Hoy / Auditoría / Tablero) instead of a flat row of
    equal-weight tabs. "Auditoría" hosts every existing crawl view
    (Vista general, Mapa, Estructura, Tabla, Visibilidad IA, Noticias)
    unchanged — this only changes what sits above them."""

    view_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(74)
        self.setStyleSheet("background: #171B21; border-right: 1px solid #262C35;")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 12)
        layout.setSpacing(4)

        self._buttons: dict[str, QPushButton] = {}
        for key, label in RAIL_ITEMS:
            button = QPushButton(label)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(_INACTIVE_QSS)
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
