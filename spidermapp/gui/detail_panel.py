from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHeaderView,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import recommendations
from spidermapp.core.models import IssueSeverity, PageResult
from spidermapp.gui import theme

_SEVERITY_LABEL_ES = {IssueSeverity.CRITICAL: "Crítico", IssueSeverity.WARNING: "Advertencia", IssueSeverity.INFO: "Info"}
_SEVERITY_HEX = {
    IssueSeverity.CRITICAL: theme.CRITICAL_HEX,
    IssueSeverity.WARNING: theme.WARNING_HEX,
    IssueSeverity.INFO: theme.INFO_HEX,
}


def _table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    return table


class IssueCard(QFrame):
    def __init__(self, issue, parent=None):
        super().__init__(parent)
        rec = recommendations.get_recommendation(issue)
        color = _SEVERITY_HEX[issue.severity]

        self.setStyleSheet(
            f"IssueCard {{ background: white; border: 1px solid #E5E7EB; border-left: 4px solid {color}; "
            f"border-radius: 4px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        header = QLabel(
            f'<span style="color:{color}; font-weight:700; font-size:10.5px; text-transform:uppercase;">'
            f"{_SEVERITY_LABEL_ES[issue.severity]}</span>"
            f'<span style="color:#9CA3AF; font-size:10.5px;"> · {issue.category.value}</span>'
        )
        layout.addWidget(header)

        title = QLabel(rec.title)
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 13.5px; font-weight: 700; color: #111827;")
        layout.addWidget(title)

        if rec.why:
            why = QLabel(rec.why)
            why.setWordWrap(True)
            why.setStyleSheet("font-size: 12px; color: #6B7280;")
            layout.addWidget(why)

        if rec.fix_steps:
            steps_html = "<ol style='margin:4px 0 0 -18px; padding:0;'>" + "".join(
                f"<li style='margin-bottom:2px;'>{step}</li>" for step in rec.fix_steps
            ) + "</ol>"
            steps = QLabel(steps_html)
            steps.setWordWrap(True)
            steps.setStyleSheet("font-size: 12px; color: #374151;")
            layout.addWidget(steps)


class DetailPanel(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.summary_label = QLabel("Selecciona una URL en la tabla para ver el detalle.")
        self.summary_label.setWordWrap(True)
        self.summary_label.setMargin(8)
        self._add_tab(self.summary_label, "Resumen")

        self.issues_container = QWidget()
        self.issues_layout = QVBoxLayout(self.issues_container)
        self.issues_layout.setContentsMargins(10, 10, 10, 10)
        self.issues_layout.setSpacing(8)
        self.issues_layout.addStretch(1)
        issues_scroll = QScrollArea()
        issues_scroll.setWidgetResizable(True)
        issues_scroll.setFrameShape(QFrame.Shape.NoFrame)
        issues_scroll.setWidget(self.issues_container)
        self._add_tab(issues_scroll, "Issues", wrap=False)

        self.redirects_label = QLabel("Esta URL no tuvo redirects.")
        self.redirects_label.setWordWrap(True)
        self.redirects_label.setTextFormat(Qt.TextFormat.RichText)
        self.redirects_label.setMargin(10)
        self._add_tab(self.redirects_label, "Redirects")

        self.outlinks_table = _table(["Destino", "Anchor", "Interno", "Rel"])
        self._add_tab(self.outlinks_table, "Enlaces salientes")

        self.inlinks_list = QListWidget()
        self._add_tab(self.inlinks_list, "Enlaces entrantes")

        self.headers_table = _table(["Header", "Valor"])
        self._add_tab(self.headers_table, "Headers")

        self.render_text = QPlainTextEdit()
        self.render_text.setReadOnly(True)
        self._add_tab(self.render_text, "Renderizado")

    def _add_tab(self, widget: QWidget, label: str, wrap: bool = True) -> None:
        if not wrap:
            self.addTab(widget, label)
            return
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(widget)
        self.addTab(container, label)

    def show_page(self, page: PageResult | None) -> None:
        if page is None:
            self.summary_label.setText("Selecciona una URL en la tabla para ver el detalle.")
            self._clear_issue_cards()
            self.redirects_label.setText("Esta URL no tuvo redirects.")
            self.outlinks_table.setRowCount(0)
            self.inlinks_list.clear()
            self.headers_table.setRowCount(0)
            self.render_text.setPlainText("")
            return

        self._update_summary(page)
        self._update_issues(page)
        self._update_redirects(page)
        self._update_outlinks(page)
        self._update_inlinks(page)
        self._update_headers(page)
        self._update_render(page)

    def _update_summary(self, page: PageResult) -> None:
        tls_line = ""
        if page.tls is not None:
            tls_line = f"<b>TLS:</b> {'válido' if page.tls.valid else 'inválido'} — expira en {page.tls.days_until_expiry} días<br>"
        orphan_line = "<b>Huérfana:</b> sí, sin enlaces internos hacia ella<br>" if page.is_orphan else ""
        lines = [
            f"<b>URL:</b> {page.url}<br>",
            f"<b>URL final:</b> {page.final_url or page.url}<br>",
            f"<b>Código:</b> {page.status_code}<br>",
            f"<b>Indexable:</b> {'Sí' if page.is_indexable else 'No'}<br>",
            orphan_line,
            f"<b>Title:</b> {page.title} ({len(page.title)} car.)<br>",
            f"<b>Meta description:</b> {page.meta_description} ({len(page.meta_description)} car.)<br>",
            f"<b>H1:</b> {' | '.join(page.h1)}<br>",
            f"<b>Canonical:</b> {page.canonical}<br>",
            f"<b>Meta robots:</b> {page.meta_robots}<br>",
            f"<b>Palabras:</b> {page.word_count}<br>",
            f"<b>Tecnología detectada:</b> {', '.join(page.tech)}<br>",
            tls_line,
            f"<b>Tiempo de respuesta:</b> {page.fetch_time_ms:.0f} ms<br>",
        ]
        if page.error:
            lines.append(f"<b>Error:</b> {page.error}<br>")
        self.summary_label.setText("".join(lines))

    def _clear_issue_cards(self) -> None:
        while self.issues_layout.count() > 1:
            item = self.issues_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _update_issues(self, page: PageResult) -> None:
        self._clear_issue_cards()
        if not page.issues:
            empty = QLabel("Sin issues en esta página. ✓")
            empty.setStyleSheet(f"color: {theme.GOOD_HEX}; font-weight: 600; padding: 8px;")
            self.issues_layout.insertWidget(0, empty)
            return
        ordered = sorted(page.issues, key=lambda i: {"critical": 0, "warning": 1, "info": 2}[i.severity.value])
        for i, issue in enumerate(ordered):
            self.issues_layout.insertWidget(i, IssueCard(issue))

    def _update_redirects(self, page: PageResult) -> None:
        if not page.redirect_chain:
            self.redirects_label.setText("Esta URL no tuvo redirects.")
            return
        hops = list(page.redirect_chain)
        final = page.final_url or page.url
        segments = []
        for url, status in hops:
            color = theme.WARNING_HEX if status in (302, 303, 307) else theme.GOOD_HEX
            segments.append(
                f'<div style="margin-bottom:6px;"><span style="font-family:monospace;">{url}</span> '
                f'&nbsp;<span style="color:{color}; font-weight:700;">──[{status}]──▶</span></div>'
            )
        segments.append(f'<div><span style="font-family:monospace; font-weight:700;">{final}</span> (destino final)</div>')
        self.redirects_label.setText("".join(segments))

    def _update_outlinks(self, page: PageResult) -> None:
        self.outlinks_table.setRowCount(len(page.outlinks))
        for row, link in enumerate(page.outlinks):
            self.outlinks_table.setItem(row, 0, QTableWidgetItem(link.target))
            self.outlinks_table.setItem(row, 1, QTableWidgetItem(link.anchor_text))
            self.outlinks_table.setItem(row, 2, QTableWidgetItem("Sí" if link.is_internal else "No"))
            self.outlinks_table.setItem(row, 3, QTableWidgetItem(link.rel))

    def _update_inlinks(self, page: PageResult) -> None:
        self.inlinks_list.clear()
        self.inlinks_list.addItems(page.inlinks)

    def _update_headers(self, page: PageResult) -> None:
        items = list(page.headers.items())
        self.headers_table.setRowCount(len(items))
        for row, (key, value) in enumerate(items):
            self.headers_table.setItem(row, 0, QTableWidgetItem(key))
            self.headers_table.setItem(row, 1, QTableWidgetItem(value))

    def _update_render(self, page: PageResult) -> None:
        if page.render is None:
            self.render_text.setPlainText("Renderizado JS no activado para este crawl.")
            return
        r = page.render
        lines = []
        if r.error:
            lines.append(f"Error al renderizar: {r.error}")
        else:
            lines.append(f"Title coincide (crudo vs renderizado): {'Sí' if r.raw_vs_rendered_title_match else 'No'}")
            lines.append(f"Meta description coincide: {'Sí' if r.raw_vs_rendered_desc_match else 'No'}")
            lines.append(f"H1 coincide: {'Sí' if r.raw_vs_rendered_h1_match else 'No'}")
            lines.append(f"Mobile y desktop muestran lo mismo: {'Sí' if r.mobile_desktop_match else 'No'}")
            lines.append("")
            lines.append(f"LCP (lab): {r.lcp_ms:.0f} ms" if r.lcp_ms is not None else "LCP (lab): n/d")
            lines.append(f"CLS (lab): {r.cls:.3f}" if r.cls is not None else "CLS (lab): n/d")
            lines.append(f"FCP (lab): {r.fcp_ms:.0f} ms" if r.fcp_ms is not None else "FCP (lab): n/d")
        self.render_text.setPlainText("\n".join(lines))
