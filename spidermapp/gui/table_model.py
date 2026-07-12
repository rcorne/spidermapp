from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor

from spidermapp.core.models import IssueCategory, IssueSeverity, PageResult
from spidermapp.gui import theme

COLUMNS = [
    ("URL", "url"),
    ("Código", "status_code"),
    ("Indexable", "indexable"),
    ("Title", "title"),
    ("Long. Title", "title_len"),
    ("Meta Description", "meta_description"),
    ("Long. Meta", "meta_len"),
    ("H1", "h1"),
    ("Palabras", "word_count"),
    ("Canonical", "canonical"),
    ("Profundidad", "depth"),
    ("Keywords objetivo", "keywords"),
    ("En sitemap", "in_sitemap"),
    ("Tecnología", "tech"),
    ("Issues", "issue_count"),
    ("Máx. severidad", "max_severity"),
]

_SEVERITY_ORDER = {IssueSeverity.CRITICAL: 3, IssueSeverity.WARNING: 2, IssueSeverity.INFO: 1}
_SEVERITY_LABEL = {IssueSeverity.CRITICAL: "Crítico", IssueSeverity.WARNING: "Advertencia", IssueSeverity.INFO: "Info"}
_SEVERITY_TEXT_COLOR = {
    IssueSeverity.CRITICAL: QColor(theme.CRITICAL_HEX),
    IssueSeverity.WARNING: QColor(theme.WARNING_HEX),
    IssueSeverity.INFO: QColor(theme.INFO_HEX),
}
_SEVERITY_ROW_TINT = {
    IssueSeverity.CRITICAL: QColor(254, 242, 242),
    IssueSeverity.WARNING: QColor(255, 251, 235),
    IssueSeverity.INFO: QColor(239, 246, 255),
}
_GOOD_TEXT_COLOR = QColor(theme.GOOD_HEX)
_CRITICAL_TEXT_COLOR = QColor(theme.CRITICAL_HEX)


def _max_severity(page: PageResult) -> IssueSeverity | None:
    if not page.issues:
        return None
    return max((i.severity for i in page.issues), key=lambda s: _SEVERITY_ORDER[s])


class PageTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pages: list[PageResult] = []
        self._index_by_url: dict[str, int] = {}

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._pages)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section][0]
        return section + 1

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        page = self._pages[index.row()]
        _, key = COLUMNS[index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(page, key)

        if role == Qt.ItemDataRole.BackgroundRole:
            severity = _max_severity(page)
            if severity is not None:
                return _SEVERITY_ROW_TINT[severity]
            return None

        if role == Qt.ItemDataRole.ForegroundRole:
            if key == "max_severity":
                severity = _max_severity(page)
                if severity is not None:
                    return _SEVERITY_TEXT_COLOR[severity]
            if key == "indexable":
                return _GOOD_TEXT_COLOR if page.is_indexable else _CRITICAL_TEXT_COLOR

        return None

    def _display_value(self, page: PageResult, key: str):
        if key == "url":
            prefix = "🕸 " if page.is_orphan else ""
            return prefix + page.url
        if key == "status_code":
            return page.status_code if page.status_code is not None else "—"
        if key == "indexable":
            return "Sí" if page.is_indexable else "No"
        if key == "title":
            return page.title
        if key == "title_len":
            return len(page.title)
        if key == "meta_description":
            return page.meta_description
        if key == "meta_len":
            return len(page.meta_description)
        if key == "h1":
            return " | ".join(page.h1)
        if key == "word_count":
            return page.word_count
        if key == "canonical":
            return page.canonical
        if key == "depth":
            return page.depth
        if key == "keywords":
            return ", ".join(page.keywords)
        if key == "in_sitemap":
            return "Sí" if page.in_sitemap else "No"
        if key == "tech":
            return ", ".join(page.tech)
        if key == "issue_count":
            return len(page.issues)
        if key == "max_severity":
            severity = _max_severity(page)
            return _SEVERITY_LABEL[severity] if severity else "Sin issues"
        return ""

    def page_at(self, row: int) -> PageResult | None:
        if 0 <= row < len(self._pages):
            return self._pages[row]
        return None

    def all_pages(self) -> list[PageResult]:
        return list(self._pages)

    def upsert_page(self, page: PageResult) -> None:
        existing_row = self._index_by_url.get(page.url)
        if existing_row is not None:
            self._pages[existing_row] = page
            top_left = self.index(existing_row, 0)
            bottom_right = self.index(existing_row, len(COLUMNS) - 1)
            self.dataChanged.emit(top_left, bottom_right)
            return

        row = len(self._pages)
        self.beginInsertRows(QModelIndex(), row, row)
        self._pages.append(page)
        self._index_by_url[page.url] = row
        self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._pages = []
        self._index_by_url = {}
        self.endResetModel()


class IssueFilterProxyModel(QSortFilterProxyModel):
    """Filters rows by sidebar selection: all pages, only pages with any
    issue, orphan pages, duplicate-content pages, or pages with an issue in
    a specific IssueCategory."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode: str = "all"
        self._category: IssueCategory | None = None
        self.setSortRole(Qt.ItemDataRole.DisplayRole)

    def set_filter_all(self) -> None:
        self._mode = "all"
        self._category = None
        self.invalidateFilter()

    def set_filter_any_issue(self) -> None:
        self._mode = "issues"
        self._category = None
        self.invalidateFilter()

    def set_filter_orphans(self) -> None:
        self._mode = "orphans"
        self._category = None
        self.invalidateFilter()

    def set_filter_duplicates(self) -> None:
        self._mode = "duplicates"
        self._category = IssueCategory.DUPLICATES
        self.invalidateFilter()

    def set_filter_category(self, category: IssueCategory) -> None:
        self._mode = "category"
        self._category = category
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if self._mode == "all":
            return True
        source: PageTableModel = self.sourceModel()
        page = source.page_at(source_row)
        if page is None:
            return True
        if self._mode == "issues":
            return len(page.issues) > 0
        if self._mode == "orphans":
            return page.is_orphan
        if self._mode in ("category", "duplicates"):
            return any(i.category == self._category for i in page.issues)
        return True
