from __future__ import annotations

from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core.models import PageResult


def _table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    return table


class DetailPanel(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.summary_label = QLabel("Selecciona una URL en la tabla para ver el detalle.")
        self.summary_label.setWordWrap(True)
        self.summary_label.setMargin(8)
        self._add_tab(self.summary_label, "Resumen")

        self.issues_table = _table(["Severidad", "Categoría", "Código", "Mensaje"])
        self._add_tab(self.issues_table, "Issues")

        self.outlinks_table = _table(["Destino", "Anchor", "Interno", "Rel"])
        self._add_tab(self.outlinks_table, "Enlaces salientes")

        self.inlinks_list = QListWidget()
        self._add_tab(self.inlinks_list, "Enlaces entrantes")

        self.headers_table = _table(["Header", "Valor"])
        self._add_tab(self.headers_table, "Headers")

        self.render_text = QPlainTextEdit()
        self.render_text.setReadOnly(True)
        self._add_tab(self.render_text, "Renderizado")

    def _add_tab(self, widget: QWidget, label: str) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(widget)
        self.addTab(container, label)

    def show_page(self, page: PageResult | None) -> None:
        if page is None:
            self.summary_label.setText("Selecciona una URL en la tabla para ver el detalle.")
            self.issues_table.setRowCount(0)
            self.outlinks_table.setRowCount(0)
            self.inlinks_list.clear()
            self.headers_table.setRowCount(0)
            self.render_text.setPlainText("")
            return

        self._update_summary(page)
        self._update_issues(page)
        self._update_outlinks(page)
        self._update_inlinks(page)
        self._update_headers(page)
        self._update_render(page)

    def _update_summary(self, page: PageResult) -> None:
        tls_line = ""
        if page.tls is not None:
            tls_line = f"<b>TLS:</b> {'válido' if page.tls.valid else 'inválido'} — expira en {page.tls.days_until_expiry} días<br>"
        lines = [
            f"<b>URL:</b> {page.url}<br>",
            f"<b>URL final:</b> {page.final_url or page.url}<br>",
            f"<b>Código:</b> {page.status_code}<br>",
            f"<b>Indexable:</b> {'Sí' if page.is_indexable else 'No'}<br>",
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

    def _update_issues(self, page: PageResult) -> None:
        self.issues_table.setRowCount(len(page.issues))
        for row, issue in enumerate(page.issues):
            self.issues_table.setItem(row, 0, QTableWidgetItem(issue.severity.value))
            self.issues_table.setItem(row, 1, QTableWidgetItem(issue.category.value))
            self.issues_table.setItem(row, 2, QTableWidgetItem(issue.code))
            self.issues_table.setItem(row, 3, QTableWidgetItem(issue.message))

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
