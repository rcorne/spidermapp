from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import auth
from spidermapp.gui import theme
from spidermapp.gui.crawl_settings_widgets import hint

_APPLE_KEY_HINT = (
    "Apple exige que el client secret sea un JWT firmado con tu clave privada de "
    "Sign in with Apple (.p8) — no un texto simple como Google/LinkedIn. "
    "Necesitas una cuenta de Apple Developer paga para generar esta clave."
)


class LoginWorker(QThread):
    finished_login = Signal(dict)
    failed = Signal(str)

    def __init__(self, provider_key: str, client_id: str, client_secret: str, parent=None):
        super().__init__(parent)
        self._provider_key = provider_key
        self._client_id = client_id
        self._client_secret = client_secret

    def run(self) -> None:
        try:
            session = auth.run_login_flow(self._provider_key, self._client_id, self._client_secret)
            self.finished_login.emit(session)
        except auth.AuthError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - surfaced to the user via a dialog
            self.failed.emit(str(exc))


class AccountTab(QWidget):
    """Archivo → Preferencias → Cuenta. Inicia sesión vía OAuth 2.0 con
    Google, LinkedIn o Apple — el flujo estándar para apps de escritorio
    (RFC 8252): abre el navegador del sistema y captura el redirect en un
    servidor local. Spidermapp no puede registrar apps OAuth en tu nombre;
    cada proveedor exige que tú mismo crees una app en su consola con
    http://127.0.0.1:53682/callback como URI de redirección."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: dict[str, LoginWorker] = {}
        self._provider_fields: dict[str, dict[str, QLineEdit]] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.session_box = QFrame()
        self.session_layout = QVBoxLayout(self.session_box)
        self.session_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.session_box)
        self._render_session()

        layout.addWidget(hint(
            "Cada proveedor requiere su propia app OAuth registrada en su consola de desarrolladores, "
            "con http://127.0.0.1:53682/callback como URI de redirección exacta."
        ))

        for provider_key in ("google", "linkedin", "apple"):
            layout.addWidget(self._build_provider_section(provider_key))

        layout.addStretch(1)

    # ------------------------------------------------------------------

    def _render_session(self) -> None:
        while self.session_layout.count():
            item = self.session_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        session = auth.load_session()
        if not session:
            label = QLabel("No has iniciado sesión.")
            label.setStyleSheet("font-size: 12.5px; color: #6B7280;")
            self.session_layout.addWidget(label)
            return

        provider = auth.PROVIDERS.get(session.get("provider", ""), None)
        profile = session.get("profile", {})
        row = QHBoxLayout()

        info = QLabel(
            f"<b>{profile.get('name') or profile.get('email') or 'Cuenta conectada'}</b><br>"
            f"{profile.get('email', '')} · vía {provider.label if provider else session.get('provider', '')} · "
            f"conectado el {datetime.fromtimestamp(session.get('connected_at', 0)).strftime('%d/%m/%Y %H:%M')}"
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setStyleSheet("font-size: 12.5px; color: #111827;")
        row.addWidget(info, stretch=1)

        disconnect = QPushButton("Desconectar")
        disconnect.setStyleSheet(theme.BUTTON_DANGER_QSS)
        disconnect.clicked.connect(self._disconnect)
        row.addWidget(disconnect)

        self.session_layout.addLayout(row)

    def _disconnect(self) -> None:
        auth.clear_session()
        self._render_session()

    # ------------------------------------------------------------------

    def _build_provider_section(self, provider_key: str) -> QWidget:
        provider = auth.PROVIDERS[provider_key]
        box = QFrame()
        box.setStyleSheet("QFrame { border: 1px solid #E5E7EB; border-radius: 8px; }")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        title = QLabel(provider.label)
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #111827;")
        header_row.addWidget(title)
        header_row.addStretch(1)

        help_link = QLabel(f'<a href="{provider.help_url}">Crear app / obtener credenciales</a>')
        help_link.setTextFormat(Qt.TextFormat.RichText)
        help_link.setOpenExternalLinks(True)
        help_link.setStyleSheet("font-size: 11px;")
        header_row.addWidget(help_link)
        layout.addLayout(header_row)

        config = auth.load_provider_config().get(provider_key, {})

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addLayout(form)

        fields: dict[str, QLineEdit] = {}

        client_id_field = QLineEdit(config.get("client_id", ""))
        client_id_field.setPlaceholderText("Client ID")
        form.addRow("Client ID:", client_id_field)
        fields["client_id"] = client_id_field

        if provider.requires_secret and provider_key != "apple":
            secret_field = QLineEdit(config.get("client_secret", ""))
            secret_field.setPlaceholderText("Client secret")
            secret_field.setEchoMode(QLineEdit.EchoMode.Password)
            form.addRow("Client secret:", secret_field)
            fields["client_secret"] = secret_field

        if provider_key == "apple":
            layout.addWidget(hint(_APPLE_KEY_HINT))

            team_id_field = QLineEdit(config.get("team_id", ""))
            team_id_field.setPlaceholderText("Team ID")
            form.addRow("Team ID:", team_id_field)
            fields["team_id"] = team_id_field

            key_id_field = QLineEdit(config.get("key_id", ""))
            key_id_field.setPlaceholderText("Key ID")
            form.addRow("Key ID:", key_id_field)
            fields["key_id"] = key_id_field

            key_path_row = QHBoxLayout()
            key_path_field = QLineEdit(config.get("private_key_path", ""))
            key_path_field.setPlaceholderText("Ruta al archivo AuthKey_XXXX.p8")
            key_path_row.addWidget(key_path_field, stretch=1)
            browse_btn = QPushButton("Elegir…")
            browse_btn.clicked.connect(lambda: self._browse_apple_key(key_path_field))
            key_path_row.addWidget(browse_btn)
            form.addRow("Clave privada:", key_path_row)
            fields["private_key_path"] = key_path_field

        self._provider_fields[provider_key] = fields

        connect_row = QHBoxLayout()
        connect_btn = QPushButton(f"Conectar con {provider.label}")
        connect_btn.setStyleSheet(theme.BUTTON_SECONDARY_QSS)
        connect_btn.clicked.connect(lambda: self._connect(provider_key, connect_btn))
        connect_row.addWidget(connect_btn)
        connect_row.addStretch(1)
        layout.addLayout(connect_row)

        return box

    def _browse_apple_key(self, field: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Clave privada de Sign in with Apple", "", "Apple Private Key (*.p8)")
        if path:
            field.setText(path)

    # ------------------------------------------------------------------

    def _save_provider_fields(self, provider_key: str) -> dict:
        fields = self._provider_fields[provider_key]
        values = {name: field.text().strip() for name, field in fields.items()}
        config = auth.load_provider_config()
        config[provider_key] = values
        auth.save_provider_config(config)
        return values

    def _connect(self, provider_key: str, button: QPushButton) -> None:
        values = self._save_provider_fields(provider_key)
        client_id = values.get("client_id", "")
        if not client_id:
            QMessageBox.warning(self, "Falta el Client ID", "Ingresa el Client ID antes de conectar.")
            return

        client_secret = values.get("client_secret", "")
        if provider_key == "apple":
            try:
                private_key_pem = open(values.get("private_key_path", ""), encoding="utf-8").read()
            except OSError as exc:
                QMessageBox.warning(self, "Clave privada no encontrada", f"No se pudo leer el archivo .p8: {exc}")
                return
            try:
                client_secret = auth.generate_apple_client_secret(
                    values.get("team_id", ""), client_id, values.get("key_id", ""), private_key_pem
                )
            except auth.AuthError as exc:
                QMessageBox.warning(self, "Error generando el client secret", str(exc))
                return

        button.setEnabled(False)
        button.setText("Conectando…")
        worker = LoginWorker(provider_key, client_id, client_secret, self)
        worker.finished_login.connect(lambda session: self._on_login_finished(provider_key, button))
        worker.failed.connect(lambda msg: self._on_login_failed(provider_key, button, msg))
        self._workers[provider_key] = worker
        worker.start()

    def _on_login_finished(self, provider_key: str, button: QPushButton) -> None:
        button.setEnabled(True)
        button.setText(f"Conectar con {auth.PROVIDERS[provider_key].label}")
        self._render_session()

    def _on_login_failed(self, provider_key: str, button: QPushButton, message: str) -> None:
        button.setEnabled(True)
        button.setText(f"Conectar con {auth.PROVIDERS[provider_key].label}")
        QMessageBox.critical(self, "No se pudo iniciar sesión", message)
