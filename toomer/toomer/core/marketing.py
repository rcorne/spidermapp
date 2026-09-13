"""Calendario comercial de ecommerce (adaptado al calendario hispanoamericano)."""
from __future__ import annotations

import pandas as pd
from pandas.tseries.holiday import FR, MO, SA, SU, AbstractHolidayCalendar, Holiday
from pandas.tseries.offsets import BDay


class CalendarioComercial(AbstractHolidayCalendar):
    rules = [
        Holiday("Rebajas de enero", month=1, day=2),
        Holiday("Día de Reyes [último día para pedir]", month=1, day=6, offset=BDay(-2)),
        Holiday("Día de Reyes", month=1, day=6),
        Holiday("San Valentín [último día para pedir]", month=2, day=14, offset=BDay(-2)),
        Holiday("San Valentín", month=2, day=14),
        Holiday("Día de la Mujer", month=3, day=8),
        Holiday("Día de la Madre [último día para pedir]", month=5, day=1, offset=[pd.DateOffset(weekday=SU(2)), BDay(-2)]),
        Holiday("Día de la Madre", month=5, day=1, offset=pd.DateOffset(weekday=SU(2))),
        Holiday("Día del Niño", month=8, day=1, offset=pd.DateOffset(weekday=SU(2))),
        Holiday("Día del Padre [último día para pedir]", month=6, day=1, offset=[pd.DateOffset(weekday=SU(3)), BDay(-2)]),
        Holiday("Día del Padre", month=6, day=1, offset=pd.DateOffset(weekday=SU(3))),
        Holiday("Halloween", month=10, day=31),
        Holiday("Black Friday [inicio de ofertas]", month=11, day=1, offset=[pd.DateOffset(weekday=SA(4)), BDay(-5)]),
        Holiday("Black Friday", month=11, day=1, offset=pd.DateOffset(weekday=FR(4))),
        Holiday("Cyber Monday", month=11, day=1, offset=[pd.DateOffset(weekday=SA(4)), pd.DateOffset(2)]),
        Holiday("Navidad [último día para pedir]", month=12, day=25, offset=BDay(-2)),
        Holiday("Navidad", month=12, day=25),
        Holiday("Año Nuevo [último día para pedir]", month=12, day=31, offset=BDay(-2)),
    ] + [
        # Día de pago: último día hábil de cada mes.
        Holiday(f"Día de pago ({m})", month=i, day=1, offset=[pd.DateOffset(months=1), BDay(-1)])
        for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                               "septiembre", "octubre", "noviembre", "diciembre"], start=1)
    ]


def _fechas(inicio, dias=365):
    return pd.DataFrame({"fecha": pd.date_range(inicio, periods=dias, freq="D")})


def eventos_comerciales(inicio, dias: int = 365) -> pd.DataFrame:
    f = _fechas(inicio, dias)
    ev = CalendarioComercial().holidays(start=f["fecha"].min(), end=f["fecha"].max(), return_name=True)
    ev = ev.reset_index()
    ev.columns = ["fecha", "evento"]
    return ev.sort_values("fecha").reset_index(drop=True)


def calendario_comercial(inicio, dias: int = 365) -> pd.DataFrame:
    f = _fechas(inicio, dias)
    ev = eventos_comerciales(inicio, dias).groupby("fecha")["evento"].agg(" · ".join).reset_index()
    cal = f.merge(ev, on="fecha", how="left").fillna("")
    cal["dia_semana"] = cal["fecha"].dt.day_name(locale=None).map({
        "Monday": "lunes", "Tuesday": "martes", "Wednesday": "miércoles", "Thursday": "jueves",
        "Friday": "viernes", "Saturday": "sábado", "Sunday": "domingo"})
    return cal
