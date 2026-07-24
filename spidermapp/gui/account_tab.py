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

from spidermapp.core import app_settings, auth, backend_client
from spidermapp.gui import theme
from spidermapp.gui.crawl_settings_widgets import hint

_APPLE_KEY_HINT = (
    "Apple exige que el client secret sea un JWT firmado con tu clave privada de "
    "Sign in with Apple (.p8) — no un texto simple como Google/GitHub. "
    "Necesitas una cuenta de Apple Developer paga para generar esta clave."
)


class LoginWorker(QThread):
    """Runs the local OAuth PKCE flow against the provider, then — if a
    Pidge server is reachable — links the resulting profile to a Pidge
    account and mints a session there too, so "Conectar con Google" also
    logs the user into chat/tasks in one step."""

    finished_login = Signal(dict)
    failed = Signal(str)

    def __init__(self, provider_key: str, client_id: str, client_secret: str, server_url: str, parent=None):
        super().__init__(parent)
        self._provider_key = provider_key
        self._client_id = client_id
        self._client_secret = client_secret
        self._server_url = server_url

    def run(self) -> None:
        try:
            session = auth.run_login_flow(self._provider_key, self._client_id, self._client_secret)
        except auth.AuthError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - surfaced to the user via a dialog
            self.failed.emit(str(exc))
            return

        profile = session.get("profile", {})
        if profile.get("email") and profile.get("subject") and self._server_url:
            try:
                client = backend_client.BackendClient(self._server_url)
                pidge_session = client.oauth_link(
                    self._provider_key, profile["subject"], profile["email"], profile.get("name", "")
                )
                backend_client.save_pidge_session(pidge_session)
            except backend_client.BackendError:
                # Provider login still succeeded — chat/tasks just won't
                # have a Pidge session until the server is reachable.
                pass
        self.finished_login.emit(session)


class AuthWorker(QThread):
    """Backend-only email/password signup or login (no OAuth provider
    involved)."""

    finished_auth = Signal(object)
    failed = Signal(str)

    def __init__(self, mode: str, server_url: str, email: str, password: str, display_name: str, parent=None):
        super().__init__(parent)
        self._mode = mode
        self._server_url = server_url
        self._email = email
        self._password = password
        self._display_name = display_name

    def run(self) -> None:
        try:
            client = backend_client.BackendClient(self._server_url)
            if self._mode == "signup":
                session = client.signup(self._email, self._password, self._display_name)
            else:
                session = client.login(self._email, self._password)
            backend_client.save_pidge_session(session)
            self.finished_auth.emit(session)
        except backend_client.BackendError as exc:
            self.failed.emit(str(exc))


class AccountTab(QWidget):
    """Archivo → Preferencias → Cuenta. Inicia sesión vía OAuth 2.0 con
    Google, GitHub o Apple — el flujo estándar para apps de escritorio
    (RFC 8252): abre el navegador del sistema y captura el redirect en un
    servidor local. Spidermapp no puede registrar apps OAuth en tu nombre;
    cada proveedor exige que tú mismo crees una app en su consola con
    http://127.0.0.1:53682/callback como URI de redirección."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: dict[str, LoginWorker] = {}
        self._provider_fields: dict[str, dict[str, QLineEdit]] = {}
        self._auth_worker: AuthWorker | None = None

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

        layout.addWidget(self._build_server_section())
        layout.addWidget(self._build_email_auth_section())

        layout.addWidget(hint(
            "Cada proveedor requiere su propia app OAuth registrada en su consola de desarrolladores, "
            "con http://127.0.0.1:53682/callback como URI de redirección exacta."
        ))

        for provider_key in ("google", "github", "apple"):
            layout.addWidget(self._build_provider_section(provider_key))

        layout.addStretch(1)

    def _server_url(self) -> str:
        return app_settings.load_settings().backend_url

    def _build_server_section(self) -> QWidget:
        box = QFrame()
        box.setStyleSheet("QFrame { border: 1px solid #2D313B; border-radius: 8px; }")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        title = QLabel("Servidor Pidge")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #E7E9EE;")
        layout.addWidget(title)

        form = QFormLayout()
        self.server_field = QLineEdit(self._server_url())
        self.server_field.setPlaceholderText("http://127.0.0.1:8000")
        form.addRow("URL:", self.server_field)
        layout.addLayout(form)

        save_btn = QPushButton("Guardar")
        save_btn.setStyleSheet(theme.BUTTON_SECONDARY_QSS)
        save_btn.clicked.connect(self._save_server_url)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(hint(
            "Aquí vive tu cuenta y el chat — por defecto un servidor local (correr "
            "`uvicorn pidge_server.main:app` en esta Mac). Para usarlo entre varias personas, "
            "cambia esto a la URL del servidor donde lo despliegues."
        ))
        return box

    def _save_server_url(self) -> None:
        settings = app_settings.load_settings()
        settings.backend_url = self.server_field.text().strip() or "http://127.0.0.1:8000"
        app_settings.save_settings(settings)
        QMessageBox.information(self, "Guardado", "URL del servidor actualizada.")

    def _build_email_auth_section(self) -> QWidget:
        box = QFrame()
        box.setStyleSheet("QFrame { border: 1px solid #2D313B; border-radius: 8px; }")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        title = QLabel("Cuenta Pidge (email y contraseña)")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #E7E9EE;")
        layout.addWidget(title)

        form = QFormLayout()
        self.email_field = QLineEdit()
        self.email_field.setPlaceholderText("tu@correo.com")
        form.addRow("Email:", self.email_field)

        self.display_name_field = QLineEdit()
        self.display_name_field.setPlaceholderText("Nombre a mostrar (opcional)")
        form.addRow("Nombre:", self.display_name_field)

        self.password_field = QLineEdit()
        self.password_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_field.setPlaceholderText("Mínimo 8 caracteres")
        form.addRow("Contraseña:", self.password_field)
        layout.addLayout(form)

        buttons_row = QHBoxLayout()
        self.signup_btn = QPushButton("Crear cuenta")
        self.signup_btn.setStyleSheet(theme.BUTTON_PRIMARY_QSS)
        self.signup_btn.clicked.connect(lambda: self._start_email_auth("signup"))
        buttons_row.addWidget(self.signup_btn)

        self.login_btn = QPushButton("Iniciar sesión")
        self.login_btn.setStyleSheet(theme.BUTTON_SECONDARY_QSS)
        self.login_btn.clicked.connect(lambda: self._start_email_auth("login"))
        buttons_row.addWidget(self.login_btn)
        buttons_row.addStretch(1)
        layout.addLayout(buttons_row)

        return box

    def _start_email_auth(self, mode: str) -> None:
        email = self.email_field.text().strip()
        password = self.password_field.text()
        if not email or not password:
            QMessageBox.warning(self, "Faltan datos", "Ingresa email y contraseña.")
            return

        for button in (self.signup_btn, self.login_btn):
            button.setEnabled(False)
        self._auth_worker = AuthWorker(
            mode, self._server_url(), email, password, self.display_name_field.text().strip(), self
        )
        self._auth_worker.finished_auth.connect(self._on_email_auth_finished)
        self._auth_worker.failed.connect(self._on_email_auth_failed)
        self._auth_worker.start()

    def _on_email_auth_finished(self, _session: object) -> None:
        for button in (self.signup_btn, self.login_btn):
            button.setEnabled(True)
        self.password_field.clear()
        self._render_session()

    def _on_email_auth_failed(self, message: str) -> None:
        for button in (self.signup_btn, self.login_btn):
            button.setEnabled(True)
        QMessageBox.critical(self, "No se pudo autenticar", message)

    # ------------------------------------------------------------------

    def _render_session(self) -> None:
        while self.session_layout.count():
            item = self.session_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        pidge_session = backend_client.load_pidge_session()
        if pidge_session:
            pidge_row = QHBoxLayout()
            pidge_info = QLabel(
                f"<b>{pidge_session.user.display_name or pidge_session.user.email}</b> "
                f"({pidge_session.user.email}) · sesión Pidge activa en {pidge_session.server_url}"
            )
            pidge_info.setTextFormat(Qt.TextFormat.RichText)
            pidge_info.setStyleSheet("font-size: 12.5px; color: #E7E9EE;")
            pidge_row.addWidget(pidge_info, stretch=1)
            pidge_disconnect = QPushButton("Cerrar sesión")
            pidge_disconnect.setStyleSheet(theme.BUTTON_DANGER_QSS)
            pidge_disconnect.clicked.connect(self._disconnect_pidge)
            pidge_row.addWidget(pidge_disconnect)
            self.session_layout.addLayout(pidge_row)
        else:
            label = QLabel("Sin sesión Pidge — crea una cuenta, inicia sesión, o conéctate con un proveedor abajo.")
            label.setStyleSheet("font-size: 12.5px; color: #9AA1AE;")
            self.session_layout.addWidget(label)

        session = auth.load_session()
        if not session:
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
        info.setStyleSheet("font-size: 12.5px; color: #E7E9EE;")
        row.addWidget(info, stretch=1)

        disconnect = QPushButton("Desconectar")
        disconnect.setStyleSheet(theme.BUTTON_DANGER_QSS)
        disconnect.clicked.connect(self._disconnect)
        row.addWidget(disconnect)

        self.session_layout.addLayout(row)

    def _disconnect(self) -> None:
        auth.clear_session()
        self._render_session()

    def _disconnect_pidge(self) -> None:
        backend_client.clear_pidge_session()
        self._render_session()

    # ------------------------------------------------------------------

    def _build_provider_section(self, provider_key: str) -> QWidget:
        provider = auth.PROVIDERS[provider_key]
        box = QFrame()
        box.setStyleSheet("QFrame { border: 1px solid #2D313B; border-radius: 8px; }")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        title = QLabel(provider.label)
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #E7E9EE;")
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
        worker = LoginWorker(provider_key, client_id, client_secret, self._server_url(), self)
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
