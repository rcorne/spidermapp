"""Carga y normalización de líneas de pedido.

Todas las funciones de Toomer trabajan sobre un DataFrame de *líneas de pedido*
con estas columnas estándar:

    id_pedido, sku, descripcion, cantidad, fecha_pedido, precio_unitario,
    id_cliente, pais, precio_linea
"""
from __future__ import annotations

import io
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNAS_REQUERIDAS = ["id_pedido", "sku", "cantidad", "fecha_pedido", "precio_unitario", "id_cliente"]
COLUMNAS_OPCIONALES = ["descripcion", "pais"]

# Nombres habituales (en inglés y español) para detectar el mapeo automáticamente.
ALIAS = {
    "id_pedido": ["order_id", "invoiceno", "invoice", "pedido", "orden", "order", "id_pedido", "invoice_no"],
    "sku": ["sku", "stockcode", "stock_code", "product_id", "producto", "codigo", "variantid"],
    "descripcion": ["description", "descripcion", "nombre", "product_name", "name"],
    "cantidad": ["quantity", "cantidad", "qty", "units", "unidades"],
    "fecha_pedido": ["order_date", "invoicedate", "invoice_date", "fecha", "fecha_pedido", "date", "created_at"],
    "precio_unitario": ["unit_price", "unitprice", "precio_unitario", "precio", "price"],
    "id_cliente": ["customer_id", "customerid", "cliente", "id_cliente", "customer"],
    "pais": ["country", "pais", "país"],
}


def detectar_mapeo(columnas: list[str]) -> dict[str, str | None]:
    """Devuelve {columna_estandar: columna_del_archivo} adivinando por nombre."""
    normalizadas = {c.strip().lower().replace(" ", "_"): c for c in columnas}
    mapeo: dict[str, str | None] = {}
    for estandar, alias in ALIAS.items():
        mapeo[estandar] = None
        for a in alias:
            if a in normalizadas:
                mapeo[estandar] = normalizadas[a]
                break
    return mapeo


def leer_archivo(ruta: str | Path) -> pd.DataFrame:
    ruta = Path(ruta)
    if ruta.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(ruta)
    # CSV: detecta separador (coma / punto y coma / tab).
    return pd.read_csv(ruta, sep=None, engine="python", encoding_errors="replace")


def normalizar(df: pd.DataFrame, mapeo: dict[str, str | None]) -> pd.DataFrame:
    """Renombra columnas al estándar, tipa los datos y calcula precio_linea."""
    faltan = [c for c in COLUMNAS_REQUERIDAS if not mapeo.get(c)]
    if faltan:
        raise ValueError("Faltan columnas obligatorias: " + ", ".join(faltan))
    renombre = {origen: destino for destino, origen in mapeo.items() if origen}
    out = df.rename(columns=renombre).copy()
    for c in COLUMNAS_OPCIONALES:
        if c not in out.columns:
            out[c] = ""
    out = out[COLUMNAS_REQUERIDAS + COLUMNAS_OPCIONALES]
    out["fecha_pedido"] = pd.to_datetime(out["fecha_pedido"], errors="coerce")
    out["cantidad"] = pd.to_numeric(out["cantidad"], errors="coerce")
    out["precio_unitario"] = pd.to_numeric(out["precio_unitario"], errors="coerce")
    out = out.dropna(subset=["fecha_pedido", "cantidad", "precio_unitario", "id_cliente"])
    out["id_pedido"] = out["id_pedido"].astype(str)
    out["sku"] = out["sku"].astype(str)
    out["id_cliente"] = out["id_cliente"].astype(str).str.replace(r"\.0$", "", regex=True)
    out["precio_linea"] = (out["cantidad"] * out["precio_unitario"]).round(2)
    return out.reset_index(drop=True)


def cargar_lineas_pedido(ruta: str | Path, mapeo: dict[str, str | None] | None = None) -> pd.DataFrame:
    df = leer_archivo(ruta)
    return normalizar(df, mapeo or detectar_mapeo(list(df.columns)))


URL_DATOS_EJEMPLO = (
    "https://raw.githubusercontent.com/databricks/Spark-The-Definitive-Guide/master/data"
    "/retail-data/all/online-retail-dataset.csv"
)


def descargar_datos_ejemplo(timeout: int = 60) -> pd.DataFrame:
    """Descarga el dataset público *Online Retail* (UCI) usado por EcommerceTools."""
    import httpx

    r = httpx.get(URL_DATOS_EJEMPLO, timeout=timeout, follow_redirects=True)
    r.raise_for_status()
    df = pd.read_csv(
        io.StringIO(r.text), skiprows=1,
        names=["id_pedido", "sku", "descripcion", "cantidad", "fecha_pedido", "precio_unitario", "id_cliente", "pais"],
    )
    mapeo = {c: c for c in df.columns}
    return normalizar(df, mapeo)


def generar_datos_sinteticos(clientes: int = 400, dias: int = 540, semilla: int = 7) -> pd.DataFrame:
    """Genera líneas de pedido sintéticas (sin conexión) para probar la app."""
    rng = np.random.default_rng(semilla)
    skus = [f"SKU-{i:03d}" for i in range(1, 61)]
    precios = dict(zip(skus, np.round(rng.gamma(2.0, 9.0, len(skus)) + 1, 2)))
    fin = pd.Timestamp.today().normalize()
    filas = []
    pedido = 100000
    for c in range(1, clientes + 1):
        n_pedidos = max(1, int(rng.negative_binomial(1.2, 0.35)))
        primero = fin - timedelta(days=int(rng.integers(30, dias)))
        fecha = primero
        for _ in range(n_pedidos):
            if fecha > fin:
                break
            pedido += 1
            for sku in rng.choice(skus, size=int(rng.integers(1, 5)), replace=False):
                filas.append((str(pedido), sku, f"Producto {sku[-3:]}", int(rng.integers(1, 6)),
                              fecha, precios[sku], f"C{c:04d}", "Chile"))
            fecha = fecha + timedelta(days=int(rng.gamma(2.0, 20.0)) + 1)
    df = pd.DataFrame(filas, columns=["id_pedido", "sku", "descripcion", "cantidad", "fecha_pedido",
                                      "precio_unitario", "id_cliente", "pais"])
    return normalizar(df, {c: c for c in df.columns})
