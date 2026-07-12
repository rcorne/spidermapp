from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from spidermapp.core.models import PageResult
from spidermapp.core.site_structure import StructureNode, build_site_tree
from spidermapp.gui import theme
from spidermapp.gui.table_model import _max_severity


class StructureTab(QWidget):
    """Domain → subdomain → path tree of the whole site (point 2)."""

    node_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(
            "Estructura del dominio: subdominios y jerarquía de rutas. "
            "Doble clic en un nodo rastreado abre su detalle en la Tabla."
        )
        header.setStyleSheet("padding: 8px 14px; font-size: 11.5px; color: #4B5563; background: #F9FAFB; border-bottom: 1px solid #E5E7EB;")
        layout.addWidget(header)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Sección", "URL", "Código", "Issues"])
        self.tree.setColumnWidth(0, 340)
        self.tree.setColumnWidth(1, 420)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.tree, stretch=1)

    def set_pages(self, pages: list[PageResult], seed_url: str) -> None:
        self.tree.clear()
        if not pages:
            return
        root = build_site_tree(pages, seed_url)

        def add_node(parent_item, node: StructureNode) -> None:
            for label in sorted(node.children):
                child = node.children[label]
                item = QTreeWidgetItem(parent_item)
                item.setText(0, child.label)
                item.setText(1, child.url)
                if child.page is not None:
                    item.setText(2, str(child.page.status_code) if child.page.status_code is not None else "—")
                    item.setText(3, str(len(child.page.issues)))
                    severity = _max_severity(child.page)
                    if severity is not None:
                        item.setForeground(0, QColor(theme.SEVERITY_HEX[severity]))
                    else:
                        item.setForeground(0, theme.GOOD_COLOR)
                    item.setData(0, Qt.ItemDataRole.UserRole, child.page.url)
                else:
                    item.setForeground(0, QColor("#9CA3AF"))
                    item.setToolTip(0, "Descubierta por enlaces, no rastreada")
                add_node(item, child)

        add_node(self.tree, root)
        self.tree.expandToDepth(1)

    def _on_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        url = item.data(0, Qt.ItemDataRole.UserRole)
        if url:
            self.node_clicked.emit(url)
