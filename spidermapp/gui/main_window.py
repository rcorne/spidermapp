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
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import export
from spidermapp.core.models import CrawlConfig, CrawlResult, IssueCategory, PageResult
from spidermapp.gui.crawl_worker import CrawlWorker
from spidermapp.gui.detail_panel import DetailPanel
from spidermapp.gui.sidebar import Sidebar
from spidermapp.gui.table_model import IssueFilterProxyModel, PageTableModel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spidermapp — Auditor de SEO")
        self.resize(1400, 900)

        self._worker: CrawlWorker | None = None
        self._all_pages: list[PageResult] = []

        self.table_model = PageTableModel(self)
        self.proxy_model = IssueFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.table_model)

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        root_layout.addLayout(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, stretch=1)

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
        self.table_view.selectionModel().selectionChanged.connect(self._on_row_selected)
        center_splitter.addWidget(self.table_view)

        self.detail_panel = DetailPanel()
        center_splitter.addWidget(self.detail_panel)
        center_splitter.setSizes([600, 300])

        splitter.addWidget(center_splitter)
        splitter.setSizes([280, 1100])

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Listo.")

    def _build_toolbar(self):
        layout = QHBoxLayout()

        layout.addWidget(QLabel("URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://ejemplo.com")
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
        self.start_button.clicked.connect(self._start_crawl)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Detener")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_crawl)
        layout.addWidget(self.stop_button)

        self.export_csv_button = QPushButton("Exportar CSV")
        self.export_csv_button.clicked.connect(lambda: self._export("csv"))
        layout.addWidget(self.export_csv_button)

        self.export_xlsx_button = QPushButton("Exportar XLSX")
        self.export_xlsx_button.clicked.connect(lambda: self._export("xlsx"))
        layout.addWidget(self.export_xlsx_button)

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
        self.detail_panel.show_page(None)

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

    def _on_progress(self, done: int, total: int) -> None:
        self.statusBar().showMessage(f"Rastreadas {done} de {total} páginas (máx.)...")

    def _on_crawl_finished(self, result: CrawlResult) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
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
        if key == "__all__":
            self.proxy_model.set_filter_all()
        elif key == "__issues__":
            self.proxy_model.set_filter_any_issue()
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
