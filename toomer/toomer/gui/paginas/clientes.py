from __future__ import annotations

import pandas as pd
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox, QLabel, QSpinBox, QTabWidget

from toomer.core import clientes, transacciones
from toomer.gui.paginas.base import PaginaBase, PaginaHerramienta


class TabClientes(PaginaHerramienta):
    titulo = "Clientes"
    subtitulo = "Ingresos, pedidos, SKUs, unidades, ticket medio, antigüedad, recencia y cohorte por cliente."
    texto_boton = "Calcular clientes"

    def calcular(self):
        return clientes.obtener_clientes(self.sesion.lineas)


class TabRFM(PaginaHerramienta):
    titulo = "Segmentación RFM (H)"
    subtitulo = ("Recencia, Frecuencia, Monetario y Heterogeneidad puntuados de 1 a 5 con K-means; "
                 "segmentos: En riesgo, Mantener y mejorar, Potencial leal, Leal, Estrella.")
    texto_boton = "Segmentar"

    def calcular(self):
        return clientes.segmentos_rfm(clientes.obtener_clientes(self.sesion.lineas))


class TabABC(PaginaHerramienta):
    titulo = "Clientes ABC"
    subtitulo = "A = 80 % de los ingresos del período, B = siguiente 10 %, C = resto, D = sin compras en el período."
    texto_boton = "Clasificar"

    def construir_parametros(self, lay):
        lay.addWidget(QLabel("Período (meses):"))
        self.meses = QSpinBox()
        self.meses.setRange(1, 120)
        self.meses.setValue(12)
        lay.addWidget(self.meses)

    def calcular(self):
        return clientes.segmentos_abc(clientes.obtener_clientes(self.sesion.lineas), self.meses.value())


class TabCohortes(PaginaHerramienta):
    titulo = "Cohortes y retención"
    subtitulo = "Matriz de clientes que vuelven a comprar N períodos después de su adquisición."
    texto_boton = "Calcular matriz"

    def construir_parametros(self, lay):
        lay.addWidget(QLabel("Período:"))
        self.periodo = QComboBox()
        for k, v in (("M", "Mes"), ("Q", "Trimestre"), ("Y", "Año")):
            self.periodo.addItem(v, k)
        lay.addWidget(self.periodo)
        self.porcentaje = QCheckBox("En porcentaje")
        self.porcentaje.setChecked(True)
        lay.addWidget(self.porcentaje)
        self.detalle = QCheckBox("Tabla larga (retención por cohorte/período)")
        lay.addWidget(self.detalle)

    def calcular(self):
        if self.detalle.isChecked():
            r = clientes.retencion(self.sesion.lineas, self.periodo.currentData())
            return r.astype({"cohorte_adquisicion": str, "cohorte_pedido": str})
        return clientes.matriz_cohortes(self.sesion.lineas, self.periodo.currentData(), self.porcentaje.isChecked())


class TabLatencia(PaginaHerramienta):
    titulo = "Latencia de compra"
    subtitulo = "Días medios entre pedidos por cliente y si su próximo pedido está pendiente, próximo o atrasado."
    texto_boton = "Calcular latencia"

    def calcular(self):
        return clientes.latencia(transacciones.obtener_transacciones(self.sesion.lineas))


class TabPredicciones(PaginaHerramienta):
    titulo = "Predicciones (BG/NBD + Gamma-Gamma)"
    subtitulo = ("Compras esperadas en los próximos N días, ticket esperado y valor de vida (CLV) por cliente. "
                 "Los modelos se ajustan con SciPy; con pocos clientes recurrentes los resultados son poco fiables.")
    texto_boton = "Predecir"

    def construir_parametros(self, lay):
        lay.addWidget(QLabel("Fin de observación:"))
        self.fin = QDateEdit(QDate.currentDate())
        self.fin.setCalendarPopup(True)
        self.fin.setDisplayFormat("yyyy-MM-dd")
        lay.addWidget(self.fin)
        lay.addWidget(QLabel("Días a predecir:"))
        self.dias = QSpinBox()
        self.dias.setRange(1, 3650)
        self.dias.setValue(90)
        lay.addWidget(self.dias)
        lay.addWidget(QLabel("Meses CLV:"))
        self.meses = QSpinBox()
        self.meses.setRange(1, 120)
        self.meses.setValue(12)
        lay.addWidget(self.meses)
        lay.addWidget(QLabel("Tasa de descuento mensual:"))
        self.descuento = QDoubleSpinBox()
        self.descuento.setRange(0, 1)
        self.descuento.setSingleStep(0.01)
        self.descuento.setValue(0.01)
        lay.addWidget(self.descuento)

    def calcular(self):
        fin = pd.Timestamp(self.fin.date().toPython())
        t = transacciones.obtener_transacciones(self.sesion.lineas)
        return clientes.predicciones_clientes(t, fin, self.dias.value(), self.meses.value(), self.descuento.value())


class PaginaClientes(PaginaBase):
    titulo = "Clientes"
    subtitulo = "Segmentación, cohortes, latencia y predicciones de valor de vida."

    def __init__(self, sesion, parent=None):
        super().__init__(sesion, parent)
        tabs = QTabWidget()
        for cls, nombre in ((TabClientes, "Clientes"), (TabRFM, "RFM"), (TabABC, "ABC"), (TabCohortes, "Cohortes"),
                            (TabLatencia, "Latencia"), (TabPredicciones, "Predicciones")):
            tabs.addTab(cls(sesion), nombre)
        self.lay.addWidget(tabs, 1)
