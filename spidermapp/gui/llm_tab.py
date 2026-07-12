from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import connectors, llm_visibility
from spidermapp.gui import theme


class LlmWorker(QThread):
    finished_report = Signal(object)  # LlmVisibilityReport
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


class LlmVisibilityTab(QWidget):
    """Point 1: does each LLM mention this domain when asked the questions
    the site is optimized for? Requires API keys from the Conectores menu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: LlmWorker | None = None
        self._seed_url = ""
        self._keywords: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        self.status_label = QLabel(
            "Corre un crawl primero; luego este análisis pregunta a cada LLM configurado "
            "(Conectores → Configurar APIs) por las keywords del sitio y detecta si menciona tu dominio."
        )
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #4B5563; font-size: 12px;")
        header_row.addWidget(self.status_label, stretch=1)

        self.run_button = QPushButton("Ejecutar análisis")
        self.run_button.setStyleSheet(theme.BUTTON_PRIMARY_QSS)
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
        layout.addWidget(self.table, stretch=1)

    def set_crawl_data(self, seed_url: str, pages) -> None:
        self._seed_url = seed_url
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
                    "No hay ningún LLM configurado todavía. Ve a Conectores → Configurar APIs y agrega al menos una clave "
                    "(OpenAI, Anthropic, Gemini, DeepSeek o Perplexity)."
                )

    def _run(self) -> None:
        self.run_button.setEnabled(False)
        self.summary_label.setText("Consultando LLMs… esto puede tardar un momento.")
        self.table.setRowCount(0)
        self._worker = LlmWorker(self._seed_url, self._keywords)
        self._worker.finished_report.connect(self._on_report)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

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
