from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import ai_visibility, connectors, llm_visibility
from spidermapp.gui import theme
from spidermapp.gui.dashboard import _fact_pill


class AiVisibilityWorker(QThread):
    """Public/keyless "AI readiness" check: robots.txt AI-bot rules,
    llms.txt, structured data, meta descriptions, Wikipedia presence."""

    finished_report = Signal(object)  # ai_visibility.AiVisibilityReport
    failed = Signal(str)

    def __init__(self, seed_url: str, pages, parent=None):
        super().__init__(parent)
        self._seed_url = seed_url
        self._pages = pages

    def run(self) -> None:
        try:
            report = ai_visibility.analyze(self._seed_url, self._pages)
            self.finished_report.emit(report)
        except Exception as exc:  # noqa: BLE001 - surfaced in the tab
            self.failed.emit(str(exc))


class LlmWorker(QThread):
    finished_report = Signal(object)  # llm_visibility.LlmVisibilityReport
    failed = Signal(str)

    def __init__(self, seed_url: str, site_keywords: list[str], parent=None):
        super().__init__(parent)
        self._seed_url = seed_url
        self._keywords = site_keywords

    def run(self) -> None:
        try:
            report = llm_visibility.run_visibility_check(self._seed_url, self._keywords)
            self.finished_report.emit(report)
        except Exception as exc:  # noqa: BLE001 - surfaced in the tab
            self.failed.emit(str(exc))


def _score_color(score: int) -> str:
    if score < 50:
        return theme.CRITICAL_HEX
    if score < 80:
        return theme.WARNING_HEX
    return theme.GOOD_HEX


class LlmVisibilityTab(QWidget):
    """Two independent checks of how visible a site is to AI systems:
    a public/keyless "readiness" audit that always works, and an optional
    direct-query check against configured LLM providers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ai_worker: AiVisibilityWorker | None = None
        self._llm_worker: LlmWorker | None = None
        self._seed_url = ""
        self._pages: list = []
        self._keywords: list[str] = []

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

        self._build_readiness_section(layout)
        self._build_llm_query_section(layout)
        layout.addStretch(1)

    # ---------- Section 1: público, sin API ----------

    def _build_readiness_section(self, layout: QVBoxLayout) -> None:
        header = QLabel("Preparación para IA")
        header.setStyleSheet("font-size: 14px; font-weight: 700; color: #111827;")
        layout.addWidget(header)

        sub = QLabel(
            "Qué tan lista está la web para que los sistemas de IA la lean y la citen — señales públicas "
            "(robots.txt, llms.txt, datos estructurados, Wikipedia). No requiere ninguna clave API."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("font-size: 11.5px; color: #6B7280;")
        layout.addWidget(sub)

        self.readiness_status = QLabel("Corre un crawl para ver este análisis.")
        self.readiness_status.setStyleSheet("font-size: 12px; color: #6B7280; margin-top: 4px;")
        layout.addWidget(self.readiness_status)

        self.readiness_container = QWidget()
        self.readiness_layout = QVBoxLayout(self.readiness_container)
        self.readiness_layout.setContentsMargins(0, 6, 0, 0)
        self.readiness_layout.setSpacing(8)
        layout.addWidget(self.readiness_container)

        rule = QFrame()
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setStyleSheet("color: #E5E7EB; margin: 10px 0;")
        layout.addWidget(rule)

    def _clear(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_crawl_data(self, seed_url: str, pages) -> None:
        self._seed_url = seed_url
        self._pages = pages
        self._keywords = llm_visibility.top_site_keywords(pages)
        has_data = bool(seed_url and pages)
        self.run_button.setEnabled(has_data)

        if has_data:
            configured = [p for p in connectors.LLM_PROVIDERS if connectors.is_configured(p)]
            if configured:
                labels = ", ".join(llm_visibility.PROVIDER_LABELS[p] for p in configured)
                self.status_label.setText(f"Keywords del sitio: {', '.join(self._keywords) or '—'}. LLMs configurados: {labels}.")
            else:
                self.status_label.setText(
                    "Opcional: configura al menos una clave de LLM en Archivo → Configuración para además "
                    "preguntarle directamente (OpenAI, Anthropic, Gemini, DeepSeek o Perplexity)."
                )
            self._run_readiness_check()
        else:
            self.readiness_status.setText("Corre un crawl para ver este análisis.")
            self._clear(self.readiness_layout)

    def _run_readiness_check(self) -> None:
        self.readiness_status.setText("Analizando señales públicas de IA…")
        self._clear(self.readiness_layout)
        self._ai_worker = AiVisibilityWorker(self._seed_url, self._pages)
        self._ai_worker.finished_report.connect(self._on_readiness_report)
        self._ai_worker.failed.connect(self._on_readiness_failed)
        self._ai_worker.start()

    def _on_readiness_failed(self, message: str) -> None:
        self.readiness_status.setText(f"No se pudo completar el análisis público: {message}")

    def _on_readiness_report(self, report: ai_visibility.AiVisibilityReport) -> None:
        score = report.readiness_score
        color = _score_color(score)
        self.readiness_status.setText("")
        self._clear(self.readiness_layout)

        score_row = QHBoxLayout()
        score_label = QLabel(f"Puntaje de preparación: <span style='color:{color}; font-weight:700;'>{score}/100</span>")
        score_label.setTextFormat(Qt.TextFormat.RichText)
        score_label.setStyleSheet("font-size: 13px;")
        score_row.addWidget(score_label)
        score_row.addStretch(1)
        score_container = QWidget()
        score_container.setLayout(score_row)
        self.readiness_layout.addWidget(score_container)

        # bots
        bots_header = QLabel("Acceso de bots de IA (robots.txt)")
        bots_header.setStyleSheet("font-size: 12px; font-weight: 700; color: #374151; margin-top: 4px;")
        self.readiness_layout.addWidget(bots_header)

        if not report.robots_found:
            note = QLabel("No se encontró robots.txt — se asume que todos los bots están permitidos.")
            note.setStyleSheet("font-size: 11.5px; color: #9CA3AF;")
            self.readiness_layout.addWidget(note)

        bots_grid = QGridLayout()
        bots_grid.setHorizontalSpacing(10)
        bots_grid.setVerticalSpacing(4)
        for row, bot in enumerate(report.bot_access):
            name = QLabel(bot.bot)
            name.setStyleSheet("font-size: 11.5px; font-weight: 600; color: #111827;")
            name.setFixedWidth(120)
            desc = QLabel(bot.description)
            desc.setStyleSheet("font-size: 11.5px; color: #6B7280;")
            pill = _fact_pill(bot.allowed, "Permitido", "Bloqueado")
            bots_grid.addWidget(name, row, 0)
            bots_grid.addWidget(desc, row, 1)
            bots_grid.addWidget(pill, row, 2)
        bots_grid_container = QWidget()
        bots_grid_container.setLayout(bots_grid)
        self.readiness_layout.addWidget(bots_grid_container)

        # other signals
        signals_header = QLabel("Otras señales públicas")
        signals_header.setStyleSheet("font-size: 12px; font-weight: 700; color: #374151; margin-top: 8px;")
        self.readiness_layout.addWidget(signals_header)

        signals_row = QHBoxLayout()
        signals_row.setSpacing(8)
        signals_row.addWidget(_fact_pill(report.llms_txt_found, "llms.txt encontrado", "Sin llms.txt"))
        sd_pct = f"{report.structured_data_ratio:.0%}"
        signals_row.addWidget(
            _fact_pill(report.structured_data_ratio > 0, f"Datos estructurados en {sd_pct} de páginas", "Sin datos estructurados (JSON-LD)")
        )
        md_pct = f"{report.meta_description_ratio:.0%}"
        signals_row.addWidget(_fact_pill(report.meta_description_ratio > 0.5, f"Meta description en {md_pct} de páginas", "Meta description incompleta"))
        signals_row.addStretch(1)
        signals_container = QWidget()
        signals_container.setLayout(signals_row)
        self.readiness_layout.addWidget(signals_container)

        if report.structured_data_types:
            types_label = QLabel("Tipos de datos estructurados detectados: " + ", ".join(report.structured_data_types))
            types_label.setWordWrap(True)
            types_label.setStyleSheet("font-size: 11px; color: #9CA3AF;")
            self.readiness_layout.addWidget(types_label)

        wiki_row = QHBoxLayout()
        wiki_row.setSpacing(8)
        if report.wikipedia_found:
            wiki_label = QLabel(f'✓ Tiene artículo en Wikipedia: <a href="{report.wikipedia_url}">{report.wikipedia_title}</a>')
            wiki_label.setTextFormat(Qt.TextFormat.RichText)
            wiki_label.setOpenExternalLinks(True)
            wiki_label.setStyleSheet(f"font-size: 11.5px; color: {theme.GOOD_HEX};")
        else:
            wiki_label = QLabel("✕ No se encontró un artículo de Wikipedia para esta marca.")
            wiki_label.setStyleSheet("font-size: 11.5px; color: #9CA3AF;")
        wiki_row.addWidget(wiki_label)
        wiki_row.addStretch(1)
        wiki_container = QWidget()
        wiki_container.setLayout(wiki_row)
        self.readiness_layout.addWidget(wiki_container)

    # ---------- Section 2: consulta directa a LLMs (opcional) ----------

    def _build_llm_query_section(self, layout: QVBoxLayout) -> None:
        header = QLabel("Consulta directa a LLMs (opcional)")
        header.setStyleSheet("font-size: 14px; font-weight: 700; color: #111827;")
        layout.addWidget(header)

        header_row = QHBoxLayout()
        self.status_label = QLabel(
            "Le pregunta a cada LLM configurado por las keywords del sitio y detecta si menciona tu dominio "
            "en la respuesta. Requiere claves API (Archivo → Configuración → Conectores)."
        )
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #6B7280; font-size: 11.5px;")
        header_row.addWidget(self.status_label, stretch=1)

        self.run_button = QPushButton("Ejecutar análisis")
        self.run_button.setStyleSheet(theme.BUTTON_SECONDARY_QSS)
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self._run)
        header_row.addWidget(self.run_button)
        layout.addLayout(header_row)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.summary_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["LLM", "Pregunta", "¿Menciona el dominio?", "Extracto / error"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 330)
        self.table.setColumnWidth(2, 150)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(220)
        layout.addWidget(self.table)

    def _run(self) -> None:
        self.run_button.setEnabled(False)
        self.summary_label.setText("Consultando LLMs… esto puede tardar un momento.")
        self.table.setRowCount(0)
        self._llm_worker = LlmWorker(self._seed_url, self._keywords)
        self._llm_worker.finished_report.connect(self._on_report)
        self._llm_worker.failed.connect(self._on_failed)
        self._llm_worker.start()

    def _on_failed(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.summary_label.setText(f'<span style="color:{theme.CRITICAL_HEX};">Error: {message}</span>')

    def _on_report(self, report) -> None:
        self.run_button.setEnabled(True)

        parts = []
        for provider, rate in report.mention_rate_by_provider.items():
            color = theme.GOOD_HEX if rate >= 0.5 else (theme.WARNING_HEX if rate > 0 else theme.CRITICAL_HEX)
            parts.append(
                f'<b>{llm_visibility.PROVIDER_LABELS[provider]}</b>: '
                f'<span style="color:{color}; font-weight:700;">{rate:.0%}</span> de menciones'
            )
        if report.providers_unconfigured:
            missing = ", ".join(llm_visibility.PROVIDER_LABELS[p] for p in report.providers_unconfigured)
            parts.append(f'<span style="color:#9CA3AF;">Sin configurar: {missing}</span>')
        self.summary_label.setText(" &nbsp;·&nbsp; ".join(parts) if parts else "Sin resultados.")

        self.table.setRowCount(len(report.results))
        for row, r in enumerate(report.results):
            self.table.setItem(row, 0, QTableWidgetItem(llm_visibility.PROVIDER_LABELS.get(r.provider, r.provider)))
            self.table.setItem(row, 1, QTableWidgetItem(r.query))
            verdict = QTableWidgetItem("Error" if r.error else ("Sí ✓" if r.mentioned else "No"))
            color = theme.WARNING_HEX if r.error else (theme.GOOD_HEX if r.mentioned else theme.CRITICAL_HEX)
            verdict.setForeground(QColor(color))
            self.table.setItem(row, 2, verdict)
            self.table.setItem(row, 3, QTableWidgetItem(r.error or r.answer_excerpt))
