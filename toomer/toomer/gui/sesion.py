"""Estado compartido de la app: el DataFrame de líneas de pedido cargado."""
from __future__ import annotations

import pandas as pd
from PySide6.QtCore import QObject, Signal


class Sesion(QObject):
    datos_cambiados = Signal()

    def __init__(self):
        super().__init__()
        self.lineas: pd.DataFrame | None = None
        self.origen: str = ""

    def cargar(self, df: pd.DataFrame, origen: str):
        self.lineas = df
        self.origen = origen
        self.datos_cambiados.emit()

    @property
    def hay_datos(self) -> bool:
        return self.lineas is not None and not self.lineas.empty
