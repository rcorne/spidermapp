from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core.app_settings import DEFAULT_USER_AGENT

# Shared building blocks for the "Rastreo" / "Límites" / "Avanzado" tabs in
# SettingsDialog (Archivo → Preferencias) — every crawl option lives there
# now, consolidated in one place instead of scattered across menus.

# Presets a user is likely to want without typing a full UA string by hand.
# "Personalizado" leaves the field free-text.
USER_AGENT_PRESETS = {
    "Spidermapp (por defecto)": DEFAULT_USER_AGENT,
    "Googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Bingbot": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Chrome de escritorio": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


def hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("font-size: 11px; color: #6B7280; margin-bottom: 4px;")
    return label


class EditableUrlList(QWidget):
    """A QListWidget plus an add/remove row, used for both exclude patterns
    and priority URLs — the two "small list of strings" settings here."""

    def __init__(self, placeholder: str, items: list[str], parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.addItems(items)
        self.list_widget.setMaximumHeight(110)
        layout.addWidget(self.list_widget)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.returnPressed.connect(self._add)
        row.addWidget(self.input, stretch=1)

        add_btn = QPushButton("+ Añadir")
        add_btn.clicked.connect(self._add)
        row.addWidget(add_btn)

        remove_btn = QPushButton("- Quitar seleccionado")
        remove_btn.clicked.connect(self._remove_selected)
        row.addWidget(remove_btn)
        layout.addLayout(row)

    def _add(self) -> None:
        text = self.input.text().strip()
        if text:
            self.list_widget.addItem(text)
            self.input.clear()

    def _remove_selected(self) -> None:
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))

    def values(self) -> list[str]:
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
