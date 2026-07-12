from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import export, history, pdf_report
from spidermapp.core.models import CrawlConfig, CrawlResult, IssueCategory, PageResult
from spidermapp.gui import theme
from spidermapp.gui.crawl_worker import CrawlWorker
from spidermapp.gui.dashboard import DashboardTab
from spidermapp.gui.detail_panel import DetailPanel
from spidermapp.gui.sidebar import ALL_KEY, DUPLICATES_KEY, ISSUES_KEY, ORPHANS_KEY, Sidebar
from spidermapp.gui.sitemap_view import SiteMapTab
from spidermapp.gui.table_model import IssueFilterProxyModel, PageTableModel

SITEMAP_REFRESH_EVERY_N_PAGES = 15


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spidermapp — Auditor de SEO")
        self.resize(1440, 940)

        self._worker: CrawlWorker | None = None
        self._all_pages: list[PageResult] = []
        self._last_result: CrawlResult | None = None
        self._previous_snapshot = None
        self._pages_since_sitemap_refresh = 0

        self.table_model = PageTableModel(self)
        self.proxy_model = IssueFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.table_model)

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        toolbar_container = QWidget()
        toolbar_container.setStyleSheet("background: white; border-bottom: 1px solid #E5E7EB;")
        toolbar_container.setLayout(self._build_toolbar())
        root_layout.addWidget(toolbar_container)

        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs, stretch=1)

        self.dashboard_tab = DashboardTab()
        self.tabs.addTab(self.dashboard_tab, "Vista general")

        self.sitemap_tab = SiteMapTab()
        self.sitemap_tab.node_clicked.connect(self._focus_url_in_table)
        self.tabs.addTab(self.sitemap_tab, "Mapa del sitio")

        self.tabs.addTab(self._build_table_tab(), "Tabla")

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Listo.")

    def _build_table_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        self.sidebar = Sidebar()
        self.sidebar.setMaximumWidth(320)
        self.sidebar.selection_changed.connect(self._on_sidebar_selection)
        splitter.addWidget(self.sidebar)

        center_splitter = QSplitter(Qt.Orientation.Vertical)

        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table_view.setAlternatingRowColors(False)
        self.table_view.selectionModel().selectionChanged.connect(self._on_row_selected)
        center_splitter.addWidget(self.table_view)

        self.detail_panel = DetailPanel()
        center_splitter.addWidget(self.detail_panel)
        center_splitter.setSizes([600, 320])

        splitter.addWidget(center_splitter)
        splitter.setSizes([280, 1100])

        return container

    def _build_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        layout.addWidget(QLabel("URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://ejemplo.com")
        self.url_input.setMinimumWidth(220)
        layout.addWidget(self.url_input, stretch=1)

        layout.addWidget(QLabel("Máx. páginas:"))
        self.max_pages_input = QSpinBox()
        self.max_pages_input.setRange(1, 100000)
        self.max_pages_input.setValue(500)
        layout.addWidget(self.max_pages_input)

        layout.addWidget(QLabel("Máx. profundidad:"))
        self.max_depth_input = QSpinBox()
        self.max_depth_input.setRange(1, 100)
        self.max_depth_input.setValue(10)
        layout.addWidget(self.max_depth_input)

        layout.addWidget(QLabel("Concurrencia:"))
        self.concurrency_input = QSpinBox()
        self.concurrency_input.setRange(1, 64)
        self.concurrency_input.setValue(8)
        layout.addWidget(self.concurrency_input)

        self.render_js_checkbox = QCheckBox("Renderizar JS (más lento)")
        layout.addWidget(self.render_js_checkbox)

        self.start_button = QPushButton("Iniciar crawl")
        self.start_button.setStyleSheet(theme.BUTTON_PRIMARY_QSS)
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.clicked.connect(self._start_crawl)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Detener")
        self.stop_button.setStyleSheet(theme.BUTTON_DANGER_QSS)
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_crawl)
        layout.addWidget(self.stop_button)

        self.compare_button = QPushButton("Comparar con crawl anterior")
        self.compare_button.setStyleSheet(theme.BUTTON_SECONDARY_QSS)
        self.compare_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.compare_button.setEnabled(False)
        self.compare_button.clicked.connect(self._compare_with_previous)
        layout.addWidget(self.compare_button)

        self.export_csv_button = QPushButton("CSV")
        self.export_csv_button.setStyleSheet(theme.BUTTON_SECONDARY_QSS)
        self.export_csv_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_csv_button.clicked.connect(lambda: self._export("csv"))
        layout.addWidget(self.export_csv_button)

        self.export_xlsx_button = QPushButton("XLSX")
        self.export_xlsx_button.setStyleSheet(theme.BUTTON_SECONDARY_QSS)
        self.export_xlsx_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_xlsx_button.clicked.connect(lambda: self._export("xlsx"))
        layout.addWidget(self.export_xlsx_button)

        self.export_pdf_button = QPushButton("Reporte PDF")
        self.export_pdf_button.setStyleSheet(theme.BUTTON_SECONDARY_QSS)
        self.export_pdf_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_pdf_button.clicked.connect(self._export_pdf)
        layout.addWidget(self.export_pdf_button)

        return layout

    def _start_crawl(self) -> None:
        seed_url = self.url_input.text().strip()
        if not seed_url:
            QMessageBox.warning(self, "Spidermapp", "Ingresa una URL para comenzar.")
            return
        if not seed_url.startswith(("http://", "https://")):
            seed_url = f"https://{seed_url}"
            self.url_input.setText(seed_url)

        self.table_model.clear()
        self._all_pages = []
        self._pages_since_sitemap_refresh = 0
        self.detail_panel.show_page(None)
        self.sidebar.refresh_counts([])
        self.dashboard_tab.update_data([])
        self.sitemap_tab.set_pages([], seed_url)
        self.compare_button.setEnabled(False)

        config = CrawlConfig(
            seed_url=seed_url,
            max_pages=self.max_pages_input.value(),
            max_depth=self.max_depth_input.value(),
            concurrency=self.concurrency_input.value(),
            render_js=self.render_js_checkbox.isChecked(),
        )

        self._worker = CrawlWorker(config)
        self._worker.page_found.connect(self._on_page_found)
        self._worker.progress.connect(self._on_progress)
        self._worker.crawl_finished.connect(self._on_crawl_finished)
        self._worker.crawl_error.connect(self._on_crawl_error)
        self._worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.statusBar().showMessage(f"Rastreando {seed_url}...")

    def _stop_crawl(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self.statusBar().showMessage("Deteniendo crawl...")

    def _on_page_found(self, page: PageResult) -> None:
        self.table_model.upsert_page(page)
        self._all_pages = self.table_model.all_pages()
        self.sidebar.refresh_counts(self._all_pages)
        self.dashboard_tab.update_data(self._all_pages)

        self._pages_since_sitemap_refresh += 1
        if self._pages_since_sitemap_refresh >= SITEMAP_REFRESH_EVERY_N_PAGES:
            self._pages_since_sitemap_refresh = 0
            seed = self._worker.config.seed_url if self._worker else ""
            self.sitemap_tab.set_pages(self._all_pages, seed)

    def _on_progress(self, done: int, total: int) -> None:
        self.statusBar().showMessage(f"Rastreadas {done} de {total} páginas (máx.)...")

    def _on_crawl_finished(self, result: CrawlResult) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        # Safety net: the table is normally kept in sync incrementally via
        # page_found signals during the crawl, but the final result is the
        # source of truth (e.g. orphan pages are appended after the main
        # BFS loop) — make sure every page ends up reflected in the table.
        for page in result.pages:
            self.table_model.upsert_page(page)

        self._all_pages = self.table_model.all_pages()
        self.dashboard_tab.update_data(self._all_pages)
        self.sitemap_tab.set_pages(self._all_pages, result.seed_url)
        self.sidebar.refresh_counts(self._all_pages)

        self._last_result = result
        self._previous_snapshot = history.load_previous_snapshot(result.seed_url)
        try:
            history.save_crawl(result)
        except OSError:
            pass
        self.compare_button.setEnabled(self._previous_snapshot is not None)

        note = " (detenido antes de terminar)" if result.stopped_early else ""
        self.statusBar().showMessage(
            f"Crawl terminado{note}: {len(result.pages)} páginas, {len(result.site_issues)} issues a nivel de sitio."
        )
        if result.site_issues:
            messages = "\n".join(f"- {i.message}" for i in result.site_issues)
            QMessageBox.information(self, "Issues a nivel de sitio", messages)

    def _on_crawl_error(self, message: str) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.statusBar().showMessage("Error durante el crawl.")
        QMessageBox.critical(self, "Spidermapp", f"Error durante el crawl:\n{message}")

    def _on_sidebar_selection(self, key: str) -> None:
        if key == ALL_KEY:
            self.proxy_model.set_filter_all()
        elif key == ISSUES_KEY:
            self.proxy_model.set_filter_any_issue()
        elif key == ORPHANS_KEY:
            self.proxy_model.set_filter_orphans()
        elif key == DUPLICATES_KEY:
            self.proxy_model.set_filter_duplicates()
        else:
            self.proxy_model.set_filter_category(IssueCategory(key))

    def _on_row_selected(self, *_args) -> None:
        indexes = self.table_view.selectionModel().selectedRows()
        if not indexes:
            self.detail_panel.show_page(None)
            return
        source_index = self.proxy_model.mapToSource(indexes[0])
        page = self.table_model.page_at(source_index.row())
        self.detail_panel.show_page(page)

    def _focus_url_in_table(self, url: str) -> None:
        self.tabs.setCurrentIndex(2)
        self.proxy_model.set_filter_all()
        self.sidebar.setCurrentRow(0)
        for row in range(self.proxy_model.rowCount()):
            source_index = self.proxy_model.mapToSource(self.proxy_model.index(row, 0))
            page = self.table_model.page_at(source_index.row())
            if page is not None and page.url == url:
                proxy_index = self.proxy_model.index(row, 0)
                self.table_view.setCurrentIndex(proxy_index)
                self.table_view.scrollTo(proxy_index)
                break

    def _compare_with_previous(self) -> None:
        if self._last_result is None or self._previous_snapshot is None:
            QMessageBox.information(self, "Spidermapp", "No hay un crawl anterior de este sitio para comparar.")
            return

        diff = history.diff_crawls(self._previous_snapshot, self._last_result)
        if diff.is_empty:
            QMessageBox.information(self, "Comparación con crawl anterior", "No hay cambios desde el crawl anterior.")
            return

        lines = [
            f"Issues nuevos: {diff.new_issue_count}",
            f"Issues resueltos: {diff.resolved_issue_count}",
            f"Páginas nuevas: {len(diff.new_pages)}",
            f"Páginas que desaparecieron: {len(diff.removed_pages)}",
            "",
        ]
        if diff.new_issue_codes_by_url:
            lines.append("Nuevos issues (primeras 10 URLs):")
            for url, codes in list(diff.new_issue_codes_by_url.items())[:10]:
                lines.append(f"  • {url}: {', '.join(codes)}")
        if diff.resolved_issue_codes_by_url:
            lines.append("")
            lines.append("Issues resueltos (primeras 10 URLs):")
            for url, codes in list(diff.resolved_issue_codes_by_url.items())[:10]:
                lines.append(f"  • {url}: {', '.join(codes)}")

        QMessageBox.information(self, "Comparación con crawl anterior", "\n".join(lines))

    def _export(self, fmt: str) -> None:
        pages = self.table_model.all_pages()
        if not pages:
            QMessageBox.warning(self, "Spidermapp", "No hay resultados para exportar todavía.")
            return

        default_name = f"spidermapp_crawl.{fmt}"
        filter_str = "CSV (*.csv)" if fmt == "csv" else "Excel (*.xlsx)"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar resultados", default_name, filter_str)
        if not path:
            return

        try:
            if fmt == "csv":
                export.export_csv(pages, path)
            else:
                export.export_xlsx(pages, path)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user via a dialog
            QMessageBox.critical(self, "Spidermapp", f"No se pudo exportar: {exc}")
            return

        self.statusBar().showMessage(f"Exportado a {path}")

    def _export_pdf(self) -> None:
        if self._last_result is None:
            QMessageBox.warning(self, "Spidermapp", "No hay resultados para exportar todavía.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Exportar reporte PDF", "spidermapp_reporte.pdf", "PDF (*.pdf)")
        if not path:
            return

        try:
            pdf_report.generate_pdf_report(self._last_result, path)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user via a dialog
            QMessageBox.critical(self, "Spidermapp", f"No se pudo generar el PDF: {exc}")
            return

        self.statusBar().showMessage(f"Reporte PDF exportado a {path}")
