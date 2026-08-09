from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import recommendations, stats
from spidermapp.core.models import Issue, IssueSeverity, PageResult
from spidermapp.gui import theme

RING_TRACK_COLOR = QColor(f"{theme.BORDER}")

_SEVERITY_HEX = {
    IssueSeverity.CRITICAL: theme.CRITICAL_HEX,
    IssueSeverity.WARNING: theme.WARNING_HEX,
    IssueSeverity.INFO: theme.INFO_HEX,
}


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
        self._pending = True  # no crawl has produced data yet — don't imply a score of 100
        self.setMinimumSize(140, 140)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_score(self, score: int) -> None:
        self._score = score
        self._pending = False
        self.update()

    def set_pending(self) -> None:
        self._pending = True
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height()) - 16
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)

        track_pen = QPen(RING_TRACK_COLOR, 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)

        if not self._pending:
            color = _score_color(self._score)
            progress_pen = QPen(color, 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(progress_pen)
            span = int(360 * 16 * (self._score / 100))
            painter.drawArc(rect, 90 * 16, -span)

        painter.setPen(QColor(f"{theme.TEXT_PRIMARY}") if not self._pending else QColor(f"{theme.TEXT_FAINT}"))
        font = QFont(self.font())
        font.setPointSize(22 if not self._pending else 15)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "—" if self._pending else str(self._score))


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
        painter.setBrush(QColor(f"{theme.BG_SOFT}"))
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


def _stat_box(value_text: str, label_text: str, definition_text: str = "", pending_text: str = "", color: str = f"{theme.TEXT_PRIMARY}") -> QWidget:
    box = QFrame()
    box.setFrameShape(QFrame.Shape.NoFrame)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(2)

    value = QLabel(value_text)
    value.setStyleSheet(f"font-size: 30px; font-weight: 700; color: {color};")
    label = QLabel(label_text)
    label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {theme.TEXT_SECONDARY};")

    layout.addWidget(value)
    layout.addWidget(label)

    definition = QLabel(definition_text)
    definition.setWordWrap(True)
    definition.setStyleSheet(f"font-size: 10.5px; color: {theme.TEXT_FAINT};")
    definition.setVisible(bool(definition_text))
    layout.addWidget(definition)

    box._value_label = value
    box._definition_label = definition
    box._definition_text = definition_text
    box._pending_text = pending_text or "Inicia el crawl para ver este dato."
    return box


def _set_stat_pending(box: QWidget, pending: bool) -> None:
    if pending:
        box._value_label.setText("—")
        box._definition_label.setText(box._pending_text)
    else:
        box._definition_label.setText(box._definition_text)
    box._definition_label.setVisible(True)


def _fact_pill(ok: bool, ok_text: str, bad_text: str) -> QLabel:
    text = f"✓ {ok_text}" if ok else f"✕ {bad_text}"
    color = theme.GOOD_HEX if ok else theme.CRITICAL_HEX
    bg = "#1F3A2E" if ok else "#3A2226"
    pill = QLabel(text)
    pill.setStyleSheet(
        f"color: {color}; background: {bg}; font-size: 11.5px; font-weight: 600; "
        f"padding: 4px 10px; border-radius: 10px;"
    )
    return pill


class OpportunityRow(QFrame):
    """One aggregated, fixable finding — framed as a concrete next step
    ('do X') rather than a list of pages that are somehow at fault."""

    def __init__(self, opportunity: stats.IssueOpportunity, parent=None):
        super().__init__(parent)
        color = _SEVERITY_HEX[opportunity.severity]
        rec = recommendations.get_recommendation(
            Issue(opportunity.category, opportunity.severity, opportunity.code, "")
        )

        self.setStyleSheet(
            f"OpportunityRow {{ background: {theme.BG_ELEVATED}; border: 1px solid {theme.BORDER}; border-left: 4px solid {color}; "
            f"border-radius: 4px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(3)

        header = QHBoxLayout()
        action_text = rec.fix_steps[0] if rec.fix_steps else rec.title
        action = QLabel(action_text)
        action.setTextFormat(Qt.TextFormat.PlainText)  # recommendation text may contain literal "<title>" etc.
        action.setWordWrap(True)
        action.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        header.addWidget(action, stretch=1)

        pages_word = "página" if opportunity.affected_pages == 1 else "páginas"
        badge = QLabel(f"{opportunity.affected_pages} {pages_word}")
        badge.setStyleSheet(
            f"color: {color}; background: {color}22; font-size: 11px; font-weight: 700; "
            f"padding: 2px 8px; border-radius: 8px;"
        )
        badge.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        if rec.why:
            why = QLabel(rec.why)
            why.setTextFormat(Qt.TextFormat.PlainText)
            why.setWordWrap(True)
            why.setStyleSheet(f"font-size: 11.5px; color: {theme.TEXT_MUTED};")
            layout.addWidget(why)


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

        self.start_banner = QLabel("👆 Ingresa una URL arriba y presiona \"Iniciar crawl\" para ver el análisis de tu sitio.")
        self.start_banner.setStyleSheet(
            f"background: {theme.PRIMARY_SOFT}; color: {theme.PRIMARY}; font-size: 12.5px; font-weight: 600; "
            f"padding: 10px 14px; border-radius: 6px;"
        )
        self.start_banner.setWordWrap(True)
        root.addWidget(self.start_banner)

        top_row = QHBoxLayout()
        top_row.setSpacing(24)

        score_box = QVBoxLayout()
        self.ring = HealthScoreRing()
        score_box.addWidget(self.ring, alignment=Qt.AlignmentFlag.AlignHCenter)
        score_caption = QLabel("Salud del sitio")
        score_caption.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_MUTED};")
        score_caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        score_box.addWidget(score_caption)
        top_row.addLayout(score_box)

        budget_grid = QGridLayout()
        budget_grid.setHorizontalSpacing(28)
        budget_grid.setVerticalSpacing(10)
        self.stat_total = _stat_box(
            "0", "Páginas rastreadas", "Total de URLs visitadas durante este rastreo.",
            "Inicia el crawl para empezar a contar las páginas rastreadas.",
        )
        self.stat_ok = _stat_box(
            "0", "OK", "Páginas con código 200 y sin errores críticos.",
            "Inicia el crawl para contar las páginas en condición OK.",
            theme.GOOD_HEX,
        )
        self.stat_errors = _stat_box(
            "0", "Errores", "Páginas con errores 4xx, 5xx u otros problemas críticos.",
            "Inicia el crawl para contar las páginas con errores.",
            theme.CRITICAL_HEX,
        )
        self.stat_blocked = _stat_box(
            "0", "Bloqueadas (robots.txt)", "Páginas que robots.txt le impide rastrear a los motores de búsqueda.",
            "Inicia el crawl para contar las páginas bloqueadas por robots.txt.",
        )
        self.stat_duplicates = _stat_box(
            "0", "Contenido duplicado", "Páginas con contenido prácticamente idéntico al de otra página del sitio.",
            "Inicia el crawl para contar las páginas con contenido duplicado.",
            theme.WARNING_HEX,
        )
        self.stat_orphans = _stat_box(
            "0", "Páginas huérfanas", "Páginas sin ningún enlace interno hacia ellas, encontradas solo por el sitemap.",
            "Inicia el crawl para contar las páginas huérfanas.",
            theme.WARNING_HEX,
        )
        for i, box in enumerate(
            (self.stat_total, self.stat_ok, self.stat_errors, self.stat_blocked, self.stat_duplicates, self.stat_orphans)
        ):
            budget_grid.addWidget(box, i // 3, i % 3)
        top_row.addLayout(budget_grid, stretch=1)
        root.addLayout(top_row)

        cat_header = QLabel("Issues por categoría")
        cat_header.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {theme.TEXT_PRIMARY}; margin-top: 8px;")
        root.addWidget(cat_header)

        self.category_grid = QGridLayout()
        self.category_grid.setHorizontalSpacing(12)
        self.category_grid.setVerticalSpacing(8)
        root.addLayout(self.category_grid)

        opportunities_header = QLabel("Oportunidades de optimización")
        opportunities_header.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {theme.TEXT_PRIMARY}; margin-top: 12px;")
        root.addWidget(opportunities_header)

        opportunities_sub = QLabel(
            "Las mejoras con mayor impacto potencial para tu sitio, agrupadas por tipo de solución."
        )
        opportunities_sub.setStyleSheet(f"font-size: 11.5px; color: {theme.TEXT_MUTED}; margin-bottom: 4px;")
        root.addWidget(opportunities_sub)

        self.opportunities_container = QWidget()
        self.opportunities_layout = QVBoxLayout(self.opportunities_container)
        self.opportunities_layout.setContentsMargins(0, 0, 0, 0)
        self.opportunities_layout.setSpacing(8)
        root.addWidget(self.opportunities_container)

        infra_header = QLabel("Robots.txt y Sitemap")
        infra_header.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {theme.TEXT_PRIMARY}; margin-top: 16px;")
        root.addWidget(infra_header)

        self.infra_container = QWidget()
        self.infra_layout = QVBoxLayout(self.infra_container)
        self.infra_layout.setContentsMargins(0, 0, 0, 0)
        self.infra_layout.setSpacing(8)
        root.addWidget(self.infra_container)
        self._show_infra_pending()

        root.addStretch(1)
        self._show_pending_state()

    def update_data(self, pages: list[PageResult], priority_urls: set[str] | None = None) -> None:
        if not pages:
            self._show_pending_state()
            return

        self.start_banner.setVisible(False)
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
        self._update_opportunities(stats.find_opportunities(pages, limit=8))

    def _show_pending_state(self) -> None:
        self.start_banner.setVisible(True)
        self.ring.set_pending()
        for box in (
            self.stat_total, self.stat_ok, self.stat_errors, self.stat_blocked, self.stat_duplicates, self.stat_orphans
        ):
            _set_stat_pending(box, True)

        self._clear_layout(self.category_grid)
        empty_cat = QLabel("Inicia el crawl para ver los issues por categoría.")
        empty_cat.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 12px; font-style: italic;")
        self.category_grid.addWidget(empty_cat, 0, 0)

        self._clear_layout(self.opportunities_layout)
        empty_opp = QLabel("Inicia el crawl para ver oportunidades de optimización.")
        empty_opp.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 12px; font-style: italic;")
        self.opportunities_layout.addWidget(empty_opp)

    def update_site_info(self, sitemap_urls: list[str], site_issues: list[Issue]) -> None:
        infra = stats.summarize_site_infrastructure(sitemap_urls, site_issues)
        self._render_infra(infra)

    def reset_site_info(self) -> None:
        self._show_infra_pending()

    @staticmethod
    def _set_stat(box: QWidget, text: str) -> None:
        box._value_label.setText(text)
        _set_stat_pending(box, False)

    def _update_categories(self, breakdown: list[stats.CategoryBreakdown]) -> None:
        while self.category_grid.count():
            item = self.category_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not breakdown:
            empty = QLabel("Sin issues detectados en este crawl.")
            empty.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 12px;")
            self.category_grid.addWidget(empty, 0, 0)
            return

        max_total = max(b.total for b in breakdown)
        from spidermapp.gui.sidebar import CATEGORY_LABELS

        for row, bucket in enumerate(breakdown):
            name = QLabel(CATEGORY_LABELS.get(bucket.category, bucket.category.value))
            name.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_SECONDARY};")
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
            count.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_MUTED};")
            count.setFixedWidth(28)
            count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            self.category_grid.addWidget(name, row, 0)
            self.category_grid.addWidget(bar, row, 1)
            self.category_grid.addWidget(count, row, 2)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _update_opportunities(self, opportunities: list[stats.IssueOpportunity]) -> None:
        self._clear_layout(self.opportunities_layout)
        if not opportunities:
            empty = QLabel("Sin oportunidades de optimización detectadas. El sitio está en buena forma. ✓")
            empty.setStyleSheet(f"color: {theme.GOOD_HEX}; font-weight: 600; font-size: 12.5px; padding: 4px 0;")
            self.opportunities_layout.addWidget(empty)
            return
        for opportunity in opportunities:
            self.opportunities_layout.addWidget(OpportunityRow(opportunity))

    def _show_infra_pending(self) -> None:
        self._clear_layout(self.infra_layout)
        pending = QLabel("Se completa al terminar el crawl.")
        pending.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 12px; font-style: italic;")
        self.infra_layout.addWidget(pending)

    def _render_infra(self, infra: stats.SiteInfrastructure) -> None:
        self._clear_layout(self.infra_layout)

        robots_row = QHBoxLayout()
        robots_row.setSpacing(8)
        robots_row.addWidget(_fact_pill(infra.robots_found, "robots.txt encontrado", "Sin robots.txt"))
        if infra.robots_found:
            robots_row.addWidget(_fact_pill(infra.robots_allows_crawling, "Permite el rastreo", "Bloquea todo el sitio"))
            robots_row.addWidget(_fact_pill(infra.robots_declares_sitemap, "Declara el sitemap", "No declara el sitemap"))
        robots_row.addStretch(1)
        robots_container = QWidget()
        robots_container.setLayout(robots_row)
        self.infra_layout.addWidget(robots_container)

        sitemap_row = QHBoxLayout()
        sitemap_row.setSpacing(8)
        sitemap_text_ok = f"Sitemap encontrado — {infra.sitemap_url_count:,} URLs".replace(",", ".")
        sitemap_row.addWidget(_fact_pill(infra.sitemap_found, sitemap_text_ok, "Sin sitemap o está vacío"))
        sitemap_row.addStretch(1)
        sitemap_container = QWidget()
        sitemap_container.setLayout(sitemap_row)
        self.infra_layout.addWidget(sitemap_container)

        if infra.other_findings:
            other_header = QLabel("Otros hallazgos técnicos a nivel de sitio")
            other_header.setStyleSheet(f"font-size: 11.5px; font-weight: 700; color: {theme.TEXT_SECONDARY}; margin-top: 6px;")
            self.infra_layout.addWidget(other_header)
            for issue in infra.other_findings:
                rec = recommendations.get_recommendation(issue)
                color = _SEVERITY_HEX[issue.severity]
                line = QLabel(f"●  {rec.title}")
                line.setTextFormat(Qt.TextFormat.PlainText)
                line.setStyleSheet(f"font-size: 12px; color: {color};")
                line.setToolTip(rec.why)
                self.infra_layout.addWidget(line)
        else:
            ok_line = QLabel("Sin otros hallazgos técnicos a nivel de sitio. ✓")
            ok_line.setStyleSheet(f"color: {theme.GOOD_HEX}; font-size: 12px; margin-top: 4px;")
            self.infra_layout.addWidget(ok_line)
