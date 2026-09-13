"""Widgets compartidos: tabla de resultados con exportación, ejecución en segundo plano y helpers."""
from __future__ import annotations

import traceback
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QSizePolicy, QTableView, QVBoxLayout, QWidget)

from toomer.gui.table_model import ModeloDataFrame


class Trabajador(QObject):
    """Ejecuta una función en un hilo y avisa con señales (resultado, error, progreso)."""
    terminado = Signal(object)
    fallo = Signal(str)
    progreso = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs

    def correr(self):
        try:
            self.terminado.emit(self.fn(*self.args, **self.kwargs))
        except Exception as e:  # noqa: BLE001
            self.fallo.emit(f"{e}\n\n{traceback.format_exc(limit=3)}")


class Ejecutor(QObject):
    """Gestiona un hilo por widget, para no bloquear la interfaz durante los cálculos."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._hilo = None
        self._trabajador = None

    def ejecutar(self, fn, al_terminar, al_fallar=None, al_progresar=None, *args, **kwargs):
        if self._hilo and self._hilo.isRunning():
            QMessageBox.information(self.parent(), "Toomer", "Ya hay una tarea en curso; espera a que termine.")
            return
        self._hilo = QThread()
        self._trabajador = Trabajador(fn, *args, **kwargs)
        self._trabajador.moveToThread(self._hilo)
        self._hilo.started.connect(self._trabajador.correr)
        self._trabajador.terminado.connect(al_terminar)
        self._trabajador.fallo.connect(al_fallar or self._error_por_defecto)
        if al_progresar:
            self._trabajador.progreso.connect(al_progresar)
        self._trabajador.terminado.connect(self._hilo.quit)
        self._trabajador.fallo.connect(self._hilo.quit)
        self._hilo.start()
        return self._trabajador

    def _error_por_defecto(self, msg: str):
        QMessageBox.critical(self.parent(), "Error", msg)


class TablaResultados(QWidget):
    """Tabla ordenable con filtro de texto, contador de filas y exportación a CSV/XLSX."""

    def __init__(self, titulo: str = "", parent=None):
        super().__init__(parent)
        self.modelo = ModeloDataFrame()
        self._df_completo = pd.DataFrame()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        barra = QHBoxLayout()
        self.etiqueta = QLabel(titulo)
        self.etiqueta.setObjectName("seccion")
        self.contador = QLabel("")
        self.contador.setObjectName("nota")
        self.filtro = QLineEdit()
        self.filtro.setPlaceholderText("Filtrar…")
        self.filtro.setMaximumWidth(220)
        self.filtro.textChanged.connect(self._filtrar)
        self.btn_csv = QPushButton("Exportar CSV")
        self.btn_xlsx = QPushButton("Exportar Excel")
        self.btn_csv.clicked.connect(lambda: self.exportar("csv"))
        self.btn_xlsx.clicked.connect(lambda: self.exportar("xlsx"))
        for w in (self.etiqueta, self.contador):
            barra.addWidget(w)
        barra.addStretch()
        for w in (self.filtro, self.btn_csv, self.btn_xlsx):
            barra.addWidget(w)
        lay.addLayout(barra)
        self.vista = QTableView()
        self.vista.setModel(self.modelo)
        self.vista.setSortingEnabled(True)
        self.vista.setAlternatingRowColors(True)
        self.vista.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.vista.horizontalHeader().setDefaultSectionSize(130)
        self.vista.horizontalHeader().setStretchLastSection(True)
        self.vista.verticalHeader().setDefaultSectionSize(26)
        self.vista.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(self.vista, 1)
        self.set_df(pd.DataFrame())

    def set_df(self, df: pd.DataFrame):
        self._df_completo = df if df is not None else pd.DataFrame()
        self.filtro.clear()
        self._mostrar(self._df_completo)

    def _mostrar(self, df):
        self.modelo.set_df(df)
        self.contador.setText(f"{len(df):,} filas × {len(df.columns)} columnas" if len(df.columns) else "")
        vacio = df.empty
        self.btn_csv.setEnabled(not vacio)
        self.btn_xlsx.setEnabled(not vacio)

    def _filtrar(self, texto: str):
        if not texto:
            self._mostrar(self._df_completo)
            return
        t = texto.lower()
        mask = self._df_completo.astype(str).apply(lambda col: col.str.lower().str.contains(t, regex=False)).any(axis=1)
        self._mostrar(self._df_completo[mask])

    @property
    def df(self) -> pd.DataFrame:
        return self._df_completo

    def exportar(self, formato: str):
        filtro = "CSV (*.csv)" if formato == "csv" else "Excel (*.xlsx)"
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar", str(Path.home() / f"toomer.{formato}"), filtro)
        if not ruta:
            return
        try:
            if formato == "csv":
                self.modelo.df.to_csv(ruta, index=False)
            else:
                self.modelo.df.to_excel(ruta, index=False)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Error al exportar", str(e))


def panel() -> QFrame:
    f = QFrame()
    f.setObjectName("panel")
    return f


def encabezado(titulo: str, subtitulo: str = "") -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    t = QLabel(titulo)
    t.setObjectName("titulo")
    lay.addWidget(t)
    if subtitulo:
        s = QLabel(subtitulo)
        s.setObjectName("subtitulo")
        s.setWordWrap(True)
        lay.addWidget(s)
    return w


def boton_primario(texto: str) -> QPushButton:
    b = QPushButton(texto)
    b.setObjectName("primario")
    b.setCursor(Qt.PointingHandCursor)
    return b


def nota(texto: str) -> QLabel:
    l = QLabel(texto)
    l.setObjectName("nota")
    l.setWordWrap(True)
    return l


def lista_desde_texto(texto: str) -> list[str]:
    return [x.strip() for x in texto.replace("\n", ",").split(",") if x.strip()]
