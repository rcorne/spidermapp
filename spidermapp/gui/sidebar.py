from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from spidermapp.core.models import IssueCategory, PageResult

CATEGORY_LABELS: dict[IssueCategory, str] = {
    IssueCategory.RESPONSE_CODES: "Códigos de respuesta",
    IssueCategory.TITLES: "Titles",
    IssueCategory.META: "Meta / H1 / Contenido",
    IssueCategory.CANONICALS: "Canonicals",
    IssueCategory.DIRECTIVES: "Directivas (noindex/nofollow)",
    IssueCategory.LINKS: "Enlaces",
    IssueCategory.SITEMAP_ROBOTS: "Sitemap / robots.txt",
    IssueCategory.SECURITY: "Seguridad (HTTPS/www)",
    IssueCategory.REDIRECTS: "Redirects",
    IssueCategory.DUPLICATES: "Contenido duplicado",
    IssueCategory.URL_CONVENTIONS: "Convenciones de URL",
    IssueCategory.RENDERING: "Renderizado / Mobile vs Desktop",
    IssueCategory.TECH: "CMS / Tecnologías",
}

_ALL_KEY = "__all__"
_ISSUES_KEY = "__issues__"


class Sidebar(QListWidget):
    selection_changed = Signal(str)  # "__all__", "__issues__", or IssueCategory.value

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_items()
        self.currentItemChanged.connect(self._on_selection_changed)

    def _build_items(self) -> None:
        self.clear()
        self._add_item("Todas las páginas", _ALL_KEY)
        self._add_item("Con issues", _ISSUES_KEY)
        for category, label in CATEGORY_LABELS.items():
            self._add_item(label, category.value)
        self.setCurrentRow(0)

    def _add_item(self, label: str, key: str) -> None:
        item = QListWidgetItem(label)
        item.setData(32, key)  # Qt.ItemDataRole.UserRole == 32
        self.addItem(item)

    def _on_selection_changed(self, current: QListWidgetItem, _previous) -> None:
        if current is None:
            return
        self.selection_changed.emit(current.data(32))

    def refresh_counts(self, pages: list[PageResult]) -> None:
        total_with_issues = sum(1 for p in pages if p.issues)
        counts: dict[str, int] = {c.value: 0 for c in CATEGORY_LABELS}
        for page in pages:
            seen_categories = {i.category.value for i in page.issues}
            for cat_value in seen_categories:
                counts[cat_value] = counts.get(cat_value, 0) + 1

        for i in range(self.count()):
            item = self.item(i)
            key = item.data(32)
            if key == _ALL_KEY:
                item.setText(f"Todas las páginas ({len(pages)})")
            elif key == _ISSUES_KEY:
                item.setText(f"Con issues ({total_with_issues})")
            else:
                category = IssueCategory(key)
                label = CATEGORY_LABELS[category]
                item.setText(f"{label} ({counts.get(key, 0)})")
