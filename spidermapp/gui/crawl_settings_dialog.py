from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core.models import CrawlConfig

# Presets a user is likely to want without typing a full UA string by hand.
# "Personalizado" leaves the field free-text.
USER_AGENT_PRESETS = {
    "Spidermapp (por defecto)": CrawlConfig.__dataclass_fields__["user_agent"].default,
    "Googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Bingbot": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Chrome de escritorio": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("font-size: 11px; color: #6B7280; margin-bottom: 4px;")
    return label


class _EditableUrlList(QWidget):
    """A QListWidget plus an add/remove row, used for both exclude patterns
    and priority URLs — the two "small list of strings" settings here."""

    def __init__(self, placeholder: str, items: list[str], parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.addItems(items)
        self.list_widget.setMaximumHeight(110)
        layout.addWidget(self.list_widget)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.returnPressed.connect(self._add)
        row.addWidget(self.input, stretch=1)

        add_btn = QPushButton("+ Añadir")
        add_btn.clicked.connect(self._add)
        row.addWidget(add_btn)

        remove_btn = QPushButton("- Quitar seleccionado")
        remove_btn.clicked.connect(self._remove_selected)
        row.addWidget(remove_btn)
        layout.addLayout(row)

    def _add(self) -> None:
        text = self.input.text().strip()
        if text:
            self.list_widget.addItem(text)
            self.input.clear()

    def _remove_selected(self) -> None:
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))

    def values(self) -> list[str]:
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]


class CrawlSettingsDialog(QDialog):
    """Opciones avanzadas del rastreador, agrupadas por lo que el usuario
    normalmente decide primero: alcance y comportamiento (Rastreo), qué
    excluir o priorizar (Límites), y ajustes técnicos poco frecuentes
    (Avanzado). Las opciones rápidas (páginas, profundidad, hilos,
    renderizar JS) se quedan en la barra principal porque se tocan en
    casi cada rastreo; estas son las que se configuran una vez y rara
    vez se vuelven a tocar."""

    def __init__(self, current: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración del rastreo")
        self.resize(560, 480)

        outer = QVBoxLayout(self)

        from PySide6.QtWidgets import QTabWidget

        tabs = QTabWidget()
        outer.addWidget(tabs)

        tabs.addTab(self._build_scope_tab(current), "Rastreo")
        tabs.addTab(self._build_limits_tab(current), "Límites")
        tabs.addTab(self._build_advanced_tab(current), "Avanzado")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    # ------------------------------------------------------------------
    # Tab 1: qué rastrear y cómo comportarse frente al sitio
    # ------------------------------------------------------------------

    def _build_scope_tab(self, current: dict) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(_hint("Reglas que el sitio ya publica y alcance del dominio."))

        self.respect_robots_check = QCheckBox("Respetar robots.txt")
        self.respect_robots_check.setChecked(current.get("respect_robots", True))
        self.respect_robots_check.setToolTip("Si lo desmarcas, el rastreo ignora las reglas Disallow del sitio — úsalo solo si sabes lo que haces.")
        layout.addWidget(self.respect_robots_check)

        self.include_subdomains_check = QCheckBox("Incluir subdominios")
        self.include_subdomains_check.setChecked(current.get("include_subdomains", False))
        self.include_subdomains_check.setToolTip("Trata blog.ejemplo.com, tienda.ejemplo.com, etc. como parte del mismo rastreo.")
        layout.addWidget(self.include_subdomains_check)

        layout.addWidget(_hint("User-Agent con el que el rastreador se identifica ante el servidor."))
        ua_row = QHBoxLayout()
        self.user_agent_combo = QComboBox()
        self.user_agent_combo.addItems(list(USER_AGENT_PRESETS.keys()) + ["Personalizado"])
        ua_row.addWidget(self.user_agent_combo)
        layout.addLayout(ua_row)

        self.user_agent_input = QLineEdit()
        current_ua = current.get("user_agent", USER_AGENT_PRESETS["Spidermapp (por defecto)"])
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
    # Tab 2: qué excluir o priorizar dentro de ese alcance
    # ------------------------------------------------------------------

    def _build_limits_tab(self, current: dict) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(_hint("URLs más largas que este límite no se rastrean (0 = sin límite). Útil para evitar trampas de parámetros infinitos."))
        length_row = QHBoxLayout()
        length_row.addWidget(QLabel("Longitud máxima de URL:"))
        self.max_url_length_spin = QSpinBox()
        self.max_url_length_spin.setRange(0, 10000)
        self.max_url_length_spin.setSingleStep(50)
        self.max_url_length_spin.setValue(current.get("max_url_length", 0))
        length_row.addWidget(self.max_url_length_spin)
        length_row.addStretch(1)
        layout.addLayout(length_row)

        layout.addWidget(_hint("Excluir por patrón (expresión regular). Ninguna URL que coincida se rastreará, ej. /wp-admin/ o \\.pdf$"))
        self.exclude_list = _EditableUrlList("Ej: /carrito|\\?sessionid=", current.get("exclude_patterns", []))
        layout.addWidget(self.exclude_list)

        layout.addWidget(_hint("URLs prioritarias: se rastrean primero y se marcan como importantes en los hallazgos."))
        self.priority_list = _EditableUrlList("Ej: https://ejemplo.com/categoria-clave", current.get("priority_urls", []))
        layout.addWidget(self.priority_list)

        return widget

    # ------------------------------------------------------------------
    # Tab 3: ajustes técnicos que casi nunca cambian
    # ------------------------------------------------------------------

    def _build_advanced_tab(self, current: dict) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(_hint("Cuánto esperar por la respuesta de cada URL antes de darla por caída."))
        timeout_row = QHBoxLayout()
        timeout_row.addWidget(QLabel("Tiempo de espera (segundos):"))
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(1.0, 120.0)
        self.timeout_spin.setSingleStep(1.0)
        self.timeout_spin.setValue(current.get("request_timeout", 15.0))
        timeout_row.addWidget(self.timeout_spin)
        timeout_row.addStretch(1)
        layout.addLayout(timeout_row)

        layout.addStretch(1)
        return widget

    # ------------------------------------------------------------------

    def result_config(self) -> dict:
        return {
            "respect_robots": self.respect_robots_check.isChecked(),
            "include_subdomains": self.include_subdomains_check.isChecked(),
            "user_agent": self.user_agent_input.text().strip() or USER_AGENT_PRESETS["Spidermapp (por defecto)"],
            "max_url_length": self.max_url_length_spin.value(),
            "exclude_patterns": self.exclude_list.values(),
            "priority_urls": self.priority_list.values(),
            "request_timeout": self.timeout_spin.value(),
        }
