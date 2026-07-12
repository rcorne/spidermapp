from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import stats
from spidermapp.core.models import PageResult
from spidermapp.gui import theme

RING_TRACK_COLOR = QColor("#E5E7EB")


def _score_color(score: int) -> QColor:
    if score < 50:
        return QColor(theme.CRITICAL_HEX)
    if score < 80:
        return QColor(theme.WARNING_HEX)
    return theme.GOOD_COLOR


class HealthScoreRing(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._score = 100
        self.setMinimumSize(140, 140)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_score(self, score: int) -> None:
        self._score = score
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height()) - 16
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)

        track_pen = QPen(RING_TRACK_COLOR, 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)

        color = _score_color(self._score)
        progress_pen = QPen(color, 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(progress_pen)
        span = int(360 * 16 * (self._score / 100))
        painter.drawArc(rect, 90 * 16, -span)

        painter.setPen(QColor("#111827"))
        font = QFont(self.font())
        font.setPointSize(22)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self._score))


class StackedBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._segments: list[tuple[int, QColor]] = []
        self._max_total = 1
        self.setFixedHeight(10)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, segments: list[tuple[int, QColor]], max_total: int) -> None:
        self._segments = segments
        self._max_total = max(max_total, 1)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#EEF0F2"))
        painter.drawRoundedRect(0, 0, w, h, h / 2, h / 2)

        total = sum(v for v, _ in self._segments)
        if total <= 0:
            return
        x = 0.0
        full_width = w * (total / self._max_total)
        for value, color in self._segments:
            if value <= 0:
                continue
            seg_w = full_width * (value / total)
            painter.setBrush(color)
            painter.drawRect(int(x), 0, int(seg_w) + 1, h)
            x += seg_w
        painter.setBrush(Qt.BrushStyle.NoBrush)


def _stat_box(value_text: str, label_text: str, color: str = "#111827") -> QWidget:
    box = QFrame()
    box.setFrameShape(QFrame.Shape.NoFrame)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(2)

    value = QLabel(value_text)
    value.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {color};")
    label = QLabel(label_text)
    label.setStyleSheet("font-size: 11px; color: #6B7280;")

    layout.addWidget(value)
    layout.addWidget(label)
    return box


class DashboardTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(20)

        top_row = QHBoxLayout()
        top_row.setSpacing(24)

        score_box = QVBoxLayout()
        self.ring = HealthScoreRing()
        score_box.addWidget(self.ring, alignment=Qt.AlignmentFlag.AlignHCenter)
        score_caption = QLabel("Salud del sitio")
        score_caption.setStyleSheet("font-size: 12px; color: #6B7280;")
        score_caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        score_box.addWidget(score_caption)
        top_row.addLayout(score_box)

        budget_grid = QGridLayout()
        budget_grid.setHorizontalSpacing(28)
        budget_grid.setVerticalSpacing(10)
        self.stat_total = _stat_box("0", "Páginas rastreadas")
        self.stat_ok = _stat_box("0", "OK", theme.GOOD_HEX)
        self.stat_errors = _stat_box("0", "Errores", theme.CRITICAL_HEX)
        self.stat_blocked = _stat_box("0", "Bloqueadas (robots.txt)")
        self.stat_duplicates = _stat_box("0", "Contenido duplicado", theme.WARNING_HEX)
        self.stat_orphans = _stat_box("0", "Páginas huérfanas", theme.WARNING_HEX)
        for i, box in enumerate(
            (self.stat_total, self.stat_ok, self.stat_errors, self.stat_blocked, self.stat_duplicates, self.stat_orphans)
        ):
            budget_grid.addWidget(box, i // 3, i % 3)
        top_row.addLayout(budget_grid, stretch=1)
        root.addLayout(top_row)

        cat_header = QLabel("Issues por categoría")
        cat_header.setStyleSheet("font-size: 13px; font-weight: 700; color: #111827; margin-top: 8px;")
        root.addWidget(cat_header)

        self.category_grid = QGridLayout()
        self.category_grid.setHorizontalSpacing(12)
        self.category_grid.setVerticalSpacing(8)
        root.addLayout(self.category_grid)
        self._category_rows: list[tuple[QLabel, StackedBar, QLabel]] = []

        offenders_header = QLabel("Top ofensores")
        offenders_header.setStyleSheet("font-size: 13px; font-weight: 700; color: #111827; margin-top: 12px;")
        root.addWidget(offenders_header)

        self.offenders_list = QListWidget()
        self.offenders_list.setMaximumHeight(180)
        root.addWidget(self.offenders_list)

        root.addStretch(1)

    def update_data(self, pages: list[PageResult], priority_urls: set[str] | None = None) -> None:
        priority_urls = priority_urls or set()
        score = stats.health_score(pages, priority_urls)
        self.ring.set_score(score)

        budget = stats.compute_crawl_budget(pages)
        self._set_stat(self.stat_total, str(budget.total_pages))
        self._set_stat(self.stat_ok, str(budget.ok_pages))
        self._set_stat(self.stat_errors, str(budget.error_pages))
        self._set_stat(self.stat_blocked, str(budget.blocked_by_robots))
        self._set_stat(self.stat_duplicates, str(budget.duplicate_pages))
        self._set_stat(self.stat_orphans, str(budget.orphan_pages))

        self._update_categories(stats.category_breakdown(pages))
        self._update_offenders(stats.top_offenders(pages, limit=8))

    @staticmethod
    def _set_stat(box: QWidget, text: str) -> None:
        value_label = box.layout().itemAt(0).widget()
        value_label.setText(text)

    def _update_categories(self, breakdown: list[stats.CategoryBreakdown]) -> None:
        while self.category_grid.count():
            item = self.category_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._category_rows.clear()

        if not breakdown:
            empty = QLabel("Sin issues detectados en este crawl.")
            empty.setStyleSheet("color: #6B7280; font-size: 12px;")
            self.category_grid.addWidget(empty, 0, 0)
            return

        max_total = max(b.total for b in breakdown)
        from spidermapp.gui.sidebar import CATEGORY_LABELS

        for row, bucket in enumerate(breakdown):
            name = QLabel(CATEGORY_LABELS.get(bucket.category, bucket.category.value))
            name.setStyleSheet("font-size: 12px; color: #374151;")
            name.setFixedWidth(190)

            bar = StackedBar()
            bar.set_data(
                [
                    (bucket.critical, QColor(theme.CRITICAL_HEX)),
                    (bucket.warning, QColor(theme.WARNING_HEX)),
                    (bucket.info, QColor(theme.INFO_HEX)),
                ],
                max_total,
            )

            count = QLabel(str(bucket.total))
            count.setStyleSheet("font-size: 12px; color: #6B7280;")
            count.setFixedWidth(28)
            count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            self.category_grid.addWidget(name, row, 0)
            self.category_grid.addWidget(bar, row, 1)
            self.category_grid.addWidget(count, row, 2)

    def _update_offenders(self, offenders: list[PageResult]) -> None:
        self.offenders_list.clear()
        if not offenders:
            item = QListWidgetItem("Sin páginas con issues.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.offenders_list.addItem(item)
            return
        for page in offenders:
            item = QListWidgetItem(f"[{len(page.issues)} issues]   {page.url}")
            item.setData(Qt.ItemDataRole.UserRole, page.url)
            self.offenders_list.addItem(item)
