from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QVBoxLayout, QWidget

from toomer.gui.sesion import Sesion
from toomer.gui.widgets import Ejecutor, TablaResultados, boton_primario, encabezado


class PaginaBase(QWidget):
    titulo = ""
    subtitulo = ""

    def __init__(self, sesion: Sesion, parent=None):
        super().__init__(parent)
        self.sesion = sesion
        self.ejecutor = Ejecutor(self)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(24, 20, 24, 20)
        self.lay.setSpacing(12)
        self.lay.addWidget(encabezado(self.titulo, self.subtitulo))
        self.estado = QLabel("")
        self.estado.setObjectName("nota")

    def requiere_datos(self) -> bool:
        if not self.sesion.hay_datos:
            QMessageBox.information(self, "Toomer", "Primero carga líneas de pedido en la sección «Datos».")
            return False
        return True

    def aviso(self, texto: str):
        self.estado.setText(texto)


class PaginaHerramienta(PaginaBase):
    """Página con una fila de parámetros, un botón «Calcular» y una tabla de resultados."""
    texto_boton = "Calcular"
    necesita_datos = True

    def __init__(self, sesion, parent=None):
        super().__init__(sesion, parent)
        self.parametros = QHBoxLayout()
        self.construir_parametros(self.parametros)
        self.parametros.addStretch()
        self.boton = boton_primario(self.texto_boton)
        self.boton.clicked.connect(self.lanzar)
        self.parametros.addWidget(self.boton)
        self.lay.addLayout(self.parametros)
        self.lay.addWidget(self.estado)
        self.tabla = TablaResultados("Resultados")
        self.lay.addWidget(self.tabla, 1)

    def construir_parametros(self, lay: QHBoxLayout):  # pragma: no cover - lo implementan las subclases
        pass

    def calcular(self):  # pragma: no cover
        raise NotImplementedError

    def lanzar(self):
        if self.necesita_datos and not self.requiere_datos():
            return
        self.boton.setEnabled(False)
        self.aviso("Calculando…")
        self.ejecutor.ejecutar(self.calcular, self._listo, self._fallo)

    def _listo(self, df):
        self.boton.setEnabled(True)
        self.tabla.set_df(df)
        self.aviso(f"Listo: {len(df):,} filas.")

    def _fallo(self, msg):
        self.boton.setEnabled(True)
        self.aviso("Error: " + msg.splitlines()[0])
        QMessageBox.critical(self, "Error", msg)
