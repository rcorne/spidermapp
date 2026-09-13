"""Publicidad (keywords y Spintax), calendario comercial, resumen de texto y calculadora de métricas."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QComboBox, QDateEdit, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget,
                               QVBoxLayout, QWidget)

from toomer.core import marketing, metricas, nlp, publicidad
from toomer.gui.paginas.base import PaginaBase, PaginaHerramienta
from toomer.gui.widgets import TablaResultados, boton_primario, lista_desde_texto, nota, panel


class TabKeywords(PaginaBase):
    titulo = "Keywords para búsqueda de pago"
    subtitulo = "Combina productos con prefijos y sufijos y genera las cuatro concordancias de Google Ads."

    def __init__(self, sesion, parent=None):
        super().__init__(sesion, parent)
        form = QFormLayout()
        self.productos = QPlainTextEdit("cañas de pescar\ncarretes de pesca\nseñuelos")
        self.prefijos = QLineEdit("comprar, mejores, baratos, ofertas de")
        self.sufijos = QLineEdit("online, precio, en oferta, cerca de mí")
        self.campana = QLineEdit("Pesca - Búsqueda")
        self.productos.setMaximumHeight(90)
        form.addRow("Productos (uno por línea o separados por coma):", self.productos)
        form.addRow("Prefijos:", self.prefijos)
        form.addRow("Sufijos:", self.sufijos)
        form.addRow("Nombre de campaña:", self.campana)
        self.lay.addLayout(form)
        b = boton_primario("Generar keywords")
        b.clicked.connect(self.generar)
        self.lay.addWidget(b, 0)
        self.tabla = TablaResultados("Keywords")
        self.lay.addWidget(self.tabla, 1)

    def generar(self):
        df = publicidad.generar_keywords(lista_desde_texto(self.productos.toPlainText()), lista_desde_texto(self.prefijos.text()),
                                         lista_desde_texto(self.sufijos.text()), self.campana.text())
        self.tabla.set_df(df)


class TabSpintax(PaginaBase):
    titulo = "Textos de anuncio con Spintax"
    subtitulo = "Escribe variantes entre llaves separadas por |: «Compra {hoy|ahora} con {envío gratis|20 % de descuento}»."

    def __init__(self, sesion, parent=None):
        super().__init__(sesion, parent)
        self.texto = QPlainTextEdit("Compra {hoy|ahora} las mejores {cañas|cañas de pescar} con {envío gratis|20 % de descuento}.")
        self.texto.setMaximumHeight(100)
        self.lay.addWidget(self.texto)
        b = boton_primario("Generar todas las variantes")
        b.clicked.connect(self.generar)
        self.lay.addWidget(b, 0)
        self.tabla = TablaResultados("Variantes")
        self.lay.addWidget(self.tabla, 1)

    def generar(self):
        giros = publicidad.generar_spintax(self.texto.toPlainText(), unico=False)
        df = pd.DataFrame({"variante": giros})
        df["caracteres"] = df["variante"].str.len()
        self.tabla.set_df(df)


class PaginaPublicidad(PaginaBase):
    titulo = "Publicidad"
    subtitulo = "Generación de keywords y textos para campañas de búsqueda de pago."

    def __init__(self, sesion, parent=None):
        super().__init__(sesion, parent)
        tabs = QTabWidget()
        tabs.addTab(TabKeywords(sesion), "Keywords")
        tabs.addTab(TabSpintax(sesion), "Spintax")
        self.lay.addWidget(tabs, 1)


class PaginaMarketing(PaginaHerramienta):
    titulo = "Marketing · Calendario comercial"
    subtitulo = "Fechas clave del ecommerce (Reyes, San Valentín, Día de la Madre, Black Friday, Cyber Monday, Navidad, días de pago…)."
    texto_boton = "Generar calendario"
    necesita_datos = False

    def construir_parametros(self, lay):
        lay.addWidget(QLabel("Desde:"))
        self.inicio = QDateEdit(QDate.currentDate())
        self.inicio.setCalendarPopup(True)
        self.inicio.setDisplayFormat("yyyy-MM-dd")
        lay.addWidget(self.inicio)
        lay.addWidget(QLabel("Días:"))
        self.dias = QSpinBox()
        self.dias.setRange(7, 1500)
        self.dias.setValue(365)
        lay.addWidget(self.dias)
        self.modo = QComboBox()
        self.modo.addItems(["Solo eventos", "Calendario completo (día a día)"])
        lay.addWidget(self.modo)

    def calcular(self):
        inicio = self.inicio.date().toPython()
        if self.modo.currentIndex() == 0:
            return marketing.eventos_comerciales(inicio, self.dias.value())
        return marketing.calendario_comercial(inicio, self.dias.value())


class PaginaNLP(PaginaBase):
    titulo = "Texto · Resúmenes"
    subtitulo = ("Resumen extractivo: selecciona las frases más representativas del texto. Funciona sin conexión y sin modelos pesados. "
                 "También puedes resumir una columna entera de un CSV.")

    def __init__(self, sesion, parent=None):
        super().__init__(sesion, parent)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Frases en el resumen:"))
        self.n = QSpinBox()
        self.n.setRange(1, 20)
        self.n.setValue(3)
        fila.addWidget(self.n)
        fila.addStretch()
        b = boton_primario("Resumir texto")
        b.clicked.connect(self.resumir)
        fila.addWidget(b)
        b2 = QPushButton("Resumir columna de un CSV…")
        b2.clicked.connect(self.resumir_csv)
        fila.addWidget(b2)
        self.lay.addLayout(fila)
        self.entrada = QPlainTextEdit()
        self.entrada.setPlaceholderText("Pega aquí el texto a resumir…")
        self.lay.addWidget(self.entrada, 1)
        self.salida = QPlainTextEdit()
        self.salida.setReadOnly(True)
        self.salida.setPlaceholderText("Resumen")
        self.lay.addWidget(self.salida, 1)
        self.tabla = TablaResultados("Resúmenes del CSV")
        self.lay.addWidget(self.tabla, 1)

    def resumir(self):
        self.salida.setPlainText(nlp.resumir(self.entrada.toPlainText(), self.n.value()))

    def resumir_csv(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir CSV", str(Path.home()), "CSV (*.csv)")
        if not ruta:
            return
        df = pd.read_csv(ruta, sep=None, engine="python")
        columnas = [c for c in df.columns if df[c].dtype == object]
        if not columnas:
            QMessageBox.information(self, "Toomer", "El CSV no tiene columnas de texto.")
            return
        col, ok = _elegir(self, "Columna de texto", columnas)
        if ok:
            self.tabla.set_df(nlp.resumir_columna(df, col, "resumen", self.n.value()))


def _elegir(parent, titulo, opciones):
    from PySide6.QtWidgets import QInputDialog
    return QInputDialog.getItem(parent, titulo, titulo + ":", opciones, 0, False)


class PaginaMetricas(PaginaBase):
    titulo = "Calculadora de métricas"
    subtitulo = "Las fórmulas de retail, marketing, inventario y atención al cliente de EcommerceTools, listas para usar."

    def __init__(self, sesion, parent=None):
        super().__init__(sesion, parent)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Categoría:"))
        self.categoria = QComboBox()
        self.categoria.addItems(metricas.CATEGORIAS)
        fila.addWidget(self.categoria)
        fila.addWidget(QLabel("Métrica:"))
        self.metrica = QComboBox()
        fila.addWidget(self.metrica, 1)
        self.lay.addLayout(fila)
        self.caja = QGroupBox("Parámetros")
        self.form = QFormLayout(self.caja)
        self.lay.addWidget(self.caja)
        self.descripcion = nota("")
        self.lay.addWidget(self.descripcion)
        self.resultado = QLabel("")
        self.resultado.setObjectName("titulo")
        self.lay.addWidget(self.resultado)
        self.lay.addStretch()
        self.campos = {}
        self.categoria.currentTextChanged.connect(self._llenar_metricas)
        self.metrica.currentIndexChanged.connect(self._construir_form)
        self._llenar_metricas()

    def _llenar_metricas(self):
        self.metrica.blockSignals(True)
        self.metrica.clear()
        for m in metricas.METRICAS:
            if m.categoria == self.categoria.currentText():
                self.metrica.addItem(m.nombre, m.clave)
        self.metrica.blockSignals(False)
        self._construir_form()

    def _construir_form(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        self.campos = {}
        m = self._actual()
        if not m:
            return
        for clave, etiqueta, valor in m.campos:
            s = QDoubleSpinBox()
            s.setRange(-1e12, 1e12)
            s.setDecimals(4)
            s.setValue(valor)
            s.valueChanged.connect(self._calcular)
            self.form.addRow(etiqueta + ":", s)
            self.campos[clave] = s
        self.descripcion.setText(m.descripcion)
        self._calcular()

    def _actual(self):
        clave = self.metrica.currentData()
        return next((m for m in metricas.METRICAS if m.clave == clave), None)

    def _calcular(self):
        m = self._actual()
        if not m:
            return
        try:
            v = metricas.calcular(m, {k: s.value() for k, s in self.campos.items()})
            self.resultado.setText(f"{m.nombre}: {v:,.2f} {m.unidad}".strip())
        except ZeroDivisionError:
            self.resultado.setText("División por cero")
