from __future__ import annotations

from pathlib import Path

import pandas as pd
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QVBoxLayout)

from toomer.core import datos
from toomer.gui.paginas.base import PaginaBase
from toomer.gui.widgets import TablaResultados, boton_primario, nota

ETIQUETAS = {
    "id_pedido": "ID de pedido *", "sku": "SKU / producto *", "cantidad": "Cantidad *", "fecha_pedido": "Fecha del pedido *",
    "precio_unitario": "Precio unitario *", "id_cliente": "ID de cliente *", "descripcion": "Descripción", "pais": "País",
}


class DialogoMapeo(QDialog):
    def __init__(self, columnas: list[str], mapeo: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Asignar columnas")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.addWidget(nota("Indica qué columna de tu archivo corresponde a cada campo estándar. Los marcados con * son obligatorios."))
        form = QFormLayout()
        self.combos = {}
        for clave, etiqueta in ETIQUETAS.items():
            cb = QComboBox()
            cb.addItem("— (ninguna) —", None)
            for c in columnas:
                cb.addItem(str(c), c)
            if mapeo.get(clave):
                cb.setCurrentIndex(cb.findData(mapeo[clave]))
            self.combos[clave] = cb
            form.addRow(etiqueta, cb)
        lay.addLayout(form)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)

    def mapeo(self) -> dict:
        return {k: cb.currentData() for k, cb in self.combos.items()}


class PaginaDatos(PaginaBase):
    titulo = "Datos"
    subtitulo = ("Toomer trabaja sobre líneas de pedido: una fila por producto dentro de cada pedido. "
                 "Carga un CSV o Excel, descarga el dataset de ejemplo Online Retail, o genera datos sintéticos para probar.")

    def __init__(self, sesion, parent=None):
        super().__init__(sesion, parent)
        fila = QHBoxLayout()
        b_abrir = boton_primario("Abrir CSV / Excel…")
        b_abrir.clicked.connect(self.abrir)
        b_ejemplo = QPushButton("Descargar datos de ejemplo (Online Retail)")
        b_ejemplo.clicked.connect(self.descargar_ejemplo)
        b_sint = QPushButton("Generar datos sintéticos")
        b_sint.clicked.connect(self.sinteticos)
        for b in (b_abrir, b_ejemplo, b_sint):
            fila.addWidget(b)
        fila.addStretch()
        self.lay.addLayout(fila)
        self.resumen = QLabel("Sin datos cargados.")
        self.resumen.setObjectName("nota")
        self.resumen.setWordWrap(True)
        self.lay.addWidget(self.resumen)
        self.lay.addWidget(self.estado)
        self.tabla = TablaResultados("Vista previa (primeras 500 filas)")
        self.lay.addWidget(self.tabla, 1)
        sesion.datos_cambiados.connect(self._refrescar)

    def abrir(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir líneas de pedido", str(Path.home()),
                                              "Datos (*.csv *.txt *.xlsx *.xls)")
        if not ruta:
            return
        try:
            crudo = datos.leer_archivo(ruta)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo leer el archivo", str(e))
            return
        dlg = DialogoMapeo(list(crudo.columns), datos.detectar_mapeo(list(crudo.columns)), self)
        if dlg.exec() != QDialog.Accepted:
            return
        self.aviso("Normalizando…")
        self.ejecutor.ejecutar(lambda: datos.normalizar(crudo, dlg.mapeo()),
                               lambda df: self.sesion.cargar(df, Path(ruta).name), self._fallo)

    def descargar_ejemplo(self):
        self.aviso("Descargando ~45 MB desde GitHub… puede tardar un momento.")
        self.ejecutor.ejecutar(datos.descargar_datos_ejemplo,
                               lambda df: self.sesion.cargar(df, "Online Retail (ejemplo)"), self._fallo)

    def sinteticos(self):
        self.sesion.cargar(datos.generar_datos_sinteticos(), "Datos sintéticos")

    def _fallo(self, msg):
        self.aviso("")
        QMessageBox.critical(self, "Error", msg)

    def _refrescar(self):
        df = self.sesion.lineas
        self.aviso("")
        self.tabla.set_df(df.head(500))
        self.resumen.setText(
            f"<b>{self.sesion.origen}</b> · {len(df):,} líneas · {df['id_pedido'].nunique():,} pedidos · "
            f"{df['id_cliente'].nunique():,} clientes · {df['sku'].nunique():,} SKUs · "
            f"del {df['fecha_pedido'].min():%Y-%m-%d} al {df['fecha_pedido'].max():%Y-%m-%d} · "
            f"ingresos {df['precio_linea'].sum():,.2f}")
