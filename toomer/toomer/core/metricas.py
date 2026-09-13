"""Métricas de retail/marketing de EcommerceTools, como fórmulas declarativas para la calculadora."""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Metrica:
    clave: str
    nombre: str
    categoria: str
    campos: list[tuple[str, str, float]]  # (clave, etiqueta, valor por defecto)
    formula: object
    descripcion: str = ""
    unidad: str = ""


def _m(clave, nombre, cat, campos, formula, desc="", unidad=""):
    return Metrica(clave, nombre, cat, campos, formula, desc, unidad)


METRICAS: list[Metrica] = [
    # Ventas y finanzas
    _m("impuesto", "Impuesto", "Ventas y finanzas", [("ingresos", "Ingresos brutos", 1000), ("tasa", "Tasa de impuesto (0.19 = 19 %)", 0.19)],
       lambda ingresos, tasa: ingresos * tasa, "Impuesto contenido en los ingresos brutos."),
    _m("ingreso_neto", "Ingreso neto", "Ventas y finanzas", [("ingresos", "Ingresos brutos", 1000), ("tasa", "Tasa de impuesto", 0.19)],
       lambda ingresos, tasa: ingresos - ingresos * tasa),
    _m("ticket_medio", "Ticket medio (AOV)", "Ventas y finanzas", [("ingresos", "Ingresos totales", 50000), ("pedidos", "Pedidos", 800)],
       lambda ingresos, pedidos: ingresos / pedidos),
    _m("costo_producto", "Costo de producto", "Ventas y finanzas", [("ingresos", "Ingresos brutos", 1000), ("margen", "Margen (0.3 = 30 %)", 0.3), ("tasa", "Tasa de impuesto", 0.19)],
       lambda ingresos, margen, tasa: (ingresos - ingresos * tasa) * margen),
    _m("utilidad_bruta", "Utilidad bruta", "Ventas y finanzas", [("ingresos", "Ingresos brutos", 1000), ("margen", "Margen", 0.3), ("tasa", "Tasa de impuesto", 0.19)],
       lambda ingresos, margen, tasa: ingresos - ((ingresos - ingresos * tasa) * margen + ingresos * tasa)),
    _m("utilidad_neta", "Utilidad neta", "Ventas y finanzas", [("ingresos", "Ingresos brutos", 1000), ("otros", "Otros costos", 100), ("margen", "Margen", 0.3), ("tasa", "Tasa de impuesto", 0.19)],
       lambda ingresos, otros, margen, tasa: ingresos - ((ingresos - ingresos * tasa) * margen + ingresos * tasa + otros)),
    _m("crecimiento_ventas", "Crecimiento de ventas", "Ventas y finanzas", [("p1", "Ventas período anterior", 1000), ("p2", "Ventas período actual", 1200)],
       lambda p1, p2: (p2 - p1) / p1 * 100, unidad="%"),
    _m("ingreso_por_unidad", "Ingreso por unidad", "Ventas y finanzas", [("ingresos", "Ingresos", 1000), ("unidades", "Unidades", 250)],
       lambda ingresos, unidades: ingresos / unidades),
    _m("cuota_mercado", "Cuota de mercado", "Estrategia", [("empresa", "Ventas de la empresa", 1000), ("mercado", "Ventas del mercado", 20000)],
       lambda empresa, mercado: empresa / mercado * 100, unidad="%"),
    # Clientes
    _m("tasa_retencion", "Tasa de retención", "Clientes", [("recompran", "Clientes que recompraron", 120), ("previos", "Clientes del período anterior", 400)],
       lambda recompran, previos: recompran / previos * 100, unidad="%"),
    # Producto
    _m("share_of_shelf", "Índice share of shelf", "Producto", [("marca", "Productos de la marca", 12), ("total", "Total de productos", 100)],
       lambda marca, total: marca / total * 100, unidad="%"),
    _m("rotacion", "Rotación de producto (sell-through)", "Producto", [("vendidas", "Unidades vendidas", 300), ("stock", "Stock medio", 400)],
       lambda vendidas, stock: vendidas / stock * 100, unidad="%"),
    _m("indice_precio", "Índice de precio", "Producto", [("px", "Precio producto X", 12), ("py", "Precio producto Y", 10)],
       lambda px, py: px / py * 100, unidad="%"),
    _m("intencion_compra", "Intención de compra", "Producto", [("interesados", "Personas interesadas", 50), ("total", "Total de personas", 1000)],
       lambda interesados, total: interesados / total * 100, unidad="%"),
    _m("tasa_prueba", "Tasa de prueba de producto", "Producto", [("primeras", "Compradores por primera vez", 40), ("total", "Total de compradores", 200)],
       lambda primeras, total: primeras / total * 100, unidad="%"),
    _m("tasa_recompra", "Tasa de recompra de producto", "Producto", [("repiten", "Compradores que repiten", 60), ("total", "Total de compradores", 200)],
       lambda repiten, total: repiten / total * 100, unidad="%"),
    _m("consumo", "Tasa de consumo (unidades por pedido)", "Producto", [("unidades", "Unidades del SKU", 500), ("pedidos", "Pedidos", 200)],
       lambda unidades, pedidos: unidades / pedidos),
    _m("penetracion_marca", "Penetración de marca", "Producto", [("marca", "Compradores de la marca", 80), ("total", "Total de compradores", 1000)],
       lambda marca, total: marca / total * 100, unidad="%"),
    _m("satisfaccion_producto", "Satisfacción de producto", "Producto", [("total", "Reseñas totales", 100), ("positivas", "Reseñas positivas", 85)],
       lambda total, positivas: positivas / total * 100, unidad="%"),
    # Marketing
    _m("cpm", "CPM (costo por mil)", "Marketing", [("costo", "Costo total", 500), ("destinatarios", "Destinatarios", 25000)],
       lambda costo, destinatarios: costo / destinatarios * 1000),
    _m("cpo", "CPO (costo por pedido)", "Marketing", [("costo", "Costo total", 500), ("pedidos", "Pedidos", 40)],
       lambda costo, pedidos: costo / pedidos),
    _m("cpa", "CPA (costo por adquisición)", "Marketing", [("costo", "Costo total", 500), ("adquisiciones", "Adquisiciones", 25)],
       lambda costo, adquisiciones: costo / adquisiciones),
    _m("cpc", "CPC (costo por clic)", "Marketing", [("costo", "Costo total", 500), ("clics", "Clics", 1200)],
       lambda costo, clics: costo / clics),
    _m("tasa_conversion", "Tasa de conversión", "Marketing", [("conversiones", "Conversiones", 30), ("acciones", "Acciones (visitas, clics…)", 1500)],
       lambda conversiones, acciones: conversiones / acciones * 100, unidad="%"),
    _m("lin_rodnitsky", "Ratio Lin-Rodnitsky", "Marketing", [("todas", "Costo/conv. medio (todas las consultas)", 20), ("con_conv", "Costo/conv. medio (consultas con ≥1 conv.)", 12)],
       lambda todas, con_conv: todas / con_conv, "1.0–1.5 gestión conservadora · 1.5–2.0 bien gestionada · 2.0–2.5 agresiva · >2.5 mal gestionada."),
    _m("romi", "ROMI", "Marketing", [("ingresos", "Ingresos", 5000), ("costo", "Costo de marketing", 1000)],
       lambda ingresos, costo: (ingresos - costo) / costo * 100, unidad="%"),
    _m("roi", "ROI", "Marketing", [("ingresos", "Ingresos", 5000), ("marketing", "Costo de marketing", 1000), ("otros", "Otros costos", 500)],
       lambda ingresos, marketing, otros: (ingresos - (marketing + otros)) / (marketing + otros) * 100, unidad="%"),
    _m("roas", "ROAS", "Marketing", [("ingresos", "Ingresos", 5000), ("costo", "Inversión publicitaria", 1000)],
       lambda ingresos, costo: ingresos / costo),
    # Contenido y social
    _m("indice_foco", "Índice de foco", "Contenido", [("media", "Páginas vistas medias en la sección", 3), ("total", "Páginas de la sección", 20)],
       lambda media, total: media / total * 100, unidad="%"),
    _m("stickiness", "Stickiness", "Contenido", [("visitas", "Visitas", 1000), ("duracion", "Minutos totales", 5000), ("usuarios", "Usuarios únicos", 600)],
       lambda visitas, duracion, usuarios: (visitas / usuarios) * (duracion / visitas) * (usuarios / visitas)),
    _m("sesiones_producto", "Sesiones con vistas de producto", "Contenido", [("total", "Sesiones totales", 1000), ("con_producto", "Sesiones con producto", 450)],
       lambda total, con_producto: con_producto / total * 100, unidad="%"),
    _m("engagement", "Tasa de engagement", "Redes sociales", [("interactuaron", "Seguidores que interactuaron", 120), ("total", "Seguidores", 5000)],
       lambda interactuaron, total: interactuaron / total * 100, unidad="%"),
    # Inventario
    _m("dio", "Días de inventario (DIO)", "Inventario", [("inventario", "Costo medio de inventario", 20000), ("cogs", "Costo de ventas", 100000)],
       lambda inventario, cogs: inventario / cogs * 365, unidad="días"),
    _m("stock_seguridad", "Stock de seguridad", "Inventario", [("max_dia", "Máx. unidades/día", 20), ("med_dia", "Unidades/día medias", 10), ("max_lead", "Lead time máx. (días)", 14), ("med_lead", "Lead time medio (días)", 7)],
       lambda max_dia, med_dia, max_lead, med_lead: max_dia * max_lead - med_dia * med_lead, unidad="unidades"),
    _m("punto_reorden", "Punto de reorden", "Inventario", [("max_dia", "Máx. unidades/día", 20), ("med_dia", "Unidades/día medias", 10), ("max_lead", "Lead time máx.", 14), ("med_lead", "Lead time medio", 7), ("lead", "Lead time (días)", 7)],
       lambda max_dia, med_dia, max_lead, med_lead, lead: lead * med_dia + (max_dia * max_lead - med_dia * med_lead), unidad="unidades"),
    _m("tasa_backorder", "Tasa de pedidos pendientes", "Inventario", [("pendientes", "Pedidos pendientes (sin stock)", 15), ("total", "Pedidos totales", 500)],
       lambda pendientes, total: pendientes / total * 100, unidad="%"),
    _m("velocidad_ventas", "Velocidad de ventas", "Inventario", [("unidades_12m", "Unidades vendidas 12 meses", 3650), ("dias_stock", "Días en stock", 300), ("dias", "Días a proyectar", 30)],
       lambda unidades_12m, dias_stock, dias: unidades_12m / dias_stock * dias, unidad="unidades"),
    _m("precision_pronostico", "Precisión del pronóstico", "Inventario", [("real", "Demanda real", 1000), ("pronostico", "Demanda pronosticada", 900)],
       lambda real, pronostico: (real - pronostico) / real * 100, unidad="%"),
    _m("eoq", "Cantidad económica de pedido (EOQ)", "Inventario", [("demanda", "Demanda (unidades)", 1000), ("costo_pedido", "Costo por pedido", 50), ("costo_almacen", "Costo de almacenar por unidad", 2)],
       lambda demanda, costo_pedido, costo_almacen: math.sqrt(demanda * costo_pedido * 2 / costo_almacen), unidad="unidades"),
    # Atención al cliente y operaciones
    _m("csat", "CSAT", "Atención al cliente", [("total", "Respuestas totales", 200), ("positivas", "Respuestas positivas", 170)],
       lambda total, positivas: positivas / total * 100, unidad="%"),
    _m("nps", "NPS", "Atención al cliente", [("promotores", "Promotores (9-10)", 120), ("detractores", "Detractores (0-6)", 30), ("total", "Encuestados", 200)],
       lambda promotores, detractores, total: promotores * 100 / total - detractores * 100 / total),
    _m("tickets_por_pedido", "Ratio tickets/pedidos", "Atención al cliente", [("tickets", "Tickets", 50), ("pedidos", "Pedidos", 500)],
       lambda tickets, pedidos: tickets / pedidos * 100, unidad="%"),
    _m("tickets_por_resolucion", "Tickets por resolución", "Atención al cliente", [("tickets", "Tickets", 50), ("resueltos", "Casos resueltos", 40)],
       lambda tickets, resueltos: tickets / resueltos),
    _m("nivel_servicio", "Nivel de servicio", "Operaciones", [("recibidos", "Pedidos recibidos", 500), ("entregados", "Pedidos entregados", 480)],
       lambda recibidos, entregados: entregados / recibidos * 100, unidad="%"),
    _m("precision_inventario", "Precisión del inventario disponible", "Operaciones", [("contados", "Ítems contados", 1000), ("coinciden", "Ítems que coinciden con el registro", 970)],
       lambda contados, coinciden: coinciden / contados * 100, unidad="%"),
    _m("ventas_perdidas", "Ratio de ventas perdidas", "Operaciones", [("sin_stock", "Días sin stock", 5), ("periodo", "Días del período", 30)],
       lambda sin_stock, periodo: sin_stock / periodo * 100, unidad="%"),
]

CATEGORIAS = list(dict.fromkeys(m.categoria for m in METRICAS))


def calcular(metrica: Metrica, valores: dict[str, float]) -> float:
    return float(metrica.formula(**{k: valores[k] for k, _, _ in metrica.campos}))
