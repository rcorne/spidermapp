from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import app_settings, connectors


class SettingsDialog(QDialog):
    """One window for every tool setting: crawl defaults and every external
    API key Spidermapp can use. Archivo → Configuración… (Cmd+,)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración")
        self.resize(680, 580)

        outer = QVBoxLayout(self)
        tabs = QTabWidget()
        outer.addWidget(tabs, stretch=1)

        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_connectors_tab(), "Conectores")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _build_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        intro = QLabel("Valores por defecto para cada crawl nuevo. Siempre puedes ajustarlos en la barra superior antes de iniciar.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #4B5563; font-size: 12px; margin-bottom: 8px;")
        layout.addWidget(intro)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addLayout(form)

        settings = app_settings.load_settings()

        self.max_pages_input = QSpinBox()
        self.max_pages_input.setRange(1, 10000)
        self.max_pages_input.setValue(settings.default_max_pages)
        form.addRow("Máx. páginas:", self.max_pages_input)

        self.max_depth_input = QSpinBox()
        self.max_depth_input.setRange(1, 100)
        self.max_depth_input.setValue(settings.default_max_depth)
        form.addRow("Máx. profundidad:", self.max_depth_input)

        self.concurrency_input = QSpinBox()
        self.concurrency_input.setRange(1, 64)
        self.concurrency_input.setValue(settings.default_concurrency)
        form.addRow("Concurrencia:", self.concurrency_input)

        self.render_js_checkbox = QCheckBox("Renderizar JS por defecto")
        self.render_js_checkbox.setChecked(settings.default_render_js)
        form.addRow("", self.render_js_checkbox)

        layout.addStretch(1)
        return widget

    def _build_connectors_tab(self) -> QWidget:
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(16, 16, 16, 16)

        intro = QLabel(
            "Pega aquí tus claves API. Cada análisis funciona solo con los servicios que configures; "
            "los demás quedan desactivados. Las claves se guardan únicamente en tu Mac "
            "(~/.spidermapp/connectors.json)."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #4B5563; font-size: 12px;")
        outer.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, stretch=1)

        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        scroll.setWidget(form_host)

        config = connectors.load_config()
        self._connector_fields: dict[str, QLineEdit] = {}
        for spec in connectors.CONNECTORS:
            field = QLineEdit(config.get(spec.key, ""))
            field.setEchoMode(QLineEdit.EchoMode.Password)
            field.setPlaceholderText(spec.field_label)
            self._connector_fields[spec.key] = field

            label = QLabel(f'{spec.label}<br><a href="{spec.help_url}" style="font-size:10px;">Cómo obtener la clave</a>')
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setOpenExternalLinks(True)
            if spec.needs_oauth:
                label.setToolTip("Este servicio requiere configuración OAuth adicional; la clave se guarda para la integración futura.")
            form.addRow(label, field)

        return widget

    def _save(self) -> None:
        app_settings.save_settings(
            app_settings.AppSettings(
                default_max_pages=self.max_pages_input.value(),
                default_max_depth=self.max_depth_input.value(),
                default_concurrency=self.concurrency_input.value(),
                default_render_js=self.render_js_checkbox.isChecked(),
            )
        )
        config = {key: field.text().strip() for key, field in self._connector_fields.items() if field.text().strip()}
        connectors.save_config(config)
        self.accept()
