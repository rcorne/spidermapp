import numpy as np
import pandas as pd
import pytest

from toomer.core import clientes, datos, informes, marketing, metricas, nlp, operaciones, productos, publicidad, seo, transacciones


@pytest.fixture(scope="module")
def lineas():
    return datos.generar_datos_sinteticos(clientes=150, dias=400)


def test_normalizar_detecta_columnas():
    crudo = pd.DataFrame({"InvoiceNo": ["1", "1"], "StockCode": ["A", "B"], "Quantity": [2, 1],
                          "InvoiceDate": ["2026-01-01", "2026-01-01"], "UnitPrice": [1.5, 2], "CustomerID": [17850.0, 17850.0]})
    df = datos.normalizar(crudo, datos.detectar_mapeo(list(crudo.columns)))
    assert list(df["precio_linea"]) == [3.0, 2.0]
    assert df["id_cliente"].iloc[0] == "17850"


def test_normalizar_exige_obligatorias():
    with pytest.raises(ValueError):
        datos.normalizar(pd.DataFrame({"x": [1]}), {"id_pedido": "x"})


def test_transacciones_y_productos(lineas):
    t = transacciones.obtener_transacciones(lineas)
    assert t["id_pedido"].is_unique and (t["numero_pedido"] >= 1).all()
    p = productos.obtener_productos(lineas)
    assert p["sku"].is_unique
    r = productos.tasas_de_recompra(lineas)
    assert r["tasa_recompra"].between(0, 1).all()


def test_clientes_rfm_abc_cohortes(lineas):
    c = clientes.obtener_clientes(lineas)
    s = clientes.segmentos_rfm(c)
    assert set(s["r"]).issubset({1, 2, 3, 4, 5}) and s["segmento_rfm"].notna().all()
    abc = clientes.segmentos_abc(c, 12)
    assert set(abc["clase_abc"]).issubset({"A", "B", "C", "D"}) and len(abc) == len(c)
    m = clientes.matriz_cohortes(lineas, "Q", True)
    assert (m.iloc[:, 1] == 100).all()
    lat = clientes.latencia(transacciones.obtener_transacciones(lineas))
    assert "etiqueta" in lat


def test_bgnbd_recupera_parametros():
    rng = np.random.default_rng(0)
    n, r, alpha, a, b = 2000, 0.3, 4.0, 0.8, 2.5
    lam, pdrop, T = rng.gamma(r, 1 / alpha, n), rng.beta(a, b, n), np.full(n, 60.0)
    freq, rec = np.zeros(n), np.zeros(n)
    for i in range(n):
        t = 0
        while True:
            t += rng.exponential(1 / lam[i])
            if t > T[i]:
                break
            freq[i] += 1
            rec[i] = t
            if rng.random() < pdrop[i]:
                break
    est = clientes.ModeloBGNBD().ajustar(freq, rec, T).params
    assert np.allclose(est, [r, alpha, a, b], rtol=0.35)


def test_predicciones(lineas):
    t = transacciones.obtener_transacciones(lineas)
    p = clientes.predicciones_clientes(t, pd.Timestamp.today(), dias=90, meses=3)
    assert {"compras_previstas", "ticket_previsto", "clv"} <= set(p.columns)
    assert (p["compras_previstas"] >= 0).all()


def test_publicidad():
    df = publicidad.generar_keywords(["cañas"], ["comprar"], ["baratas"], "c")
    assert len(df) == 12 and set(df["concordancia"]) == {"Exacta", "Frase", "Amplia", "Amplia modificada"}
    assert sorted(publicidad.generar_spintax("a {b|c}", False)) == ["a b", "a c"]


def test_operaciones_informes_marketing(lineas):
    abc = operaciones.clasificacion_inventario(lineas)
    assert abc["clase_abc"].iloc[0] == "A"
    assert not informes.informe_transacciones(lineas, "M").empty
    assert (informes.informe_clientes(lineas, "Y")["tasa_adquisicion"] <= 100).all()
    ev = marketing.eventos_comerciales("2026-01-01", 365)
    assert "Black Friday" in ev["evento"].values and ev.loc[ev["evento"] == "Black Friday", "fecha"].iloc[0] == pd.Timestamp("2026-11-27")


def test_nlp_y_metricas():
    r = nlp.resumir("Uno dos. Tres cuatro. Cinco seis. Siete ocho.", 2)
    assert r.count(".") == 2
    m = next(x for x in metricas.METRICAS if x.clave == "roas")
    assert metricas.calcular(m, {"ingresos": 500, "costo": 100}) == 5


def test_abcd_gsc():
    df = pd.DataFrame({"page": list("abcdef"), "clics": [50, 30, 10, 5, 5, 0], "impresiones": [1] * 6, "ctr": [0.1] * 6, "posicion": [1] * 6})
    c = seo.clasificar_abcd(df)
    assert c.set_index("page")["clase"].to_dict() == {"a": "A", "b": "A", "c": "B", "d": "C", "e": "C", "f": "D"}
    assert len(seo.resumen_abcd(c)) == 4
