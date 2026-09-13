"""Páginas de análisis sobre las líneas de pedido: transacciones, productos, operaciones, informes."""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QSpinBox, QTabWidget

from toomer.core import informes, operaciones, productos, transacciones
from toomer.gui.paginas.base import PaginaBase, PaginaHerramienta


class PaginaTransacciones(PaginaHerramienta):
    titulo = "Transacciones"
    subtitulo = "Una fila por pedido: fecha, cliente, SKUs distintos, unidades, ingresos y número de pedido del cliente."
    texto_boton = "Generar transacciones"

    def calcular(self):
        return transacciones.obtener_transacciones(self.sesion.lineas)


def _spin_dias(lay):
    lay.addWidget(QLabel("Solo últimos (días, 0 = todo):"))
    s = QSpinBox()
    s.setRange(0, 3650)
    s.setValue(0)
    lay.addWidget(s)
    return s


class PaginaProductosLista(PaginaHerramienta):
    titulo = "Productos"
    subtitulo = "Métricas por SKU: clientes, pedidos, unidades, ingresos, precio medio, antigüedad y recencia."
    texto_boton = "Calcular productos"

    def construir_parametros(self, lay):
        self.dias = _spin_dias(lay)

    def calcular(self):
        return productos.obtener_productos(self.sesion.lineas, self.dias.value() or None)


class PaginaRecompra(PaginaHerramienta):
    titulo = "Recompra y compra por volumen"
    subtitulo = "Para cada SKU: qué proporción de pedidos son recompras y cuántos se compran en cantidades > 1."
    texto_boton = "Calcular tasas"

    def calcular(self):
        return productos.tasas_de_recompra(self.sesion.lineas)


class PaginaOperaciones(PaginaHerramienta):
    titulo = "Operaciones · Inventario ABC"
    subtitulo = "Clase A: SKUs que suman el 80 % de los ingresos · B: hasta el 90 % · C: el resto."
    texto_boton = "Clasificar inventario"

    def construir_parametros(self, lay):
        self.dias = _spin_dias(lay)
        self.detallado = QCheckBox("Mostrar cálculo detallado")
        lay.addWidget(self.detallado)

    def calcular(self):
        return operaciones.clasificacion_inventario(self.sesion.lineas, self.dias.value() or None, self.detallado.isChecked())


class PaginaInformes(PaginaHerramienta):
    titulo = "Informes"
    subtitulo = "Informes periódicos de transacciones (ingresos, ticket medio…) y de clientes (nuevos vs recurrentes)."
    texto_boton = "Generar informe"

    def construir_parametros(self, lay):
        lay.addWidget(QLabel("Informe:"))
        self.tipo = QComboBox()
        self.tipo.addItems(["Transacciones", "Clientes"])
        lay.addWidget(self.tipo)
        lay.addWidget(QLabel("Frecuencia:"))
        self.frecuencia = QComboBox()
        for k, v in informes.FRECUENCIAS.items():
            self.frecuencia.addItem(v, k)
        self.frecuencia.setCurrentIndex(2)
        lay.addWidget(self.frecuencia)

    def calcular(self):
        f = self.frecuencia.currentData()
        if self.tipo.currentText() == "Clientes":
            return informes.informe_clientes(self.sesion.lineas, f)
        return informes.informe_transacciones(self.sesion.lineas, f)


class PaginaProductos(PaginaBase):
    titulo = "Productos"
    subtitulo = "Análisis por SKU a partir de las líneas de pedido."

    def __init__(self, sesion, parent=None):
        super().__init__(sesion, parent)
        tabs = QTabWidget()
        tabs.addTab(PaginaProductosLista(sesion), "Productos")
        tabs.addTab(PaginaRecompra(sesion), "Recompra y volumen")
        self.lay.addWidget(tabs, 1)
