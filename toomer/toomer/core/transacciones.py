from __future__ import annotations

import numpy as np
import pandas as pd

from toomer.core import utilidades


def obtener_transacciones(lineas: pd.DataFrame) -> pd.DataFrame:
    """Agrega las líneas de pedido en una fila por pedido."""
    lineas = lineas.sort_values(by=["fecha_pedido"])
    tx = lineas.groupby("id_pedido").agg(
        fecha_pedido=("fecha_pedido", "max"),
        id_cliente=("id_cliente", "max"),
        skus=("sku", "nunique"),
        unidades=("cantidad", "sum"),
        ingresos=("precio_linea", "sum"),
    ).reset_index()
    tx["devolucion"] = np.where(tx["ingresos"] > 0, 0, 1)
    tx["numero_pedido"] = utilidades.conteo_acumulado(tx, "id_cliente", "id_pedido", "fecha_pedido") + 1
    return tx
