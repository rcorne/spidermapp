from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd


def conteo_acumulado(df, col_grupo, col_conteo, col_orden):
    df = df.sort_values(by=col_orden, ascending=True)
    return df.groupby([col_grupo])[col_conteo].cumcount()


def valor_anterior(df, col_grupo, col_valor):
    df = df.sort_values(by=[col_valor], ascending=False)
    return df.groupby([col_grupo])[col_valor].shift(-1)


def dias_entre(df, col_antes, col_despues):
    diff = pd.to_datetime(df[col_despues]) - pd.to_datetime(df[col_antes])
    return round(diff / np.timedelta64(1, "D")).fillna(0).astype(int)


def ultimos_dias(df, col_fecha="fecha_pedido", dias=365):
    desde = pd.Timestamp.today() - timedelta(days=dias)
    return df[df[col_fecha] >= desde]


def clasificar_abc(porcentaje: float) -> str:
    if 0 < porcentaje <= 80:
        return "A"
    if 80 < porcentaje <= 90:
        return "B"
    return "C"
