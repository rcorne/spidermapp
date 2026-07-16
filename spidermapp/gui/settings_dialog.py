from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import app_settings, connectors
from spidermapp.gui.crawl_settings_widgets import USER_AGENT_PRESETS, EditableUrlList, hint


class SettingsDialog(QDialog):
    """Every Spidermapp setting, in one window: crawl defaults, advanced
    crawl behavior, and every external API key. Archivo → Preferencias
    (Cmd+,) — nothing configurable lives anywhere else."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferencias")
        self.resize(680, 580)

        outer = QVBoxLayout(self)
        tabs = QTabWidget()
        outer.addWidget(tabs, stretch=1)

        settings = app_settings.load_settings()

        tabs.addTab(self._build_general_tab(settings), "General")
        tabs.addTab(self._build_scope_tab(settings), "Rastreo")
        tabs.addTab(self._build_limits_tab(settings), "Límites")
        tabs.addTab(self._build_advanced_tab(settings), "Avanzado")
        tabs.addTab(self._build_connectors_tab(), "Conectores")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    # ------------------------------------------------------------------
    # General: lo que se toca en casi cada rastreo
    # ------------------------------------------------------------------

    def _build_general_tab(self, settings: app_settings.AppSettings) -> QWidget:
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

    # ------------------------------------------------------------------
    # Rastreo: alcance y comportamiento frente al sitio
    # ------------------------------------------------------------------

    def _build_scope_tab(self, settings: app_settings.AppSettings) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(hint("Reglas que el sitio ya publica y alcance del dominio."))

        self.respect_robots_check = QCheckBox("Respetar robots.txt")
        self.respect_robots_check.setChecked(settings.default_respect_robots)
        self.respect_robots_check.setToolTip("Si lo desmarcas, el rastreo ignora las reglas Disallow del sitio — úsalo solo si sabes lo que haces.")
        layout.addWidget(self.respect_robots_check)

        self.include_subdomains_check = QCheckBox("Incluir subdominios")
        self.include_subdomains_check.setChecked(settings.default_include_subdomains)
        self.include_subdomains_check.setToolTip("Trata blog.ejemplo.com, tienda.ejemplo.com, etc. como parte del mismo rastreo.")
        layout.addWidget(self.include_subdomains_check)

        layout.addWidget(hint("User-Agent con el que el rastreador se identifica ante el servidor."))
        ua_row = QHBoxLayout()
        self.user_agent_combo = QComboBox()
        self.user_agent_combo.addItems(list(USER_AGENT_PRESETS.keys()) + ["Personalizado"])
        ua_row.addWidget(self.user_agent_combo)
        layout.addLayout(ua_row)

        self.user_agent_input = QLineEdit()
        current_ua = settings.default_user_agent
        self.user_agent_input.setText(current_ua)
        preset_name = next((name for name, value in USER_AGENT_PRESETS.items() if value == current_ua), "Personalizado")
        self.user_agent_combo.setCurrentText(preset_name)
        self.user_agent_input.setEnabled(preset_name == "Personalizado")
        self.user_agent_combo.currentTextChanged.connect(self._on_user_agent_preset_changed)
        layout.addWidget(self.user_agent_input)

        layout.addStretch(1)
        return widget

    def _on_user_agent_preset_changed(self, name: str) -> None:
        if name in USER_AGENT_PRESETS:
            self.user_agent_input.setText(USER_AGENT_PRESETS[name])
            self.user_agent_input.setEnabled(False)
        else:
            self.user_agent_input.setEnabled(True)

    # ------------------------------------------------------------------
    # Límites: qué excluir o priorizar dentro de ese alcance
    # ------------------------------------------------------------------

    def _build_limits_tab(self, settings: app_settings.AppSettings) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(hint("URLs más largas que este límite no se rastrean (0 = sin límite). Útil para evitar trampas de parámetros infinitos."))
        length_row = QHBoxLayout()
        length_row.addWidget(QLabel("Longitud máxima de URL:"))
        self.max_url_length_spin = QSpinBox()
        self.max_url_length_spin.setRange(0, 10000)
        self.max_url_length_spin.setSingleStep(50)
        self.max_url_length_spin.setValue(settings.default_max_url_length)
        length_row.addWidget(self.max_url_length_spin)
        length_row.addStretch(1)
        layout.addLayout(length_row)

        layout.addWidget(hint("Excluir por patrón (expresión regular). Ninguna URL que coincida se rastreará, ej. /wp-admin/ o \\.pdf$"))
        self.exclude_list = EditableUrlList("Ej: /carrito|\\?sessionid=", settings.default_exclude_patterns)
        layout.addWidget(self.exclude_list)

        layout.addWidget(hint("URLs prioritarias: se rastrean primero y se marcan como importantes en los hallazgos."))
        self.priority_list = EditableUrlList("Ej: https://ejemplo.com/categoria-clave", settings.default_priority_urls)
        layout.addWidget(self.priority_list)

        return widget

    # ------------------------------------------------------------------
    # Avanzado: ajustes técnicos que casi nunca cambian
    # ------------------------------------------------------------------

    def _build_advanced_tab(self, settings: app_settings.AppSettings) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(hint("Cuánto esperar por la respuesta de cada URL antes de darla por caída."))
        timeout_row = QHBoxLayout()
        timeout_row.addWidget(QLabel("Tiempo de espera (segundos):"))
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(1.0, 120.0)
        self.timeout_spin.setSingleStep(1.0)
        self.timeout_spin.setValue(settings.default_request_timeout)
        timeout_row.addWidget(self.timeout_spin)
        timeout_row.addStretch(1)
        layout.addLayout(timeout_row)

        layout.addStretch(1)
        return widget

    # ------------------------------------------------------------------
    # Conectores: claves de servicios externos
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------

    def _save(self) -> None:
        app_settings.save_settings(
            app_settings.AppSettings(
                default_max_pages=self.max_pages_input.value(),
                default_max_depth=self.max_depth_input.value(),
                default_concurrency=self.concurrency_input.value(),
                default_render_js=self.render_js_checkbox.isChecked(),
                default_respect_robots=self.respect_robots_check.isChecked(),
                default_include_subdomains=self.include_subdomains_check.isChecked(),
                default_user_agent=self.user_agent_input.text().strip() or USER_AGENT_PRESETS["Spidermapp (por defecto)"],
                default_max_url_length=self.max_url_length_spin.value(),
                default_request_timeout=self.timeout_spin.value(),
                default_exclude_patterns=self.exclude_list.values(),
                default_priority_urls=self.priority_list.values(),
            )
        )
        config = {key: field.text().strip() for key, field in self._connector_fields.items() if field.text().strip()}
        connectors.save_config(config)
        self.accept()
