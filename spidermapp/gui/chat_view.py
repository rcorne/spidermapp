from __future__ import annotations

import asyncio
import json
from datetime import datetime

import websockets
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from spidermapp.core import backend_client
from spidermapp.gui import theme

DEFAULT_CHANNEL = "general"


def _ws_url(server_url: str, channel: str, token: str) -> str:
    base = server_url.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")
    return f"{base}/ws/chat/{channel}?token={token}"


class ChatWorker(QThread):
    """Owns the live websocket connection on a dedicated asyncio loop —
    keeps the network I/O off the Qt UI thread the same way CrawlWorker
    keeps crawling off it. History loads once at startup over plain REST;
    everything after that streams in over the socket."""

    connected = Signal()
    disconnected = Signal(str)  # human-readable reason, "" for a clean close
    history_loaded = Signal(list)
    message_received = Signal(dict)

    def __init__(self, server_url: str, token: str, channel: str, parent=None):
        super().__init__(parent)
        self._server_url = server_url
        self._token = token
        self._channel = channel
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ws = None

    def send_message(self, text: str) -> None:
        if self._loop is None or self._ws is None:
            return
        asyncio.run_coroutine_threadsafe(self._send(text), self._loop)

    async def _send(self, text: str) -> None:
        try:
            await self._ws.send(json.dumps({"text": text}))
        except Exception:  # noqa: BLE001 - connection may have just dropped
            pass

    def stop(self) -> None:
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._close(), self._loop)

    async def _close(self) -> None:
        if self._ws is not None:
            await self._ws.close()

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        finally:
            self._loop.close()
            self._loop = None

    async def _main(self) -> None:
        try:
            history = await asyncio.to_thread(
                backend_client.BackendClient(self._server_url).chat_history, self._channel, self._token
            )
            self.history_loaded.emit(history)
        except backend_client.BackendError as exc:
            self.disconnected.emit(str(exc))
            return

        url = _ws_url(self._server_url, self._channel, self._token)
        try:
            async with websockets.connect(url) as ws:
                self._ws = ws
                self.connected.emit()
                async for raw in ws:
                    self.message_received.emit(json.loads(raw))
            self.disconnected.emit("")
        except Exception as exc:  # noqa: BLE001 - surfaced to the user via the status label
            self.disconnected.emit(str(exc))
        finally:
            self._ws = None


class _MessageBubble(QFrame):
    def __init__(self, message: dict, is_own: bool, parent=None):
        super().__init__(parent)
        bg = theme.PRIMARY_SOFT if is_own else theme.BG_ELEVATED
        self.setStyleSheet(f"_MessageBubble {{ background: {bg}; border-radius: 8px; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(1)

        when = datetime.fromtimestamp(message.get("created_at", 0)).strftime("%H:%M")
        header = QLabel(f"<b>{message.get('author_name', '?')}</b> <span style='color:{theme.TEXT_FAINT};font-size:10px;'>{when}</span>")
        header.setTextFormat(Qt.TextFormat.RichText)
        header.setStyleSheet(f"font-size: 11.5px; color: {theme.TEXT_PRIMARY};")
        layout.addWidget(header)

        body = QLabel(message.get("text", ""))
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setStyleSheet(f"font-size: 12.5px; color: {theme.TEXT_SECONDARY};")
        layout.addWidget(body)


class ChatView(QWidget):
    """Rail entry "Chat" — a real-time channel backed by pidge_server.
    Requires an active Pidge session (email/password or OAuth, set up in
    Preferencias → Cuenta); shows a prompt instead of connecting if
    there's none."""

    def __init__(self, channel: str = DEFAULT_CHANNEL, parent=None):
        super().__init__(parent)
        self._channel = channel
        self._worker: ChatWorker | None = None
        self._current_user_id: int | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        header = QWidget()
        header.setStyleSheet(f"background: {theme.BG_ELEVATED}; border-bottom: 1px solid {theme.BORDER};")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 14)
        title = QLabel(f"Chat · #{channel}")
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        header_layout.addWidget(title)
        self.status_label = QLabel("Conectando…")
        self.status_label.setStyleSheet(f"font-size: 11.5px; color: {theme.TEXT_MUTED};")
        header_layout.addWidget(self.status_label)
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, stretch=1)
        self._scroll = scroll

        content = QWidget()
        scroll.setWidget(content)
        self.messages_layout = QVBoxLayout(content)
        self.messages_layout.setContentsMargins(16, 12, 16, 12)
        self.messages_layout.setSpacing(6)
        self.messages_layout.addStretch(1)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(16, 10, 16, 14)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Escribe un mensaje…")
        self.input_field.returnPressed.connect(self._send)
        input_row.addWidget(self.input_field, stretch=1)
        self.send_btn = QPushButton("Enviar")
        self.send_btn.setStyleSheet(theme.BUTTON_PRIMARY_QSS)
        self.send_btn.clicked.connect(self._send)
        input_row.addWidget(self.send_btn)
        outer.addLayout(input_row)

        self._set_input_enabled(False)

    def _set_input_enabled(self, enabled: bool) -> None:
        self.input_field.setEnabled(enabled)
        self.send_btn.setEnabled(enabled)

    def start(self) -> None:
        """Called each time the rail switches to Chat — (re)connects if
        there's a Pidge session and no worker already running."""
        if self._worker is not None and self._worker.isRunning():
            return
        session = backend_client.load_pidge_session()
        self._clear_messages()
        if session is None:
            self.status_label.setText("Sin sesión Pidge. Crea una cuenta o inicia sesión en Preferencias → Cuenta.")
            self._set_input_enabled(False)
            return

        self._current_user_id = session.user.id
        self.status_label.setText("Conectando…")
        self._worker = ChatWorker(session.server_url, session.token, self._channel, self)
        self._worker.connected.connect(self._on_connected)
        self._worker.disconnected.connect(self._on_disconnected)
        self._worker.history_loaded.connect(self._on_history_loaded)
        self._worker.message_received.connect(self._on_message)
        self._worker.start()

    def stop(self) -> None:
        if self._worker is not None:
            self._worker.stop()

    def _on_connected(self) -> None:
        self.status_label.setText("Conectado.")
        self._set_input_enabled(True)

    def _on_disconnected(self, reason: str) -> None:
        self._set_input_enabled(False)
        self.status_label.setText(f"Desconectado: {reason}" if reason else "Desconectado.")

    def _on_history_loaded(self, messages: list) -> None:
        for message in messages:
            self._append_message(message)

    def _on_message(self, message: dict) -> None:
        self._append_message(message)

    def _send(self) -> None:
        text = self.input_field.text().strip()
        if not text or self._worker is None:
            return
        self._worker.send_message(text)
        self.input_field.clear()

    def _clear_messages(self) -> None:
        while self.messages_layout.count() > 1:  # keep the trailing stretch
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _append_message(self, message: dict) -> None:
        is_own = message.get("author_id") == self._current_user_id
        bubble = _MessageBubble(message, is_own)
        bubble.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
