from __future__ import annotations

import itertools
import random
import re

import pandas as pd


def _combinaciones(productos, prefijos, sufijos):
    kws = []
    for p in productos:
        kws.append([p, p])
        kws += [[p, f"{pre} {p}"] for pre in prefijos]
        kws += [[p, f"{p} {suf}"] for suf in sufijos]
    return kws


def generar_keywords(productos: list[str], prefijos: list[str], sufijos: list[str], campana: str) -> pd.DataFrame:
    """Keywords para búsqueda de pago con los cuatro tipos de concordancia de Google Ads."""
    kws = _combinaciones(productos, prefijos, sufijos)
    tipos = [
        ("Exacta", lambda k: f"[{k}]"),
        ("Frase", lambda k: f'"{k}"'),
        ("Amplia", lambda k: k),
        ("Amplia modificada", lambda k: "+" + k.replace(" ", " +")),
    ]
    filas = [(p, f(k), tipo) for tipo, f in tipos for p, k in kws]
    df = pd.DataFrame(filas, columns=["producto", "keyword", "concordancia"])
    df["campana"] = campana
    return df


def generar_spintax(texto: str, unico: bool = True):
    """Expande texto Spintax: 'Soy el {rey|presidente} de {Chile|Perú}'."""
    trozos = re.compile(r"({[^}]+}|[^{}]*)").split(texto)

    def opciones(s):
        return s[1:-1].split("|") if s.startswith("{") else [s]

    giros = ["".join(g) for g in itertools.product(*[opciones(t) for t in trozos])]
    giros = list(dict.fromkeys(giros))
    return random.choice(giros) if unico else giros
