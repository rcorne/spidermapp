from __future__ import annotations

import pandas as pd

from toomer.core import utilidades


def obtener_productos(lineas: pd.DataFrame, dias: int | None = None) -> pd.DataFrame:
    if dias:
        lineas = utilidades.ultimos_dias(lineas, "fecha_pedido", dias)
    p = lineas.groupby("sku").agg(
        primera_venta=("fecha_pedido", "min"),
        ultima_venta=("fecha_pedido", "max"),
        clientes=("id_cliente", "nunique"),
        pedidos=("id_pedido", "nunique"),
        unidades=("cantidad", "sum"),
        ingresos=("precio_linea", "sum"),
        precio_unitario_medio=("precio_unitario", "mean"),
        cantidad_media=("cantidad", "mean"),
        ingreso_medio=("precio_linea", "mean"),
    ).reset_index()
    p["pedidos_por_cliente"] = (p["pedidos"] / p["clientes"]).round(2)
    hoy = pd.Timestamp.today()
    p["antiguedad_dias"] = (hoy - p["primera_venta"]).dt.days
    p["recencia_dias"] = (hoy - p["ultima_venta"]).dt.days
    return p


ETIQUETAS_RECOMPRA = ["Recompra muy baja", "Recompra baja", "Recompra moderada", "Recompra alta", "Recompra muy alta"]
ETIQUETAS_VOLUMEN = ["Volumen muy bajo", "Volumen bajo", "Volumen moderado", "Volumen alto", "Volumen muy alto"]


def tasas_de_recompra(lineas: pd.DataFrame) -> pd.DataFrame:
    """Tasa de recompra y de compra por volumen para cada SKU."""
    df = lineas.copy()
    df["veces_comprado"] = df.groupby(["sku", "id_cliente"])["id_pedido"].transform("count")
    df["comprado_individualmente"] = df[df["cantidad"] == 1].groupby("sku")["id_pedido"].transform("count")
    df["comprado_una_vez"] = df[df["veces_comprado"] == 1].groupby("sku")["id_pedido"].transform("count")
    df[["comprado_individualmente", "comprado_una_vez"]] = df[["comprado_individualmente", "comprado_una_vez"]].fillna(0)

    skus = df.groupby("sku").agg(
        ingresos=("precio_linea", "sum"),
        unidades=("cantidad", "sum"),
        pedidos=("id_pedido", "nunique"),
        clientes=("id_cliente", "nunique"),
        precio_unitario_medio=("precio_unitario", "mean"),
        precio_linea_medio=("precio_linea", "mean"),
    )
    skus["unidades_por_pedido"] = skus["unidades"] / skus["pedidos"]
    skus["unidades_por_cliente"] = skus["unidades"] / skus["clientes"]

    sub = df.groupby("sku")[["comprado_individualmente", "comprado_una_vez"]].max()
    skus = skus.join(sub).reset_index()
    skus["compras_volumen"] = skus["pedidos"] - skus["comprado_individualmente"]
    skus["tasa_volumen"] = skus["compras_volumen"] / skus["pedidos"]
    skus["recompras"] = skus["pedidos"] - skus["comprado_una_vez"]
    skus["tasa_recompra"] = skus["recompras"] / skus["pedidos"]
    skus["etiqueta_recompra"] = pd.cut(skus["tasa_recompra"], bins=5, labels=ETIQUETAS_RECOMPRA).astype(str)
    skus["etiqueta_volumen"] = pd.cut(skus["tasa_volumen"], bins=5, labels=ETIQUETAS_VOLUMEN).astype(str)
    skus["etiqueta_combinada"] = skus["etiqueta_recompra"] + " · " + skus["etiqueta_volumen"]
    return skus
