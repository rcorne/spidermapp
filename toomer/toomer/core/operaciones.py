from __future__ import annotations

import pandas as pd

from toomer.core import productos, utilidades


def clasificacion_inventario(lineas: pd.DataFrame, dias: int | None = None, detallado: bool = False) -> pd.DataFrame:
    """Clasificación ABC de inventario según contribución acumulada a los ingresos."""
    p = productos.obtener_productos(lineas, dias).sort_values("ingresos", ascending=False)
    p["ingresos_total"] = p["ingresos"].sum()
    p["ingresos_acumulados"] = p["ingresos"].cumsum()
    p["porcentaje_acumulado"] = p["ingresos_acumulados"] / p["ingresos_total"] * 100
    p["clase_abc"] = p["porcentaje_acumulado"].apply(utilidades.clasificar_abc)
    p["rango_abc"] = p["porcentaje_acumulado"].rank().astype(int)
    cols = ["sku", "clase_abc", "rango_abc"]
    if detallado:
        cols += ["ingresos", "ingresos_acumulados", "ingresos_total", "porcentaje_acumulado"]
    return p[cols].round(2)
