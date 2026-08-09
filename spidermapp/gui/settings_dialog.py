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
from spidermapp.gui.account_tab import AccountTab
from spidermapp.gui.crawl_settings_widgets import USER_AGENT_PRESETS, EditableUrlList, hint


def _section_header(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-size: 12px; font-weight: 700; color: #C3C7D1; margin-top: 10px;")
    return label


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
        tabs.addTab(AccountTab(), "Cuenta")

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
        intro.setStyleSheet("color: #C3C7D1; font-size: 12px; margin-bottom: 8px;")
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

        self.prevent_sleep_checkbox = QCheckBox("Evitar que la Mac se suspenda mientras rastrea")
        self.prevent_sleep_checkbox.setChecked(settings.default_prevent_sleep)
        form.addRow("", self.prevent_sleep_checkbox)
        layout.addWidget(hint(
            "Si el equipo se suspende (por inactividad o al cerrar la tapa), el rastreo también se "
            "pausa — es una limitación del sistema operativo, no de la app. Con esta opción activa, "
            "Spidermapp le pide a macOS que no suspenda el equipo mientras un rastreo está en curso."
        ))

        layout.addStretch(1)
        return widget

    # ------------------------------------------------------------------
    # Rastreo: alcance y comportamiento frente al sitio
    # ------------------------------------------------------------------

    def _build_scope_tab(self, settings: app_settings.AppSettings) -> QWidget:
        outer_widget = QWidget()
        outer = QVBoxLayout(outer_widget)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        outer.addWidget(scroll)

        widget = QWidget()
        scroll.setWidget(widget)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(_section_header("Reglas del sitio"))
        self.respect_robots_check = QCheckBox("Respetar robots.txt")
        self.respect_robots_check.setChecked(settings.default_respect_robots)
        layout.addWidget(self.respect_robots_check)
        layout.addWidget(hint("El sitio publica en /robots.txt qué rutas no quiere que rastreen bots. Si lo desmarcas, el rastreo las visita igual — úsalo solo si sabes lo que haces."))

        self.include_subdomains_check = QCheckBox("Incluir subdominios")
        self.include_subdomains_check.setChecked(settings.default_include_subdomains)
        layout.addWidget(self.include_subdomains_check)
        layout.addWidget(hint("Trata blog.ejemplo.com, tienda.ejemplo.com, etc. como parte del mismo rastreo que ejemplo.com, en vez de ignorarlos."))

        layout.addWidget(_section_header("Alcance del rastreo"))
        self.limit_to_start_folder_check = QCheckBox("Limitar a la carpeta de inicio")
        self.limit_to_start_folder_check.setChecked(settings.default_limit_to_start_folder)
        layout.addWidget(self.limit_to_start_folder_check)
        layout.addWidget(hint("Si la URL semilla es ejemplo.com/blog/, solo rastrea dentro de /blog/ — ignora el resto del sitio aunque esté enlazado desde ahí. Útil para auditar una sola sección."))

        self.follow_nofollow_check = QCheckBox("Seguir enlaces marcados como \"nofollow\"")
        self.follow_nofollow_check.setChecked(settings.default_follow_nofollow)
        layout.addWidget(self.follow_nofollow_check)
        layout.addWidget(hint("rel=\"nofollow\" le pide a los motores de búsqueda que no sigan ese enlace. Desmárcalo para que el rastreo se comporte como Google: no seguir esos enlaces."))

        layout.addWidget(_section_header("Identificación"))
        layout.addWidget(hint("User-Agent con el que el rastreador se identifica ante el servidor. Algunos sitios bloquean o sirven contenido distinto según este valor."))
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
        return outer_widget

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
        outer_widget = QWidget()
        outer = QVBoxLayout(outer_widget)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        outer.addWidget(scroll)

        widget = QWidget()
        scroll.setWidget(widget)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(_section_header("Trampas de rastreo"))
        layout.addWidget(hint("Sitios con filtros, calendarios o sesiones pueden generar URLs infinitas. Estos dos límites cortan esas trampas antes de que consuman todo el presupuesto de páginas."))

        length_row = QHBoxLayout()
        length_row.addWidget(QLabel("Longitud máxima de URL:"))
        self.max_url_length_spin = QSpinBox()
        self.max_url_length_spin.setRange(0, 10000)
        self.max_url_length_spin.setSingleStep(50)
        self.max_url_length_spin.setValue(settings.default_max_url_length)
        length_row.addWidget(self.max_url_length_spin)
        length_row.addWidget(QLabel("caracteres (0 = sin límite)"))
        length_row.addStretch(1)
        layout.addLayout(length_row)

        query_row = QHBoxLayout()
        query_row.addWidget(QLabel("Máx. parámetros de consulta por URL:"))
        self.max_query_params_spin = QSpinBox()
        self.max_query_params_spin.setRange(0, 50)
        self.max_query_params_spin.setValue(settings.default_max_query_params)
        query_row.addWidget(self.max_query_params_spin)
        query_row.addWidget(QLabel("(0 = sin límite)"))
        query_row.addStretch(1)
        layout.addLayout(query_row)
        layout.addWidget(hint("Ej: ejemplo.com/tienda?color=azul&talla=m&orden=precio tiene 3 parámetros. Un límite bajo evita rastrear cada combinación de filtros como si fuera una página distinta."))

        links_row = QHBoxLayout()
        links_row.addWidget(QLabel("Máx. enlaces a seguir por página:"))
        self.max_links_per_page_spin = QSpinBox()
        self.max_links_per_page_spin.setRange(0, 10000)
        self.max_links_per_page_spin.setSingleStep(10)
        self.max_links_per_page_spin.setValue(settings.default_max_links_per_page)
        links_row.addWidget(self.max_links_per_page_spin)
        links_row.addWidget(QLabel("(0 = sin límite)"))
        links_row.addStretch(1)
        layout.addLayout(links_row)
        layout.addWidget(hint('Limita cuántos enlaces nuevos se toman de una sola página. Útil si el sitio tiene páginas "hub" con miles de enlaces (ej. un índice de etiquetas) que no quieres que dominen el rastreo.'))

        layout.addWidget(_section_header("Exclusión y prioridad"))
        layout.addWidget(hint("Excluir por patrón (expresión regular). Ninguna URL que coincida se rastreará, ej. /wp-admin/ o \\.pdf$"))
        self.exclude_list = EditableUrlList("Ej: /carrito|\\?sessionid=", settings.default_exclude_patterns)
        layout.addWidget(self.exclude_list)

        layout.addWidget(hint("URLs prioritarias: se rastrean primero y se marcan como importantes en los hallazgos."))
        self.priority_list = EditableUrlList("Ej: https://ejemplo.com/categoria-clave", settings.default_priority_urls)
        layout.addWidget(self.priority_list)

        layout.addStretch(1)
        return outer_widget

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
        intro.setStyleSheet("color: #C3C7D1; font-size: 12px;")
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
                default_limit_to_start_folder=self.limit_to_start_folder_check.isChecked(),
                default_follow_nofollow=self.follow_nofollow_check.isChecked(),
                default_max_query_params=self.max_query_params_spin.value(),
                default_max_links_per_page=self.max_links_per_page_spin.value(),
                default_prevent_sleep=self.prevent_sleep_checkbox.isChecked(),
                backend_url=app_settings.load_settings().backend_url,
            )
        )
        config = {key: field.text().strip() for key, field in self._connector_fields.items() if field.text().strip()}
        connectors.save_config(config)
        self.accept()
