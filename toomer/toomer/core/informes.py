from __future__ import annotations

import numpy as np
import pandas as pd

from toomer.core.transacciones import obtener_transacciones

FRECUENCIAS = {"Y": "Año", "Q": "Trimestre", "M": "Mes", "W": "Semana", "D": "Día"}


def _periodo(fecha: pd.Series, frecuencia: str) -> pd.Series:
    if frecuencia == "Y":
        return fecha.dt.year.astype(str)
    if frecuencia == "Q":
        return fecha.dt.year.astype(str) + "-T" + fecha.dt.quarter.astype(str)
    if frecuencia == "W":
        return fecha.dt.strftime("%Y-S%W")
    if frecuencia == "D":
        return fecha.dt.strftime("%Y-%m-%d")
    return fecha.dt.strftime("%Y-%m")


def informe_transacciones(lineas: pd.DataFrame, frecuencia: str = "M") -> pd.DataFrame:
    df = lineas.assign(periodo=_periodo(lineas["fecha_pedido"], frecuencia))
    a = df.groupby("periodo").agg(
        clientes=("id_cliente", "nunique"), pedidos=("id_pedido", "nunique"), ingresos=("precio_linea", "sum"),
        lineas=("sku", "count"), unidades=("cantidad", "sum")).reset_index()
    a["ticket_medio"] = (a["ingresos"] / a["pedidos"]).round(2)
    a["skus_por_pedido"] = (a["lineas"] / a["pedidos"]).round(2)
    a["unidades_por_pedido"] = (a["unidades"] / a["pedidos"]).round(2)
    a["ingresos_por_cliente"] = (a["ingresos"] / a["clientes"]).round(2)
    return a.round(2)


def informe_clientes(lineas: pd.DataFrame, frecuencia: str = "M") -> pd.DataFrame:
    t = obtener_transacciones(lineas)
    t["periodo"] = _periodo(t["fecha_pedido"], frecuencia)
    t["nuevos"] = np.where(t["numero_pedido"] == 1, 1, 0)
    a = t.groupby("periodo").agg(pedidos=("id_pedido", "nunique"), clientes=("id_cliente", "nunique"),
                                 clientes_nuevos=("nuevos", "sum")).reset_index()
    a["clientes_recurrentes"] = a["clientes"] - a["clientes_nuevos"]
    a["tasa_adquisicion"] = (a["clientes_nuevos"] / a["clientes"] * 100).round(2)
    return a
