"""Clientes: agregación, segmentación RFM (H), ABC, cohortes, latencia y predicciones.

Las predicciones (BG/NBD y Gamma-Gamma) están implementadas aquí con SciPy en vez
de depender del paquete `lifetimes`, que no se mantiene y rompe con pandas moderno.
"""
from __future__ import annotations

import operator as op

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln, hyp2f1

from toomer.core import utilidades
from toomer.core.transacciones import obtener_transacciones


def obtener_clientes(lineas: pd.DataFrame) -> pd.DataFrame:
    c = lineas.groupby("id_cliente").agg(
        ingresos=("precio_linea", "sum"),
        pedidos=("id_pedido", "nunique"),
        skus=("sku", "nunique"),
        unidades=("cantidad", "sum"),
        primer_pedido=("fecha_pedido", "min"),
        ultimo_pedido=("fecha_pedido", "max"),
    ).reset_index()
    c["unidades_medias"] = (c["unidades"] / c["pedidos"]).round(2)
    c["ticket_medio"] = (c["ingresos"] / c["pedidos"]).round(2)
    hoy = pd.Timestamp.today()
    c["antiguedad_dias"] = (hoy - c["primer_pedido"]).dt.days
    c["recencia_dias"] = (hoy - c["ultimo_pedido"]).dt.days
    c["cohorte"] = c["primer_pedido"].dt.year.astype(str) + "T" + c["primer_pedido"].dt.quarter.astype(str)
    return c


# ---------------------------------------------------------------- RFM (H)

def _kmeans_1d(valores: np.ndarray, k: int = 5, iteraciones: int = 100, semilla: int = 0) -> np.ndarray:
    """K-means unidimensional; devuelve el índice de clúster (0..k-1) ordenado por centro ascendente."""
    v = valores.astype(float)
    unicos = np.unique(v)
    if len(unicos) <= k:
        return np.searchsorted(unicos, v)
    centros = np.quantile(v, np.linspace(0.1, 0.9, k))
    for _ in range(iteraciones):
        asign = np.abs(v[:, None] - centros[None, :]).argmin(axis=1)
        nuevos = np.array([v[asign == i].mean() if np.any(asign == i) else centros[i] for i in range(k)])
        if np.allclose(nuevos, centros):
            break
        centros = nuevos
    orden = np.argsort(centros)
    rango = np.empty_like(orden)
    rango[orden] = np.arange(k)
    return rango[asign]


def _puntuar(df: pd.DataFrame, columna: str, nombre: str, ascendente: bool = True) -> pd.DataFrame:
    idx = _kmeans_1d(df[columna].to_numpy())
    puntaje = idx + 1 if ascendente else 5 - idx
    df[nombre] = puntaje.astype(int)
    return df


def _etiqueta_rfm(rfm: int) -> str:
    if 111 <= rfm <= 155:
        return "En riesgo"
    if 211 <= rfm <= 255:
        return "Mantener y mejorar"
    if 311 <= rfm <= 353:
        return "Potencial leal"
    if 354 <= rfm <= 454 or 511 <= rfm <= 535 or rfm == 541:
        return "Leal"
    if rfm == 455 or 542 <= rfm <= 555:
        return "Estrella"
    return "Otro"


def segmentos_rfm(clientes: pd.DataFrame) -> pd.DataFrame:
    s = pd.DataFrame({
        "id_cliente": clientes["id_cliente"],
        "fecha_adquisicion": clientes["primer_pedido"],
        "fecha_recencia": clientes["ultimo_pedido"],
        "recencia": clientes["recencia_dias"],
        "frecuencia": clientes["pedidos"],
        "monetario": clientes["ingresos"],
        "heterogeneidad": clientes["skus"],
        "antiguedad": clientes["antiguedad_dias"],
    })
    s = _puntuar(s, "recencia", "r", ascendente=False)
    s = _puntuar(s, "frecuencia", "f")
    s = _puntuar(s, "monetario", "m")
    s = _puntuar(s, "heterogeneidad", "h")
    s["rfm"] = s["r"].astype(str) + s["f"].astype(str) + s["m"].astype(str)
    s["puntaje_rfm"] = s["r"] + s["f"] + s["m"]
    s["segmento_rfm"] = s["rfm"].astype(int).map(_etiqueta_rfm)
    return s


# ---------------------------------------------------------------- ABC

def segmentos_abc(clientes: pd.DataFrame, meses: int = 12) -> pd.DataFrame:
    activos = clientes[clientes["recencia_dias"] <= meses * 30].sort_values("ingresos", ascending=False).copy()
    pct = activos["ingresos"].cumsum() / activos["ingresos"].sum() * 100
    activos["clase_abc"] = pct.apply(utilidades.clasificar_abc)
    activos["rango_abc"] = pct.rank().astype(int)
    inactivos = clientes[clientes["recencia_dias"] > meses * 30].copy()
    inactivos["clase_abc"] = "D"
    inactivos["rango_abc"] = len(activos) + 1
    abc = pd.concat([activos, inactivos])
    return abc[["id_cliente", "clase_abc", "rango_abc", "ingresos", "recencia_dias"]]


# ---------------------------------------------------------------- Cohortes

def cohortes(lineas: pd.DataFrame, periodo: str = "M") -> pd.DataFrame:
    df = lineas[["id_cliente", "id_pedido", "fecha_pedido"]].drop_duplicates()
    df = df.assign(cohorte_adquisicion=df.groupby("id_cliente")["fecha_pedido"].transform("min").dt.to_period(periodo))
    df = df.assign(cohorte_pedido=df["fecha_pedido"].dt.to_period(periodo))
    return df


def retencion(lineas: pd.DataFrame, periodo: str = "M") -> pd.DataFrame:
    df = cohortes(lineas, periodo).groupby(["cohorte_adquisicion", "cohorte_pedido"]).agg(
        clientes=("id_cliente", "nunique")).reset_index()
    df["periodos"] = (df["cohorte_pedido"] - df["cohorte_adquisicion"]).apply(op.attrgetter("n"))
    return df


def matriz_cohortes(lineas: pd.DataFrame, periodo: str = "M", porcentaje: bool = False) -> pd.DataFrame:
    m = retencion(lineas, periodo).pivot_table(index="cohorte_adquisicion", columns="periodos", values="clientes")
    if porcentaje:
        m = (m.divide(m.iloc[:, 0], axis=0) * 100).round(1)
    m.index = m.index.astype(str)
    m.columns = [str(c) for c in m.columns]
    return m.reset_index()


# ---------------------------------------------------------------- Latencia

def _etiqueta_latencia(media, desv, recencia):
    sup = media - (recencia - desv)
    inf = media - (recencia + desv)
    if recencia < inf:
        return "Pedido no vencido"
    if recencia <= sup:
        return "Pedido próximo"
    return "Pedido atrasado"


def latencia(transacciones: pd.DataFrame) -> pd.DataFrame:
    """Días entre pedidos por cliente y estimación de cuándo debería comprar de nuevo."""
    t = transacciones[transacciones["ingresos"] > 0][["id_pedido", "id_cliente", "fecha_pedido"]].copy()
    t = t.sort_values("fecha_pedido", ascending=False)
    t["fecha_anterior"] = utilidades.valor_anterior(t, "id_cliente", "fecha_pedido")
    t["dias_desde_anterior"] = utilidades.dias_entre(t, "fecha_anterior", "fecha_pedido")
    t["numero_pedido"] = utilidades.conteo_acumulado(t, "id_cliente", "id_pedido", "fecha_pedido")

    hoy = pd.Timestamp.today()
    c = t.groupby("id_cliente").agg(frecuencia=("id_pedido", "nunique"), fecha_recencia=("fecha_pedido", "max"),
                                    latencia_media=("dias_desde_anterior", "mean")).reset_index()
    c["recencia"] = ((hoy - c["fecha_recencia"]) / np.timedelta64(1, "D")).round().astype(int)
    c["latencia_media"] = c["latencia_media"].astype(int)
    rec = t[t["numero_pedido"] > 0].groupby("id_cliente")["dias_desde_anterior"]
    c = c.merge(rec.min().rename("latencia_min"), on="id_cliente", how="left")
    c = c.merge(rec.max().rename("latencia_max"), on="id_cliente", how="left")
    c = c.merge(rec.std().rename("latencia_desv"), on="id_cliente", how="left")
    c["cv"] = c["latencia_desv"] / c["latencia_media"].replace(0, np.nan)
    c["dias_hasta_proximo"] = (c["latencia_media"] - (c["recencia"] - c["latencia_desv"])).round()
    c["etiqueta"] = [
        _etiqueta_latencia(a, d, r) if pd.notna(d) else "Solo un pedido"
        for a, d, r in zip(c["latencia_media"], c["latencia_desv"], c["recencia"])
    ]
    return c


# ---------------------------------------------------------------- BG/NBD + Gamma-Gamma

def resumen_rfmt(transacciones: pd.DataFrame, fin_observacion: str | pd.Timestamp) -> pd.DataFrame:
    """frecuencia (compras repetidas), recencia, T y valor monetario medio por cliente (como lifetimes)."""
    fin = pd.Timestamp(fin_observacion).normalize()
    t = transacciones[transacciones["devolucion"] == 0].copy()
    t["dia"] = t["fecha_pedido"].dt.normalize()
    t = t[t["dia"] <= fin]
    diario = t.groupby(["id_cliente", "dia"])["ingresos"].sum().reset_index()
    diario = diario.sort_values(["id_cliente", "dia"])
    primera = diario.groupby("id_cliente")["dia"].transform("min")
    repetidas = diario[diario["dia"] > primera]
    g = diario.groupby("id_cliente")["dia"]
    r = pd.DataFrame({
        "frecuencia": g.count() - 1,
        "recencia": (g.max() - g.min()).dt.days.astype(float),
        "T": (fin - g.min()).dt.days.astype(float),
    })
    r["valor_monetario"] = repetidas.groupby("id_cliente")["ingresos"].mean()
    r["valor_monetario"] = r["valor_monetario"].fillna(0.0)
    return r.reset_index()


class ModeloBGNBD:
    def __init__(self, penalizacion: float = 0.0):
        self.penalizacion = penalizacion
        self.params = None  # r, alpha, a, b

    def _nll(self, log_p, x, tx, T):
        r, alpha, a, b = np.exp(log_p)
        A1 = gammaln(r + x) - gammaln(r) + r * np.log(alpha)
        A2 = gammaln(a + b) + gammaln(b + x) - gammaln(b) - gammaln(a + b + x)
        A3 = -(r + x) * np.log(alpha + T)
        con_x = x > 0
        A4 = np.where(con_x, np.log(a) - np.log(np.where(con_x, b + x - 1, 1)) - (r + x) * np.log(alpha + tx), -np.inf)
        ll = A1 + A2 + np.logaddexp(A3, A4)
        return -ll.mean() + self.penalizacion * np.sum(np.exp(log_p) ** 2)

    def ajustar(self, frecuencia, recencia, T):
        x, tx, T = (np.asarray(v, dtype=float) for v in (frecuencia, recencia, T))
        res = minimize(self._nll, np.log([1.0, 1.0, 1.0, 1.0]), args=(x, tx, T), method="Nelder-Mead",
                       options={"maxiter": 4000, "xatol": 1e-6, "fatol": 1e-8})
        self.params = np.exp(res.x)
        return self

    def compras_esperadas(self, t, frecuencia, recencia, T):
        r, alpha, a, b = self.params
        x, tx, T = (np.asarray(v, dtype=float) for v in (frecuencia, recencia, T))
        h = hyp2f1(r + x, b + x, a + b + x - 1, t / (alpha + T + t))
        num = (a + b + x - 1) / (a - 1) * (1 - ((alpha + T) / (alpha + T + t)) ** (r + x) * h)
        den = 1 + np.where(x > 0, a / (b + x - 1) * ((alpha + T) / (alpha + tx)) ** (r + x), 0)
        return num / den


class ModeloGammaGamma:
    def __init__(self, penalizacion: float = 0.0):
        self.penalizacion = penalizacion
        self.params = None  # p, q, v

    def _nll(self, log_p, x, m):
        p, q, v = np.exp(log_p)
        ll = (gammaln(p * x + q) - gammaln(p * x) - gammaln(q) + q * np.log(v)
              + (p * x - 1) * np.log(m) + p * x * np.log(x) - (p * x + q) * np.log(v + m * x))
        return -ll.mean() + self.penalizacion * np.sum(np.exp(log_p) ** 2)

    def ajustar(self, frecuencia, valor_monetario):
        x, m = np.asarray(frecuencia, dtype=float), np.asarray(valor_monetario, dtype=float)
        res = minimize(self._nll, np.log([1.0, 1.0, 1.0]), args=(x, m), method="Nelder-Mead",
                       options={"maxiter": 4000, "xatol": 1e-6, "fatol": 1e-8})
        self.params = np.exp(res.x)
        return self

    def ticket_esperado(self, frecuencia, valor_monetario):
        p, q, v = self.params
        x, m = np.asarray(frecuencia, dtype=float), np.asarray(valor_monetario, dtype=float)
        peso = p * x / (p * x + q - 1)
        media_poblacion = v * p / (q - 1)
        return (1 - peso) * media_poblacion + peso * m

    def valor_vida(self, bgnbd, frecuencia, recencia, T, valor_monetario, meses=12, tasa_descuento=0.01):
        ticket = self.ticket_esperado(frecuencia, valor_monetario)
        clv = np.zeros(len(ticket))
        for i in range(30, 30 * meses + 1, 30):
            nuevas = bgnbd.compras_esperadas(i, frecuencia, recencia, T) - bgnbd.compras_esperadas(i - 30, frecuencia, recencia, T)
            clv += ticket * nuevas / (1 + tasa_descuento) ** (i / 30)
        return clv


def predicciones_clientes(transacciones: pd.DataFrame, fin_observacion, dias: int = 90, meses: int = 3,
                          tasa_descuento: float = 0.01, penalizacion_gg: float = 0.0,
                          penalizacion_bg: float = 0.0) -> pd.DataFrame:
    """Compras previstas (BG/NBD), ticket previsto y CLV (Gamma-Gamma) por cliente."""
    rfmt = resumen_rfmt(transacciones, fin_observacion)
    bg = ModeloBGNBD(penalizacion_bg).ajustar(rfmt["frecuencia"], rfmt["recencia"], rfmt["T"])
    rfmt["compras_previstas"] = bg.compras_esperadas(dias, rfmt["frecuencia"], rfmt["recencia"], rfmt["T"])

    rep = rfmt[(rfmt["frecuencia"] > 0) & (rfmt["valor_monetario"] > 0)]
    if len(rep) >= 5:
        gg = ModeloGammaGamma(penalizacion_gg).ajustar(rep["frecuencia"], rep["valor_monetario"])
        rfmt.loc[rep.index, "ticket_previsto"] = gg.ticket_esperado(rep["frecuencia"], rep["valor_monetario"])
        rfmt.loc[rep.index, "clv"] = gg.valor_vida(bg, rep["frecuencia"], rep["recencia"], rep["T"],
                                                   rep["valor_monetario"], meses, tasa_descuento)
    else:
        rfmt["ticket_previsto"] = np.nan
        rfmt["clv"] = np.nan
    out = rfmt[["id_cliente", "frecuencia", "recencia", "T", "valor_monetario", "compras_previstas", "ticket_previsto", "clv"]]
    return out.round(2)
