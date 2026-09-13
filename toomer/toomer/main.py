from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from toomer.gui.main_window import VentanaPrincipal
from toomer.gui.theme import HOJA_ESTILO


def _icono() -> QIcon | None:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    for ruta in (base / "toomer" / "assets" / "toomer.png", base / "assets" / "toomer.png"):
        if ruta.exists():
            return QIcon(str(ruta))
    return None


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Toomer")
    app.setOrganizationName("Toomer")
    app.setStyleSheet(HOJA_ESTILO)
    icono = _icono()
    if icono:
        app.setWindowIcon(icono)
    ventana = VentanaPrincipal(icono)
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
