from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

APP_VERSION = "0.2.0"
GITHUB_REPO = "rcorne/spidermapp"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}"
GITHUB_URL = f"https://github.com/{GITHUB_REPO}"


def _asset_path(name: str) -> Path:
    """Works both running from source and frozen inside the PyInstaller
    .app bundle, where files are unpacked under sys._MEIPASS instead of
    living next to this file."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", "."))
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "assets" / name


class GithubInfoWorker(QThread):
    finished_info = Signal(dict)
    failed = Signal(str)

    def run(self) -> None:
        try:
            response = httpx.get(
                GITHUB_API_URL,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "Pidgeot-About-Dialog"},
                timeout=8.0,
            )
        except httpx.RequestError as exc:
            self.failed.emit(f"sin conexión ({exc})")
            return

        if response.status_code == 404:
            # The GitHub REST API returns 404 (not 403) for private repos
            # when the request is unauthenticated — this is not a network
            # problem, it just means nobody without access can see the data.
            self.failed.emit("repositorio privado")
            return
        if response.status_code != 200:
            self.failed.emit(f"GitHub respondió {response.status_code}")
            return

        self.finished_info.emit(response.json())


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Acerca de Pidgeot")
        self.setFixedWidth(420)

        self._worker: GithubInfoWorker | None = None

        outer = QVBoxLayout(self)
        outer.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(14)

        icon_label = QLabel()
        pixmap = QPixmap(str(_asset_path("icon.png")))
        if not pixmap.isNull():
            icon_label.setPixmap(pixmap.scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header.addWidget(icon_label)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        name = QLabel("Pidgeot")
        name.setStyleSheet("font-size: 19px; font-weight: 700; color: #E7E9EE;")
        title_box.addWidget(name)
        version = QLabel(f"Versión {APP_VERSION}")
        version.setStyleSheet("font-size: 12px; color: #9AA1AE;")
        title_box.addWidget(version)
        tagline = QLabel("Auditor de SEO de escritorio")
        tagline.setStyleSheet("font-size: 12px; color: #9AA1AE;")
        title_box.addWidget(tagline)
        header.addLayout(title_box, stretch=1)
        outer.addLayout(header)

        rule1 = QFrame()
        rule1.setFrameShape(QFrame.Shape.HLine)
        rule1.setStyleSheet("color: #2D313B;")
        outer.addWidget(rule1)

        info = QLabel(
            "Licencia: <b>MIT</b><br>"
            "Desarrollado por <b>@rcorne</b><br>"
            f'Repositorio: <a href="{GITHUB_URL}">{GITHUB_URL}</a>'
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setOpenExternalLinks(True)
        info.setStyleSheet("font-size: 12.5px; color: #C3C7D1;")
        outer.addWidget(info)

        rule2 = QFrame()
        rule2.setFrameShape(QFrame.Shape.HLine)
        rule2.setStyleSheet("color: #2D313B;")
        outer.addWidget(rule2)

        github_header = QLabel("Datos de GitHub")
        github_header.setStyleSheet("font-size: 12px; font-weight: 700; color: #C3C7D1;")
        outer.addWidget(github_header)

        self.github_status = QLabel("Consultando GitHub…")
        self.github_status.setWordWrap(True)
        self.github_status.setTextFormat(Qt.TextFormat.RichText)
        self.github_status.setOpenExternalLinks(True)
        self.github_status.setStyleSheet("font-size: 12px; color: #9AA1AE;")
        outer.addWidget(self.github_status)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        outer.addWidget(buttons)

        self._load_github_info()

    def _load_github_info(self) -> None:
        self._worker = GithubInfoWorker(self)
        self._worker.finished_info.connect(self._on_github_info)
        self._worker.failed.connect(self._on_github_failed)
        self._worker.start()

    def _on_github_failed(self, message: str) -> None:
        if "privado" in message:
            explanation = "El repositorio es privado, así que las estadísticas en vivo no están disponibles públicamente."
        elif "sin conexión" in message:
            explanation = "No hay conexión a internet ahora mismo."
        else:
            explanation = f"No se pudo consultar GitHub ({message})."
        self.github_status.setText(f'{explanation} <a href="{GITHUB_URL}">Abrir el repositorio</a>.')

    def _on_github_info(self, data: dict) -> None:
        stars = data.get("stargazers_count", 0)
        forks = data.get("forks_count", 0)
        description = data.get("description") or "Sin descripción."
        license_info = (data.get("license") or {}).get("spdx_id", "MIT")
        default_branch = data.get("default_branch", "main")
        pushed_at = data.get("pushed_at", "")

        updated_text = "—"
        if pushed_at:
            try:
                dt = datetime.strptime(pushed_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                updated_text = dt.astimezone().strftime("%d/%m/%Y %H:%M")
            except ValueError:
                updated_text = pushed_at

        self.github_status.setText(
            f"{description}<br>"
            f"⭐ {stars} &nbsp;·&nbsp; 🍴 {forks} &nbsp;·&nbsp; Licencia en GitHub: {license_info} &nbsp;·&nbsp; Rama: {default_branch}<br>"
            f"Último push: {updated_text}"
        )
