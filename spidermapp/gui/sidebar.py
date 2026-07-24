from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QWidget

from spidermapp.core.models import IssueCategory, PageResult
from spidermapp.gui import theme
from spidermapp.gui.dashboard import StackedBar

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

ALL_KEY = "__all__"
ISSUES_KEY = "__issues__"
ORPHANS_KEY = "__orphans__"
DUPLICATES_KEY = "__duplicates__"


class SidebarRow(QWidget):
    def __init__(self, label_text: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)

        self.label = QLabel(label_text)
        self.label.setStyleSheet("font-size: 12.5px; color: #C3C7D1;")

        self.bar = StackedBar()
        self.bar.setFixedWidth(52)

        self.count = QLabel("0")
        self.count.setStyleSheet("font-size: 11px; color: #9AA1AE;")
        self.count.setFixedWidth(26)
        self.count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self.label, stretch=1)
        layout.addWidget(self.bar)
        layout.addWidget(self.count)

    def set_value(self, segments: list[tuple[int, QColor]], max_total: int, count_text: str) -> None:
        self.bar.set_data(segments, max_total)
        self.count.setText(count_text)


class Sidebar(QListWidget):
    selection_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSpacing(1)
        self._rows: dict[str, tuple[QListWidgetItem, SidebarRow]] = {}
        self._build_items()
        self.currentItemChanged.connect(self._on_selection_changed)

    def _build_items(self) -> None:
        self.clear()
        self._rows.clear()
        self._add_item(ALL_KEY, "Todas las páginas")
        self._add_item(ISSUES_KEY, "Con issues")
        self._add_item(ORPHANS_KEY, "Páginas huérfanas")
        self._add_item(DUPLICATES_KEY, "Contenido duplicado")
        for category, label in CATEGORY_LABELS.items():
            self._add_item(category.value, label)
        self.setCurrentRow(0)

    def _add_item(self, key: str, label: str) -> None:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, key)
        row = SidebarRow(label)
        item.setSizeHint(row.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, row)
        self._rows[key] = (item, row)

    def _on_selection_changed(self, current: QListWidgetItem, _previous) -> None:
        if current is None:
            return
        self.selection_changed.emit(current.data(Qt.ItemDataRole.UserRole))

    def refresh_counts(self, pages: list[PageResult]) -> None:
        total = len(pages)
        denom = max(total, 1)

        with_issues = sum(1 for p in pages if p.issues)
        orphans = sum(1 for p in pages if p.is_orphan)
        duplicates = sum(1 for p in pages if any(i.category == IssueCategory.DUPLICATES for i in p.issues))

        self._rows[ALL_KEY][1].set_value([(total, QColor(theme.PRIMARY))], denom, str(total))
        self._rows[ISSUES_KEY][1].set_value([(with_issues, QColor(theme.CRITICAL_HEX))], denom, str(with_issues))
        self._rows[ORPHANS_KEY][1].set_value([(orphans, QColor(theme.WARNING_HEX))], denom, str(orphans))
        self._rows[DUPLICATES_KEY][1].set_value([(duplicates, QColor(theme.WARNING_HEX))], denom, str(duplicates))

        category_counts = {c: {"critical": 0, "warning": 0, "info": 0} for c in IssueCategory}
        for page in pages:
            for issue in page.issues:
                category_counts[issue.category][issue.severity.value] += 1

        max_cat_total = max((sum(v.values()) for v in category_counts.values()), default=1) or 1
        for category, counts in category_counts.items():
            key = category.value
            if key not in self._rows:
                continue
            segments = [
                (counts["critical"], QColor(theme.CRITICAL_HEX)),
                (counts["warning"], QColor(theme.WARNING_HEX)),
                (counts["info"], QColor(theme.INFO_HEX)),
            ]
            self._rows[key][1].set_value(segments, max_cat_total, str(sum(counts.values())))
