from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from toomer import __version__
from toomer.gui.paginas.analisis import PaginaInformes, PaginaOperaciones, PaginaProductos, PaginaTransacciones
from toomer.gui.paginas.clientes import PaginaClientes
from toomer.gui.paginas.datos import PaginaDatos
from toomer.gui.paginas.marketing import PaginaMarketing, PaginaMetricas, PaginaNLP, PaginaPublicidad
from toomer.gui.paginas.seo import PaginaSEO
from toomer.gui.sesion import Sesion

SECCIONES = [
    ("Datos", PaginaDatos), ("Transacciones", PaginaTransacciones), ("Productos", PaginaProductos),
    ("Clientes", PaginaClientes), ("Operaciones", PaginaOperaciones), ("Informes", PaginaInformes),
    ("Publicidad", PaginaPublicidad), ("Marketing", PaginaMarketing), ("SEO", PaginaSEO),
    ("Texto", PaginaNLP), ("Métricas", PaginaMetricas),
]


class VentanaPrincipal(QMainWindow):
    def __init__(self, icono: QIcon | None = None):
        super().__init__()
        self.setWindowTitle("Toomer")
        if icono:
            self.setWindowIcon(icono)
        self.resize(1280, 820)
        self.sesion = Sesion()

        raiz = QWidget()
        lay = QHBoxLayout(raiz)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        rail = QWidget()
        rail.setFixedWidth(200)
        rl = QVBoxLayout(rail)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        marca = QLabel("Toomer")
        marca.setObjectName("marca")
        sub = QLabel("ecommerce · marketing · SEO")
        sub.setObjectName("marca_sub")
        self.lista = QListWidget()
        self.lista.setObjectName("rail")
        self.lista.setFocusPolicy(Qt.NoFocus)
        rl.addWidget(marca)
        rl.addWidget(sub)
        rl.addWidget(self.lista, 1)
        lay.addWidget(rail)

        self.pila = QStackedWidget()
        for nombre, cls in SECCIONES:
            self.lista.addItem(nombre)
            self.pila.addWidget(cls(self.sesion))
        self.lista.currentRowChanged.connect(self.pila.setCurrentIndex)
        self.lista.setCurrentRow(0)
        lay.addWidget(self.pila, 1)
        self.setCentralWidget(raiz)

        self.statusBar().showMessage("Sin datos cargados")
        self.sesion.datos_cambiados.connect(self._estado)
        self._menu()

    def _estado(self):
        df = self.sesion.lineas
        self.statusBar().showMessage(f"{self.sesion.origen} · {len(df):,} líneas · {df['id_cliente'].nunique():,} clientes")

    def _menu(self):
        m = self.menuBar().addMenu("Archivo")
        a = QAction("Abrir datos…", self)
        a.setShortcut("Ctrl+O")
        a.triggered.connect(lambda: (self.lista.setCurrentRow(0), self.pila.widget(0).abrir()))
        m.addAction(a)
        m.addSeparator()
        s = QAction("Salir", self)
        s.setShortcut("Ctrl+Q")
        s.triggered.connect(self.close)
        m.addAction(s)
        h = self.menuBar().addMenu("Ayuda")
        ac = QAction("Acerca de Toomer", self)
        ac.triggered.connect(self._acerca)
        h.addAction(ac)

    def _acerca(self):
        QMessageBox.about(self, "Acerca de Toomer",
                          f"<b>Toomer {__version__}</b><br>Caja de herramientas de análisis para ecommerce, marketing y SEO.<br><br>"
                          "Adaptación de escritorio en español de <i>EcommerceTools</i> de Matt Clarke "
                          "(practical-data-science/ecommercetools, licencia MIT).")
