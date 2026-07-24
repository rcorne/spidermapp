from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from spidermapp.core import history
from spidermapp.gui import theme


class HistoryDialog(QDialog):
    """Browse saved crawls (~/.spidermapp/history). Selecting one and pressing
    'Abrir' loads it; selecting two and pressing 'Comparar' diffs them."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Historial de crawls")
        self.resize(760, 480)
        self.selected_path = None
        self.compare_paths: tuple | None = None

        layout = QVBoxLayout(self)

        hint = QLabel("Selecciona un crawl y ábrelo, o selecciona dos (Cmd+clic) para compararlos.")
        hint.setStyleSheet("color: #C3C7D1; font-size: 12px;")
        layout.addWidget(hint)

        content_row = QHBoxLayout()

        compare_col = QVBoxLayout()
        self.compare_button = QPushButton("Comparar\nseleccionados")
        self.compare_button.setStyleSheet(theme.BUTTON_SUCCESS_QSS)
        self.compare_button.setMinimumWidth(120)
        self.compare_button.setMinimumHeight(56)
        self.compare_button.clicked.connect(self._compare_selected)
        compare_col.addWidget(self.compare_button)
        compare_col.addStretch(1)
        content_row.addLayout(compare_col)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Sitio", "Fecha", "Páginas", "Recuperable"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 300)
        self.table.setColumnWidth(1, 160)
        content_row.addWidget(self.table, stretch=1)
        layout.addLayout(content_row, stretch=1)

        self._entries = history.list_all_snapshots()
        self.table.setRowCount(len(self._entries))
        for row, entry in enumerate(self._entries):
            when = datetime.fromtimestamp(entry["timestamp"]).strftime("%d/%m/%Y %H:%M") if entry["timestamp"] else "—"
            self.table.setItem(row, 0, QTableWidgetItem(entry["seed_url"]))
            self.table.setItem(row, 1, QTableWidgetItem(when))
            self.table.setItem(row, 2, QTableWidgetItem(str(entry["page_count"])))
            self.table.setItem(row, 3, QTableWidgetItem("Sí" if entry["has_full"] else "Solo comparación"))

        buttons_row = QHBoxLayout()
        self.open_button = QPushButton("Abrir crawl")
        self.open_button.setStyleSheet(theme.BUTTON_PRIMARY_QSS)
        self.open_button.clicked.connect(self._open_selected)
        buttons_row.addWidget(self.open_button)

        buttons_row.addStretch(1)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        buttons_row.addWidget(close)
        layout.addLayout(buttons_row)

    def _selected_rows(self) -> list[int]:
        return sorted({index.row() for index in self.table.selectionModel().selectedRows()})

    def _open_selected(self) -> None:
        rows = self._selected_rows()
        if len(rows) != 1:
            return
        self.selected_path = self._entries[rows[0]]["path"]
        self.accept()

    def _compare_selected(self) -> None:
        rows = self._selected_rows()
        if len(rows) != 2:
            return
        self.compare_paths = (self._entries[rows[0]]["path"], self._entries[rows[1]]["path"])
        self.accept()
