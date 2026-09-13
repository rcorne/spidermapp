from __future__ import annotations

from pathlib import Path

import pandas as pd
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QSpinBox, QTabWidget)

from toomer.core import seo
from toomer.gui.paginas.base import PaginaBase, PaginaHerramienta
from toomer.gui.widgets import lista_desde_texto, nota


class _Herramienta(PaginaHerramienta):
    necesita_datos = False


class TabRobots(_Herramienta):
    titulo = "robots.txt y sitemaps"
    subtitulo = "Lee el robots.txt de un sitio y descubre sus sitemaps, o vuelca un sitemap XML (índices incluidos) a una tabla."
    texto_boton = "Consultar"

    def construir_parametros(self, lay):
        self.modo = QComboBox()
        self.modo.addItems(["Directivas de robots.txt", "Sitemaps declarados en robots.txt", "URLs de un sitemap XML"])
        lay.addWidget(self.modo)
        self.url = QLineEdit("https://www.ejemplo.com/robots.txt")
        self.url.setMinimumWidth(360)
        lay.addWidget(self.url, 1)

    def calcular(self):
        u = self.url.text().strip()
        m = self.modo.currentIndex()
        if m == 0:
            return seo.leer_robots(u)
        if m == 1:
            return pd.DataFrame({"sitemap": seo.sitemaps_en_robots(u)})
        return seo.leer_sitemap(u)


class TabAutocompletar(_Herramienta):
    titulo = "Sugerencias de Google Autocomplete"
    subtitulo = "Ideas de keywords a partir del autocompletado de Google, con expansión por prefijos (cómo, qué, mejor…) y sufijos (a–z, precio…)."
    texto_boton = "Buscar sugerencias"

    def construir_parametros(self, lay):
        self.consulta = QLineEdit("zapatillas running")
        self.consulta.setMinimumWidth(260)
        lay.addWidget(self.consulta, 1)
        lay.addWidget(QLabel("Idioma:"))
        self.idioma = QLineEdit("es")
        self.idioma.setMaximumWidth(50)
        lay.addWidget(self.idioma)
        self.expandir = QCheckBox("Expandir con prefijos y sufijos")
        self.expandir.setChecked(True)
        lay.addWidget(self.expandir)

    def calcular(self):
        return seo.autocompletar(self.consulta.text().strip(), self.expandir.isChecked(), self.idioma.text().strip() or "es")


class _ConListaURLs(_Herramienta):
    def _caja_urls(self, lay, ejemplo):
        self.urls = QPlainTextEdit(ejemplo)
        self.urls.setMaximumHeight(90)
        self.lay.insertWidget(1, self.urls)
        b = QPushButton("Cargar URLs desde sitemap…")
        b.clicked.connect(self._desde_sitemap)
        lay.addWidget(b)

    def _desde_sitemap(self):
        from PySide6.QtWidgets import QInputDialog
        u, ok = QInputDialog.getText(self, "Sitemap", "URL del sitemap XML:")
        if ok and u.strip():
            self.aviso("Leyendo sitemap…")
            self.ejecutor.ejecutar(lambda: seo.leer_sitemap(u.strip()),
                                   lambda df: (self.urls.setPlainText("\n".join(df["loc"].tolist())), self.aviso(f"{len(df)} URLs cargadas.")))

    def lista(self):
        return lista_desde_texto(self.urls.toPlainText())


class TabPaginas(_ConListaURLs):
    titulo = "Análisis de páginas"
    subtitulo = "Título, meta descripción, canonical, robots, hreflang, H1, enlaces y palabras de cada URL."
    texto_boton = "Analizar"

    def construir_parametros(self, lay):
        self._caja_urls(lay, "https://www.ejemplo.com/\nhttps://www.ejemplo.com/productos")

    def calcular(self):
        return seo.analizar_sitio(self.lista())


class TabPageSpeed(_ConListaURLs):
    titulo = "Core Web Vitals (PageSpeed Insights)"
    subtitulo = "Necesita una API key de Google (PageSpeed Insights API, gratuita) desde Google Cloud Console."
    texto_boton = "Medir"

    def construir_parametros(self, lay):
        self._caja_urls(lay, "https://www.ejemplo.com/")
        lay.addWidget(QLabel("API key:"))
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setMinimumWidth(220)
        lay.addWidget(self.key)
        self.estrategia = QComboBox()
        self.estrategia.addItems(["mobile", "desktop"])
        lay.addWidget(self.estrategia)

    def calcular(self):
        return seo.core_web_vitals(self.key.text().strip(), self.lista(), self.estrategia.currentText())


class TabKnowledgeGraph(_Herramienta):
    titulo = "Google Knowledge Graph"
    subtitulo = "Entidades del Knowledge Graph para una consulta. Necesita API key (Knowledge Graph Search API)."
    texto_boton = "Buscar entidades"

    def construir_parametros(self, lay):
        self.consulta = QLineEdit("Nike")
        lay.addWidget(self.consulta, 1)
        lay.addWidget(QLabel("API key:"))
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        lay.addWidget(self.key)
        lay.addWidget(QLabel("Límite:"))
        self.limite = QSpinBox()
        self.limite.setRange(1, 50)
        self.limite.setValue(10)
        lay.addWidget(self.limite)

    def calcular(self):
        return seo.knowledge_graph(self.key.text().strip(), self.consulta.text().strip(), self.limite.value())


class TabGoogle(_Herramienta):
    titulo = "Google: páginas indexadas y SERPs"
    subtitulo = ("Extrae resultados directamente del HTML de Google. Es frágil: Google cambia su HTML y puede bloquear "
                 "las peticiones automáticas (captcha). Úsalo con moderación.")
    texto_boton = "Consultar Google"

    def construir_parametros(self, lay):
        self.modo = QComboBox()
        self.modo.addItems(["Páginas indexadas (site:)", "Resultados orgánicos (SERP)"])
        lay.addWidget(self.modo)
        self.consulta = QLineEdit("ejemplo.com")
        self.consulta.setMinimumWidth(260)
        lay.addWidget(self.consulta, 1)
        lay.addWidget(QLabel("Páginas:"))
        self.paginas = QSpinBox()
        self.paginas.setRange(1, 5)
        lay.addWidget(self.paginas)
        lay.addWidget(QLabel("Dominio:"))
        self.dominio = QLineEdit("google.com")
        self.dominio.setMaximumWidth(120)
        lay.addWidget(self.dominio)

    def calcular(self):
        if self.modo.currentIndex() == 0:
            return seo.paginas_indexadas(lista_desde_texto(self.consulta.text()), self.dominio.text().strip())
        return seo.serps(self.consulta.text().strip(), self.paginas.value(), self.dominio.text().strip())


class TabSearchConsole(_Herramienta):
    titulo = "Google Search Console"
    subtitulo = ("Consulta la API con una cuenta de servicio (archivo JSON) que tenga acceso a la propiedad. "
                 "Puedes traer datos por dimensión, comparar dos períodos o clasificar páginas en ABCD por clics.")
    texto_boton = "Consultar"

    def construir_parametros(self, lay):
        self.modo = QComboBox()
        self.modo.addItems(["Datos por dimensión", "Comparar con el período anterior", "Clasificación ABCD de páginas", "Resumen ABCD"])
        lay.addWidget(self.modo)
        self.sitio = QLineEdit("https://www.ejemplo.com/")
        self.sitio.setMinimumWidth(200)
        lay.addWidget(self.sitio, 1)
        self.dimension = QComboBox()
        self.dimension.addItems(["page", "query", "date", "device", "country", "page,query"])
        lay.addWidget(self.dimension)
        lay.addWidget(QLabel("Desde:"))
        self.desde = QDateEdit(QDate.currentDate().addDays(-28))
        self.desde.setCalendarPopup(True)
        self.desde.setDisplayFormat("yyyy-MM-dd")
        lay.addWidget(self.desde)
        lay.addWidget(QLabel("Hasta:"))
        self.hasta = QDateEdit(QDate.currentDate().addDays(-1))
        self.hasta.setCalendarPopup(True)
        self.hasta.setDisplayFormat("yyyy-MM-dd")
        lay.addWidget(self.hasta)
        self.todo = QCheckBox("Todas las filas")
        lay.addWidget(self.todo)
        fila = QHBoxLayout()
        self.ruta_clave = QLineEdit()
        self.ruta_clave.setPlaceholderText("Archivo JSON de la cuenta de servicio…")
        b = QPushButton("Elegir…")
        b.clicked.connect(self._elegir_clave)
        fila.addWidget(self.ruta_clave, 1)
        fila.addWidget(b)
        self.lay.insertLayout(1, fila)

    def _elegir_clave(self):
        r, _ = QFileDialog.getOpenFileName(self, "Clave de cuenta de servicio", str(Path.home()), "JSON (*.json)")
        if r:
            self.ruta_clave.setText(r)

    def calcular(self):
        clave, sitio = self.ruta_clave.text().strip(), self.sitio.text().strip()
        d1, d2 = self.desde.date().toPython(), self.hasta.date().toPython()
        dims = self.dimension.currentText().split(",")
        carga = {"startDate": str(d1), "endDate": str(d2), "dimensions": dims}
        m = self.modo.currentIndex()
        if m == 0:
            return seo.consultar_gsc(clave, sitio, carga, self.todo.isChecked())
        if m == 1:
            n = (d2 - d1).days + 1
            antes = {"startDate": str(d1 - pd.Timedelta(days=n)), "endDate": str(d1 - pd.Timedelta(days=1)), "dimensions": dims}
            return seo.comparar_gsc(clave, sitio, antes, carga, self.todo.isChecked())
        carga["dimensions"] = ["page"]
        clases = seo.clasificar_abcd(seo.consultar_gsc(clave, sitio, carga, True))
        return clases if m == 2 else seo.resumen_abcd(clases)


class PaginaSEO(PaginaBase):
    titulo = "SEO"
    subtitulo = "Herramientas de SEO técnico: rastreo de metadatos, sitemaps, keywords, rendimiento y Search Console."

    def __init__(self, sesion, parent=None):
        super().__init__(sesion, parent)
        tabs = QTabWidget()
        for cls, nombre in ((TabRobots, "robots / sitemaps"), (TabPaginas, "Páginas"), (TabAutocompletar, "Autocompletar"),
                            (TabPageSpeed, "Core Web Vitals"), (TabKnowledgeGraph, "Knowledge Graph"),
                            (TabGoogle, "Google"), (TabSearchConsole, "Search Console")):
            tabs.addTab(cls(sesion), nombre)
        self.lay.addWidget(tabs, 1)
