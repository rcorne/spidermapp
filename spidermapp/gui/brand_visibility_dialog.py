from __future__ import annotations

import time
import webbrowser
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import brand_visibility as bv
from spidermapp.core import connectors
from spidermapp.gui import paths, theme

MIN_COMPETITORS = 2
MAX_COMPETITORS = 10


class BatteryWorker(QThread):
    finished_battery = Signal(list)
    failed = Signal(str)

    def __init__(self, category: str, market: str, provider: str, n: int, parent=None):
        super().__init__(parent)
        self._category = category
        self._market = market
        self._provider = provider
        self._n = n

    def run(self) -> None:
        try:
            templates = bv.generate_query_battery(self._category, self._market, self._provider, n=self._n)
            self.finished_battery.emit(templates)
        except Exception as exc:  # noqa: BLE001 - surfaced in the dialog
            self.failed.emit(str(exc))


class BrandVisibilityWorker(QThread):
    progress = Signal(int, int)
    finished_run = Signal(object)  # bv.BrandVisibilityReport
    failed = Signal(str)

    def __init__(self, config: bv.BrandVisibilityConfig, queries: list[bv.QueryTemplate], parent=None):
        super().__init__(parent)
        self._config = config
        self._queries = queries

    def run(self) -> None:
        analyses: list[bv.ResponseAnalysis] = []
        total = max(1, len(self._config.providers) * len(self._queries) * self._config.repetitions)
        done = 0
        try:
            def on_response(raw: bv.RawResponse) -> None:
                nonlocal done
                analyses.append(bv.analyze_response(self._config, raw))
                done += 1
                self.progress.emit(done, total)

            bv.run_battery(self._config, self._queries, on_response=on_response)
            report = bv.BrandVisibilityReport(config=self._config, created_at=time.time(), analyses=analyses)
            bv.save_run(report)
            self.finished_run.emit(report)
        except Exception as exc:  # noqa: BLE001 - surfaced in the dialog
            self.failed.emit(str(exc))


def _section_header(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-size: 13px; font-weight: 700; color: #111827; margin-top: 6px;")
    return label


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("font-size: 11px; color: #6B7280;")
    return label


class BrandVisibilityDialog(QDialog):
    """Analizador de visibilidad de marca/dominio en LLMs: mide, de forma
    repetida y estadística, con qué frecuencia, posición y framing aparece
    una marca en las respuestas de LLMs frente a competidores. Trata al LLM
    como caja negra: nunca le pide que explique por qué mencionó algo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Analizador de visibilidad de marca en LLMs")
        self.resize(920, 720)

        self._battery_worker: BatteryWorker | None = None
        self._run_worker: BrandVisibilityWorker | None = None
        self._queries: list[bv.QueryTemplate] = []
        self._current_report: bv.BrandVisibilityReport | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        layout.addWidget(_hint(
            "Mide con qué frecuencia, en qué posición y con qué tono aparece tu marca en las respuestas de "
            "varios LLMs, comparada contra competidores — no cuánto ranquea tu SEO, sino cuánto te menciona "
            "la IA. Metodología de caja negra: se muestrean respuestas repetidas y se miden estadísticamente; "
            "nunca se le pregunta al modelo por qué mencionó (o no) una marca."
        ))

        self._build_config_section(layout)
        self._build_battery_section(layout)
        self._build_run_section(layout)
        self._build_results_section(layout)
        layout.addStretch(1)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def _build_config_section(self, layout: QVBoxLayout) -> None:
        layout.addWidget(_section_header("1. Marca objetivo y competidores"))

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Marca objetivo:"))
        self.target_name = QLineEdit()
        self.target_name.setPlaceholderText("Ej: Cruz Verde")
        target_row.addWidget(self.target_name, stretch=1)
        target_row.addWidget(QLabel("Dominio:"))
        self.target_domain = QLineEdit()
        self.target_domain.setPlaceholderText("Ej: cruzverde.com.co")
        target_row.addWidget(self.target_domain, stretch=1)
        layout.addLayout(target_row)

        layout.addWidget(_hint("Competidores (2 a 10). El nombre y dominio se usan para detectar menciones, incluyendo variantes."))

        self.competitors_table = QTableWidget(0, 2)
        self.competitors_table.setHorizontalHeaderLabels(["Nombre", "Dominio"])
        self.competitors_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.competitors_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.competitors_table.setMaximumHeight(160)
        layout.addWidget(self.competitors_table)
        for _ in range(MIN_COMPETITORS):
            self._add_competitor_row()

        comp_buttons = QHBoxLayout()
        add_btn = QPushButton("+ Añadir competidor")
        add_btn.clicked.connect(self._add_competitor_row)
        remove_btn = QPushButton("- Quitar seleccionado")
        remove_btn.clicked.connect(self._remove_selected_competitor)
        comp_buttons.addWidget(add_btn)
        comp_buttons.addWidget(remove_btn)
        comp_buttons.addStretch(1)
        layout.addLayout(comp_buttons)

        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("Categoría:"))
        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("Ej: farmacias online")
        cat_row.addWidget(self.category_input, stretch=1)
        cat_row.addWidget(QLabel("Mercado:"))
        self.market_input = QLineEdit()
        self.market_input.setPlaceholderText("Ej: Colombia")
        cat_row.addWidget(self.market_input, stretch=1)
        layout.addLayout(cat_row)

        models_row = QHBoxLayout()
        models_row.addWidget(QLabel("Modelos a evaluar:"))
        self.provider_checks: dict[str, QCheckBox] = {}
        configured = [p for p in connectors.LLM_PROVIDERS if connectors.is_configured(p)]
        for provider in connectors.LLM_PROVIDERS:
            check = QCheckBox(bv.PROVIDER_LABELS.get(provider, provider))
            check.setEnabled(provider in configured)
            check.setChecked(provider in configured)
            if provider not in configured:
                check.setToolTip("Sin clave configurada (Archivo → Configuración → Conectores)")
            self.provider_checks[provider] = check
            models_row.addWidget(check)
        models_row.addStretch(1)
        layout.addLayout(models_row)
        if not configured:
            layout.addWidget(_hint("No hay ningún LLM configurado. Ve a Archivo → Configuración → Conectores para añadir al menos una clave."))

        params_row = QHBoxLayout()
        params_row.addWidget(QLabel("Repeticiones por consulta:"))
        self.repetitions_spin = QSpinBox()
        self.repetitions_spin.setRange(1, 50)
        self.repetitions_spin.setValue(bv.DEFAULT_REPETITIONS)
        params_row.addWidget(self.repetitions_spin)

        params_row.addWidget(QLabel("Temperatura:"))
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 1.5)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(bv.DEFAULT_TEMPERATURE)
        params_row.addWidget(self.temperature_spin)
        params_row.addStretch(1)
        layout.addLayout(params_row)

        rule = QFrame()
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setStyleSheet("color: #E5E7EB; margin: 8px 0;")
        layout.addWidget(rule)

    def _add_competitor_row(self) -> None:
        if self.competitors_table.rowCount() >= MAX_COMPETITORS:
            return
        row = self.competitors_table.rowCount()
        self.competitors_table.insertRow(row)
        self.competitors_table.setItem(row, 0, QTableWidgetItem(""))
        self.competitors_table.setItem(row, 1, QTableWidgetItem(""))

    def _remove_selected_competitor(self) -> None:
        rows = sorted({idx.row() for idx in self.competitors_table.selectedIndexes()}, reverse=True)
        if not rows and self.competitors_table.rowCount() > MIN_COMPETITORS:
            rows = [self.competitors_table.rowCount() - 1]
        for row in rows:
            if self.competitors_table.rowCount() > MIN_COMPETITORS:
                self.competitors_table.removeRow(row)

    def _collect_config(self) -> bv.BrandVisibilityConfig | None:
        target_name = self.target_name.text().strip()
        if not target_name:
            QMessageBox.warning(self, "Falta información", "Ingresa el nombre de la marca objetivo.")
            return None

        competitors: list[bv.Brand] = []
        for row in range(self.competitors_table.rowCount()):
            name_item = self.competitors_table.item(row, 0)
            domain_item = self.competitors_table.item(row, 1)
            name = (name_item.text().strip() if name_item else "")
            domain = (domain_item.text().strip() if domain_item else "")
            if name:
                competitors.append(bv.Brand(name=name, domain=domain))
        if len(competitors) < MIN_COMPETITORS:
            QMessageBox.warning(self, "Faltan competidores", f"Ingresa al menos {MIN_COMPETITORS} competidores.")
            return None

        category = self.category_input.text().strip()
        market = self.market_input.text().strip()
        if not category or not market:
            QMessageBox.warning(self, "Falta información", "Ingresa la categoría y el mercado.")
            return None

        providers = [p for p, check in self.provider_checks.items() if check.isChecked() and check.isEnabled()]
        if not providers:
            QMessageBox.warning(self, "Falta un modelo", "Selecciona al menos un LLM configurado.")
            return None

        return bv.BrandVisibilityConfig(
            target=bv.Brand(name=target_name, domain=self.target_domain.text().strip()),
            competitors=competitors,
            category=category,
            market=market,
            providers=providers,
            repetitions=self.repetitions_spin.value(),
            temperature=self.temperature_spin.value(),
            paraphrase_provider=providers[0],
        )

    # ------------------------------------------------------------------
    # Battery generation
    # ------------------------------------------------------------------

    def _build_battery_section(self, layout: QVBoxLayout) -> None:
        layout.addWidget(_section_header("2. Batería de consultas"))
        layout.addWidget(_hint(
            "Genera automáticamente paráfrasis de 5 tipos de intención (recomendación abierta, con caso de "
            "uso, comparativa, transaccional, informacional) simulando lenguaje real de usuario. Puedes "
            "revisar la lista antes de ejecutar el análisis."
        ))

        battery_row = QHBoxLayout()
        self.generate_battery_button = QPushButton("Generar batería de consultas")
        self.generate_battery_button.setStyleSheet(theme.BUTTON_SECONDARY_QSS)
        self.generate_battery_button.clicked.connect(self._generate_battery)
        battery_row.addWidget(self.generate_battery_button)
        self.battery_status = QLabel("")
        self.battery_status.setStyleSheet("font-size: 11.5px; color: #6B7280;")
        battery_row.addWidget(self.battery_status, stretch=1)
        layout.addLayout(battery_row)

        self.queries_list = QListWidget()
        self.queries_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.queries_list.setMaximumHeight(180)
        layout.addWidget(self.queries_list)

        remove_query_row = QHBoxLayout()
        remove_query_btn = QPushButton("Quitar consulta(s) seleccionada(s)")
        remove_query_btn.clicked.connect(self._remove_selected_queries)
        remove_query_row.addWidget(remove_query_btn)
        remove_query_row.addStretch(1)
        layout.addLayout(remove_query_row)

        rule = QFrame()
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setStyleSheet("color: #E5E7EB; margin: 8px 0;")
        layout.addWidget(rule)

    def _generate_battery(self) -> None:
        config = self._collect_config()
        if config is None:
            return
        self.generate_battery_button.setEnabled(False)
        self.battery_status.setText("Generando paráfrasis…")
        self._battery_worker = BatteryWorker(config.category, config.market, config.paraphrase_provider, bv.PARAPHRASES_PER_INTENT)
        self._battery_worker.finished_battery.connect(self._on_battery_ready)
        self._battery_worker.failed.connect(self._on_battery_failed)
        self._battery_worker.start()

    def _on_battery_failed(self, message: str) -> None:
        self.generate_battery_button.setEnabled(True)
        self.battery_status.setText(f"Error generando la batería: {message}")

    def _on_battery_ready(self, templates: list[bv.QueryTemplate]) -> None:
        self.generate_battery_button.setEnabled(True)
        self._queries = templates
        self.queries_list.clear()
        for t in templates:
            item = QListWidgetItem(f"[{bv.INTENT_LABELS.get(t.intent, t.intent)}] {t.text}")
            item.setData(Qt.ItemDataRole.UserRole, t)
            self.queries_list.addItem(item)
        self.battery_status.setText(f"{len(templates)} consultas generadas.")
        self._update_run_estimate()

    def _remove_selected_queries(self) -> None:
        for item in self.queries_list.selectedItems():
            row = self.queries_list.row(item)
            self.queries_list.takeItem(row)
        self._queries = [self.queries_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.queries_list.count())]
        self._update_run_estimate()

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _build_run_section(self, layout: QVBoxLayout) -> None:
        layout.addWidget(_section_header("3. Ejecutar análisis"))

        self.run_estimate_label = _hint("Genera la batería de consultas primero.")
        layout.addWidget(self.run_estimate_label)

        run_row = QHBoxLayout()
        self.run_button = QPushButton("Ejecutar análisis")
        self.run_button.setStyleSheet(theme.BUTTON_PRIMARY_QSS)
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self._run_analysis)
        run_row.addWidget(self.run_button)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        run_row.addWidget(self.progress_bar, stretch=1)
        layout.addLayout(run_row)

        self.run_status = QLabel("")
        self.run_status.setWordWrap(True)
        self.run_status.setStyleSheet("font-size: 11.5px; color: #6B7280;")
        layout.addWidget(self.run_status)

        rule = QFrame()
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setStyleSheet("color: #E5E7EB; margin: 8px 0;")
        layout.addWidget(rule)

    def _update_run_estimate(self) -> None:
        config = self._collect_config()
        if config is None or not self._queries:
            self.run_button.setEnabled(False)
            return
        total_calls = len(config.providers) * len(self._queries) * config.repetitions
        self.run_estimate_label.setText(
            f"Esto hará aproximadamente {total_calls} llamadas a LLMs (más llamadas adicionales para clasificar "
            f"el tono de cada mención encontrada). Puede tardar varios minutos y generar costo de API."
        )
        self.run_button.setEnabled(True)

    def _run_analysis(self) -> None:
        config = self._collect_config()
        if config is None or not self._queries:
            return
        self.run_button.setEnabled(False)
        self.generate_battery_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.run_status.setText("Ejecutando consultas…")

        self._run_worker = BrandVisibilityWorker(config, list(self._queries))
        self._run_worker.progress.connect(self._on_run_progress)
        self._run_worker.finished_run.connect(self._on_run_finished)
        self._run_worker.failed.connect(self._on_run_failed)
        self._run_worker.start()

    def _on_run_progress(self, done: int, total: int) -> None:
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)
        self.run_status.setText(f"Procesando respuesta {done} de {total}…")

    def _on_run_failed(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.generate_battery_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.run_status.setText(f"Error durante la ejecución: {message}")

    def _on_run_finished(self, report: bv.BrandVisibilityReport) -> None:
        self.run_button.setEnabled(True)
        self.generate_battery_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        errors = len(report.errors)
        self.run_status.setText(
            f"Análisis completo: {len(report.analyses)} respuestas procesadas"
            + (f", {errors} con error." if errors else ".")
        )
        self._current_report = report
        self._render_results(report)
        self._refresh_history()

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def _build_results_section(self, layout: QVBoxLayout) -> None:
        layout.addWidget(_section_header("4. Resultados"))

        export_row = QHBoxLayout()
        self.export_csv_button = QPushButton("Exportar CSV")
        self.export_csv_button.setEnabled(False)
        self.export_csv_button.clicked.connect(self._export_csv)
        self.export_html_button = QPushButton("Exportar reporte HTML")
        self.export_html_button.setEnabled(False)
        self.export_html_button.clicked.connect(self._export_html)
        export_row.addWidget(self.export_csv_button)
        export_row.addWidget(self.export_html_button)
        export_row.addStretch(1)
        layout.addLayout(export_row)

        self.results_tabs = QTabWidget()
        self.results_tabs.setMinimumHeight(320)
        self.overall_table = self._make_stats_table()
        self.provider_table = self._make_stats_table()
        self.intent_table = self._make_stats_table()
        self.results_tabs.addTab(self.overall_table, "Comparativa general")
        self.results_tabs.addTab(self.provider_table, "Por modelo")
        self.results_tabs.addTab(self.intent_table, "Por tipo de intención")
        layout.addWidget(self.results_tabs)

        layout.addWidget(_section_header("Historial (tracking longitudinal)"))
        layout.addWidget(_hint("Corridas anteriores para esta marca, guardadas localmente con su fecha, para comparar en el tiempo."))
        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(120)
        self.history_list.itemDoubleClicked.connect(self._load_history_item)
        layout.addWidget(self.history_list)

    def _make_stats_table(self) -> QTableWidget:
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(
            ["Marca", "Tasa de mención", "Posición promedio", "Share of voice", "Cita de dominio (búsqueda web)", "Framing"]
        )
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _fill_stats_table(self, table: QTableWidget, stats: list[bv.BrandStats]) -> None:
        stats = sorted(stats, key=lambda s: s.mention_rate, reverse=True)
        table.setRowCount(len(stats))
        for row, s in enumerate(stats):
            name_item = QTableWidgetItem(("★ " if s.is_target else "") + s.brand)
            table.setItem(row, 0, name_item)
            table.setItem(row, 1, QTableWidgetItem(f"{s.mention_rate:.0%}"))
            table.setItem(row, 2, QTableWidgetItem(f"{s.avg_position:.2f}" if s.avg_position is not None else "—"))
            table.setItem(row, 3, QTableWidgetItem(f"{s.share_of_voice:.0%}"))
            table.setItem(row, 4, QTableWidgetItem(f"{s.domain_citation_rate:.0%}" if s.domain_citation_rate is not None else "—"))
            framing_txt = ", ".join(
                f"{bv.FRAMING_LABELS[f]} {s.framing_distribution.get(f, 0.0):.0%}"
                for f in bv.FRAMINGS
                if s.framing_distribution.get(f)
            ) or "—"
            table.setItem(row, 5, QTableWidgetItem(framing_txt))

    def _render_results(self, report: bv.BrandVisibilityReport) -> None:
        overall = bv.compute_brand_stats(report.analyses, report.config)
        self._fill_stats_table(self.overall_table, overall)

        by_provider = bv.stats_by_provider(report.analyses, report.config)
        combined_provider: list[bv.BrandStats] = []
        for provider, stats in sorted(by_provider.items()):
            combined_provider.extend(stats)
        self._fill_stats_table(self.provider_table, combined_provider)

        by_intent = bv.stats_by_intent(report.analyses, report.config)
        combined_intent: list[bv.BrandStats] = []
        for intent, stats in sorted(by_intent.items()):
            combined_intent.extend(stats)
        self._fill_stats_table(self.intent_table, combined_intent)

        self.export_csv_button.setEnabled(True)
        self.export_html_button.setEnabled(True)

    def _export_csv(self) -> None:
        if not self._current_report:
            return
        path_str, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", paths.default_export_path("visibilidad_marca.csv"), "CSV (*.csv)")
        if not path_str:
            return
        bv.export_csv(self._current_report, Path(path_str))
        QMessageBox.information(self, "Exportado", f"CSV guardado en {path_str}")

    def _export_html(self) -> None:
        if not self._current_report:
            return
        path_str, _ = QFileDialog.getSaveFileName(self, "Exportar reporte HTML", paths.default_export_path("visibilidad_marca.html"), "HTML (*.html)")
        if not path_str:
            return
        bv.export_html_report(self._current_report, Path(path_str))
        if QMessageBox.question(self, "Exportado", f"Reporte guardado en {path_str}. ¿Abrirlo ahora?") == QMessageBox.StandardButton.Yes:
            webbrowser.open(Path(path_str).resolve().as_uri())

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def _refresh_history(self) -> None:
        if not self._current_report:
            return
        self.history_list.clear()
        for path in reversed(bv.list_runs(self._current_report.config.target.name)):
            data_ts = int(path.stem) / 1000
            label = time.strftime("%d/%m/%Y %H:%M", time.localtime(data_ts))
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.history_list.addItem(item)

    def _load_history_item(self, item: QListWidgetItem) -> None:
        path: Path = item.data(Qt.ItemDataRole.UserRole)
        try:
            report = bv.load_run(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Error", f"No se pudo cargar esa corrida: {exc}")
            return
        self._current_report = report
        self.run_status.setText(f"Mostrando corrida guardada del {time.strftime('%d/%m/%Y %H:%M', time.localtime(report.created_at))}.")
        self._render_results(report)
