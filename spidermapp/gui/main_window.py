from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import app_settings, export, history, pdf_report, reports
from spidermapp.core.models import CrawlConfig, CrawlResult, IssueCategory, PageResult
from spidermapp.gui import theme
from spidermapp.gui.about_dialog import AboutDialog
from spidermapp.gui.crawl_worker import CrawlWorker
from spidermapp.gui.dashboard import DashboardTab
from spidermapp.gui.detail_panel import DetailPanel
from spidermapp.gui.history_dialog import HistoryDialog
from spidermapp.gui.llm_tab import LlmVisibilityTab
from spidermapp.gui.settings_dialog import SettingsDialog
from spidermapp.gui.sidebar import ALL_KEY, DUPLICATES_KEY, ISSUES_KEY, ORPHANS_KEY, Sidebar
from spidermapp.gui.sitemap_view import SiteMapTab
from spidermapp.gui.structure_view import StructureTab
from spidermapp.gui.table_model import IssueFilterProxyModel, PageTableModel

SITEMAP_REFRESH_EVERY_N_PAGES = 15
MAX_CRAWL_PAGES = 10000


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spidermapp — Auditor de SEO")

        # Behave like any normal window: shrinkable, and never open wider
        # than the screen the app lands on.
        self.setMinimumSize(720, 480)
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(1440, available.width() - 48), min(940, available.height() - 48))
        else:
            self.resize(1200, 800)

        self._worker: CrawlWorker | None = None
        self._all_pages: list[PageResult] = []
        self._last_result: CrawlResult | None = None
        self._previous_snapshot = None
        self._pages_since_sitemap_refresh = 0

        # Advanced crawl options, set once via Archivo → Preferencias and
        # persisted alongside every other setting — kept separate from the
        # quick controls in the toolbar (páginas, profundidad, hilos,
        # renderizar JS) that get touched on nearly every crawl.
        self._crawl_advanced: dict = self._load_crawl_advanced()

        self.table_model = PageTableModel(self)
        self.proxy_model = IssueFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.table_model)

        self._build_ui()

    def _build_ui(self) -> None:
        self._build_menus()

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        toolbar_container = QWidget()
        toolbar_container.setStyleSheet("background: white; border-bottom: 1px solid #E5E7EB;")
        toolbar_container.setLayout(self._build_toolbar())
        root_layout.addWidget(toolbar_container)

        root_layout.addWidget(self._build_progress_row())

        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs, stretch=1)

        self.dashboard_tab = DashboardTab()
        self.tabs.addTab(self.dashboard_tab, "Vista general")

        self.sitemap_tab = SiteMapTab()
        self.sitemap_tab.node_clicked.connect(self._focus_url_in_table)
        self.tabs.addTab(self.sitemap_tab, "Mapa del sitio")

        self.structure_tab = StructureTab()
        self.structure_tab.node_clicked.connect(self._focus_url_in_table)
        self.tabs.addTab(self.structure_tab, "Estructura")

        self.table_tab = self._build_table_tab()
        self.tabs.addTab(self.table_tab, "Tabla")

        self.llm_tab = LlmVisibilityTab()
        self.tabs.addTab(self.llm_tab, "Visibilidad en LLMs")

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Listo.")

    def _build_menus(self) -> None:
        menubar = self.menuBar()

        def action(menu, text: str, slot, shortcut: str | None = None, role=QAction.MenuRole.NoRole) -> QAction:
            act = QAction(text, self)
            if shortcut:
                act.setShortcut(QKeySequence(shortcut))
            # macOS auto-relocates actions whose text matches "preferences"/
            # "about"/"quit"-like words (QAction.MenuRole.TextHeuristicRole,
            # the default) into the system App menu — which silently empties
            # and hides whatever custom menu they were in. NoRole opts every
            # action out of that guesswork; the three below opt back in
            # deliberately, in the exact native slot macOS users expect.
            act.setMenuRole(role)
            act.triggered.connect(slot)
            menu.addAction(act)
            return act

        archivo = menubar.addMenu("Archivo")
        action(archivo, "Nuevo crawl…", self._menu_new_crawl, "Ctrl+N")
        action(archivo, "Abrir crawl guardado…", self._open_history_dialog, "Ctrl+O")
        # Preferencias… and Salir carry PreferencesRole/QuitRole below, so
        # macOS pulls them into the native app menu — no separators needed
        # here since nothing custom is left to separate them from.
        action(archivo, "Preferencias…", self._open_settings_dialog, "Ctrl+,", role=QAction.MenuRole.PreferencesRole)
        action(archivo, "Salir", QApplication.instance().quit, "Ctrl+Q", role=QAction.MenuRole.QuitRole)

        edicion = menubar.addMenu("Edición")
        action(edicion, "Copiar URL seleccionada", self._copy_selected_url, "Ctrl+C")
        action(edicion, "Copiar tabla visible (CSV)", self._copy_visible_table)

        analisis = menubar.addMenu("Análisis")
        action(analisis, "Iniciar crawl", self._start_crawl, "Ctrl+R")
        action(analisis, "Detener crawl", self._stop_crawl, "Ctrl+.")
        analisis.addSeparator()
        action(analisis, "Comparar con crawl anterior", self._compare_with_previous)
        action(analisis, "Historial de crawls…", self._open_history_dialog)
        analisis.addSeparator()
        action(analisis, "Visibilidad en LLMs", lambda: self.tabs.setCurrentWidget(self.llm_tab))
        action(analisis, "PageSpeed de la URL semilla", self._run_pagespeed)

        exportar = menubar.addMenu("Exportar")
        action(exportar, "CSV…", lambda: self._export("csv"))
        action(exportar, "XLSX…", lambda: self._export("xlsx"))
        action(exportar, "Reporte PDF ejecutivo…", self._export_pdf)
        action(exportar, "Informes por área de SEO…", self._export_area_reports)

        ayuda = menubar.addMenu("Ayuda")
        # Deliberately NoRole (not AboutRole): the user wants this reachable
        # from the "Ayuda" menu specifically. AboutRole would let macOS pull
        # it into the native app menu instead — which would leave "Ayuda"
        # with zero items and macOS would hide the whole menu, same bug as
        # the vanished "Conectores" menu this file used to have.
        action(ayuda, "Acerca de Spidermapp", self._show_about)

    def _build_progress_row(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: #F9FAFB; border-bottom: 1px solid #E5E7EB;")
        row = QHBoxLayout(container)
        row.setContentsMargins(12, 4, 12, 4)
        row.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v de %m páginas")
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ border: 1px solid #E5E7EB; border-radius: 7px; background: #EEF0F2; font-size: 10px; }}"
            f"QProgressBar::chunk {{ background-color: {theme.PRIMARY}; border-radius: 7px; }}"
        )
        row.addWidget(self.progress_bar, stretch=1)

        self.phase_label = QLabel("Listo.")
        self.phase_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        # Never let a long URL in the label dictate the window's minimum width
        self.phase_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.phase_label.setMinimumWidth(120)
        row.addWidget(self.phase_label, stretch=1)
        return container

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

    def _build_toolbar(self) -> QVBoxLayout:
        """Two compact rows so the window can shrink to laptop widths.
        Export/compare actions live in the menu bar (Exportar / Análisis)."""
        outer = QVBoxLayout()
        outer.setSpacing(4)
        outer.setContentsMargins(10, 8, 10, 8)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(QLabel("URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://ejemplo.com")
        self.url_input.setMinimumWidth(140)
        self.url_input.returnPressed.connect(self._start_crawl)
        row1.addWidget(self.url_input, stretch=1)

        self.start_button = QPushButton("Iniciar crawl")
        self.start_button.setStyleSheet(theme.BUTTON_PRIMARY_QSS)
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.clicked.connect(self._start_crawl)
        row1.addWidget(self.start_button)

        self.stop_button = QPushButton("Detener")
        self.stop_button.setStyleSheet(theme.BUTTON_DANGER_QSS)
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_crawl)
        row1.addWidget(self.stop_button)
        outer.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)

        defaults = app_settings.load_settings()

        row2.addWidget(QLabel("Páginas:"))
        self.max_pages_input = QSpinBox()
        self.max_pages_input.setRange(1, MAX_CRAWL_PAGES)
        self.max_pages_input.setValue(defaults.default_max_pages)
        self.max_pages_input.setMaximumWidth(72)
        row2.addWidget(self.max_pages_input)

        row2.addWidget(QLabel("Prof.:"))
        self.max_depth_input = QSpinBox()
        self.max_depth_input.setRange(1, 100)
        self.max_depth_input.setValue(defaults.default_max_depth)
        self.max_depth_input.setMaximumWidth(56)
        row2.addWidget(self.max_depth_input)

        row2.addWidget(QLabel("Hilos:"))
        self.concurrency_input = QSpinBox()
        self.concurrency_input.setRange(1, 64)
        self.concurrency_input.setValue(defaults.default_concurrency)
        self.concurrency_input.setMaximumWidth(50)
        row2.addWidget(self.concurrency_input)

        self.render_js_checkbox = QCheckBox("Renderizar JS")
        self.render_js_checkbox.setChecked(defaults.default_render_js)
        self.render_js_checkbox.setToolTip(
            "Abre cada página en Chromium para comparar HTML crudo vs renderizado y mobile vs desktop. "
            "Si el sitio es una app JavaScript, el crawler lo activa solo aunque no marques esta casilla."
        )
        row2.addWidget(self.render_js_checkbox)

        row2.addStretch(1)

        self.compare_button = QPushButton("Comparar")
        self.compare_button.setToolTip("Comparar con el crawl anterior de este mismo sitio")
        self.compare_button.setStyleSheet(theme.BUTTON_SECONDARY_QSS)
        self.compare_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.compare_button.setEnabled(False)
        self.compare_button.clicked.connect(self._compare_with_previous)
        row2.addWidget(self.compare_button)
        outer.addLayout(row2)

        return outer

    def _start_crawl(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self.statusBar().showMessage("Ya hay un crawl en curso.")
            return

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
        self.dashboard_tab.reset_site_info()
        self.sitemap_tab.set_pages([], seed_url)
        self.structure_tab.set_pages([], seed_url)
        self.llm_tab.set_crawl_data("", [])
        self.compare_button.setEnabled(False)

        config = CrawlConfig(
            seed_url=seed_url,
            max_pages=self.max_pages_input.value(),
            max_depth=self.max_depth_input.value(),
            concurrency=self.concurrency_input.value(),
            render_js=self.render_js_checkbox.isChecked(),
            **self._crawl_advanced,
        )

        self._worker = CrawlWorker(config)
        self._worker.page_found.connect(self._on_page_found)
        self._worker.progress.connect(self._on_progress)
        self._worker.status_changed.connect(self._on_status_changed)
        self._worker.crawl_finished.connect(self._on_crawl_finished)
        self._worker.crawl_error.connect(self._on_crawl_error)
        self._worker.start()

        self.progress_bar.setRange(0, config.max_pages)
        self.progress_bar.setValue(0)
        self.phase_label.setText("Iniciando crawl…")

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
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        self.statusBar().showMessage(f"Rastreadas {done} de {total} páginas (máx.)...")

    def _on_status_changed(self, message: str) -> None:
        metrics = self.phase_label.fontMetrics()
        elided = metrics.elidedText(message, Qt.TextElideMode.ElideMiddle, max(80, self.phase_label.width() - 8))
        self.phase_label.setText(elided)
        self.phase_label.setToolTip(message)

    def _on_crawl_finished(self, result: CrawlResult) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setValue(self.progress_bar.maximum() if not result.stopped_early else self.progress_bar.value())
        self.phase_label.setText("Crawl terminado.")

        # Safety net: the table is normally kept in sync incrementally via
        # page_found signals during the crawl, but the final result is the
        # source of truth (e.g. orphan pages are appended after the main
        # BFS loop) — make sure every page ends up reflected in the table.
        for page in result.pages:
            self.table_model.upsert_page(page)

        self._all_pages = self.table_model.all_pages()
        self.dashboard_tab.update_data(self._all_pages)
        self.dashboard_tab.update_site_info(result.sitemap_urls, result.site_issues)
        self.sitemap_tab.set_pages(self._all_pages, result.seed_url)
        self.structure_tab.set_pages(self._all_pages, result.seed_url)
        self.llm_tab.set_crawl_data(result.seed_url, self._all_pages)
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
            f"Crawl terminado{note}: {len(result.pages)} páginas rastreadas. "
            f"Revisa Vista general para la estructura técnica y las oportunidades de mejora."
        )

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
        self.tabs.setCurrentWidget(self.table_tab)
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

    # ------------------------------------------------------------- menús

    def _menu_new_crawl(self) -> None:
        self.url_input.clear()
        self.url_input.setFocus()

    def _copy_selected_url(self) -> None:
        indexes = self.table_view.selectionModel().selectedRows()
        if not indexes:
            return
        source_index = self.proxy_model.mapToSource(indexes[0])
        page = self.table_model.page_at(source_index.row())
        if page is not None:
            QApplication.clipboard().setText(page.url)
            self.statusBar().showMessage("URL copiada al portapapeles.")

    def _copy_visible_table(self) -> None:
        rows = []
        headers = [self.table_model.headerData(c, Qt.Orientation.Horizontal) for c in range(self.table_model.columnCount())]
        rows.append(",".join(str(h) for h in headers))
        for row in range(self.proxy_model.rowCount()):
            values = []
            for col in range(self.proxy_model.columnCount()):
                value = self.proxy_model.data(self.proxy_model.index(row, col))
                text = "" if value is None else str(value)
                values.append('"' + text.replace('"', '""') + '"')
            rows.append(",".join(values))
        QApplication.clipboard().setText("\n".join(rows))
        self.statusBar().showMessage(f"{self.proxy_model.rowCount()} filas copiadas como CSV.")

    def _load_crawl_advanced(self) -> dict:
        settings = app_settings.load_settings()
        return {
            "respect_robots": settings.default_respect_robots,
            "include_subdomains": settings.default_include_subdomains,
            "user_agent": settings.default_user_agent,
            "max_url_length": settings.default_max_url_length,
            "exclude_patterns": list(settings.default_exclude_patterns),
            "priority_urls": list(settings.default_priority_urls),
            "request_timeout": settings.default_request_timeout,
        }

    def _open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self)
        if not dialog.exec():
            return
        self.statusBar().showMessage("Preferencias guardadas.")

        settings = app_settings.load_settings()
        self.max_pages_input.setValue(settings.default_max_pages)
        self.max_depth_input.setValue(settings.default_max_depth)
        self.concurrency_input.setValue(settings.default_concurrency)
        self.render_js_checkbox.setChecked(settings.default_render_js)
        self._crawl_advanced = self._load_crawl_advanced()

        if self._last_result is not None:
            self.llm_tab.set_crawl_data(self._last_result.seed_url, self._all_pages)

    def _open_history_dialog(self) -> None:
        dialog = HistoryDialog(self)
        if not dialog.exec():
            return
        if dialog.selected_path is not None:
            self._load_saved_crawl(dialog.selected_path)
        elif dialog.compare_paths is not None:
            self._compare_two_snapshots(*dialog.compare_paths)

    def _load_saved_crawl(self, path) -> None:
        try:
            result = history.load_full_crawl(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Spidermapp", f"No se pudo abrir el crawl guardado: {exc}")
            return
        if result is None:
            QMessageBox.information(
                self, "Spidermapp",
                "Ese crawl es de una versión anterior y solo sirve para comparaciones, no se puede abrir completo."
            )
            return

        self.table_model.clear()
        for page in result.pages:
            self.table_model.upsert_page(page)
        self._all_pages = self.table_model.all_pages()
        self._last_result = result
        self.url_input.setText(result.seed_url)

        self.dashboard_tab.update_data(self._all_pages)
        self.sitemap_tab.set_pages(self._all_pages, result.seed_url)
        self.structure_tab.set_pages(self._all_pages, result.seed_url)
        self.llm_tab.set_crawl_data(result.seed_url, self._all_pages)
        self.sidebar.refresh_counts(self._all_pages)
        self._previous_snapshot = history.load_previous_snapshot(result.seed_url, before=result.started_at)
        self.compare_button.setEnabled(self._previous_snapshot is not None)
        self.statusBar().showMessage(f"Crawl guardado cargado: {result.seed_url} ({len(result.pages)} páginas).")

    def _compare_two_snapshots(self, path_a, path_b) -> None:
        try:
            snap_a = history.load_snapshot(path_a)
            snap_b = history.load_snapshot(path_b)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Spidermapp", f"No se pudieron cargar los crawls: {exc}")
            return
        older, newer_path = (snap_a, path_b) if snap_a.timestamp <= snap_b.timestamp else (snap_b, path_a)
        newer_full = history.load_full_crawl(newer_path)
        if newer_full is None:
            QMessageBox.information(self, "Spidermapp", "El crawl más reciente no tiene datos completos para comparar.")
            return
        diff = history.diff_crawls(older, newer_full)
        self._show_diff_dialog(diff)

    def _show_diff_dialog(self, diff) -> None:
        if diff.is_empty:
            QMessageBox.information(self, "Comparación de crawls", "No hay cambios entre los crawls seleccionados.")
            return
        when = datetime.fromtimestamp(diff.previous_timestamp).strftime("%d/%m/%Y %H:%M")
        lines = [
            f"Comparado contra el crawl del {when}:",
            "",
            f"Issues nuevos: {diff.new_issue_count}",
            f"Issues resueltos: {diff.resolved_issue_count}",
            f"Páginas nuevas: {len(diff.new_pages)}",
            f"Páginas que desaparecieron: {len(diff.removed_pages)}",
        ]
        if diff.new_issue_codes_by_url:
            lines += ["", "Nuevos issues (primeras 10 URLs):"]
            for url, codes in list(diff.new_issue_codes_by_url.items())[:10]:
                lines.append(f"  • {url}: {', '.join(codes)}")
        if diff.resolved_issue_codes_by_url:
            lines += ["", "Issues resueltos (primeras 10 URLs):"]
            for url, codes in list(diff.resolved_issue_codes_by_url.items())[:10]:
                lines.append(f"  • {url}: {', '.join(codes)}")
        QMessageBox.information(self, "Comparación de crawls", "\n".join(lines))

    def _run_pagespeed(self) -> None:
        from spidermapp.core import connectors

        seed = self.url_input.text().strip()
        if not seed:
            QMessageBox.warning(self, "Spidermapp", "Ingresa una URL primero.")
            return
        if not connectors.is_configured("pagespeed"):
            QMessageBox.information(
                self, "Spidermapp",
                "Configura tu API key de PageSpeed Insights en Conectores → Configurar APIs "
                "(es gratuita, ver el enlace en ese diálogo)."
            )
            return
        self.statusBar().showMessage("Consultando PageSpeed Insights…")
        QApplication.processEvents()
        try:
            data = connectors.run_pagespeed(seed)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Spidermapp", f"PageSpeed falló: {exc}")
            self.statusBar().showMessage("PageSpeed falló.")
            return
        lines = [
            f"URL: {seed}",
            f"Performance (mobile): {data['score']}/100" if data["score"] is not None else "Performance: n/d",
            f"LCP: {data['lcp_ms']:.0f} ms" if data["lcp_ms"] is not None else "LCP: n/d",
            f"CLS: {data['cls']:.3f}" if data["cls"] is not None else "CLS: n/d",
            f"FCP: {data['fcp_ms']:.0f} ms" if data["fcp_ms"] is not None else "FCP: n/d",
            f"TBT: {data['tbt_ms']:.0f} ms" if data["tbt_ms"] is not None else "TBT: n/d",
        ]
        self.statusBar().showMessage("PageSpeed listo.")
        QMessageBox.information(self, "PageSpeed Insights (datos de campo de Google)", "\n".join(lines))

    def _export_area_reports(self) -> None:
        if self._last_result is None:
            QMessageBox.warning(self, "Spidermapp", "No hay resultados para generar informes todavía.")
            return
        directory = QFileDialog.getExistingDirectory(self, "Carpeta para los informes por área")
        if not directory:
            return
        try:
            written = reports.generate_area_reports(self._last_result, directory)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Spidermapp", f"No se pudieron generar los informes: {exc}")
            return
        if not written:
            QMessageBox.information(self, "Spidermapp", "No hay hallazgos: no se generó ningún informe.")
            return
        names = "\n".join(f"  • {p.name}" for p in written)
        QMessageBox.information(self, "Informes por área", f"Se generaron {len(written)} informes en {directory}:\n{names}")
        self.statusBar().showMessage(f"{len(written)} informes generados en {directory}.")

    def _show_about(self) -> None:
        AboutDialog(self).exec()
