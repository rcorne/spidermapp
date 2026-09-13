"""Resumen extractivo de texto, sin modelos pesados.

EcommerceTools usa un transformer (varios GB con torch). Toomer usa un resumen
extractivo por frecuencia de términos que funciona sin conexión y en cualquier idioma.
"""
from __future__ import annotations

import re
from collections import Counter

import pandas as pd

_STOP = set("""
a al algo ante antes aquel aquella as así aun aunque bajo bien cada como con contra cual cuando de del desde donde
dos e el ella ellas ellos en entre era eran es esa esas ese eso esos esta estas este esto estos fue fueron ha había
han hasta hay la las le les lo los más me mi mis mucho muy nada ni no nos o os otra otro para pero poco por porque
que qué quien se sea ser si sí sin sobre su sus también tan tanto te tiene tienen todo todos tu tus un una uno unos
y ya yo the a an and or of to in on for with is are was were be been by at from that this it its as
""".split())


def _frases(texto: str) -> list[str]:
    return [f.strip() for f in re.split(r"(?<=[.!?])\s+", texto.strip()) if f.strip()]


def _palabras(texto: str) -> list[str]:
    return [p for p in re.findall(r"[a-záéíóúñü0-9]+", texto.lower()) if p not in _STOP and len(p) > 2]


def resumir(texto: str, max_frases: int = 3) -> str:
    frases = _frases(texto)
    if len(frases) <= max_frases:
        return " ".join(frases)
    freq = Counter(_palabras(texto))
    puntajes = []
    for i, f in enumerate(frases):
        ps = _palabras(f)
        puntajes.append((sum(freq[p] for p in ps) / (len(ps) + 3), i))
    mejores = sorted(sorted(puntajes, reverse=True)[:max_frases], key=lambda x: x[1])
    return " ".join(frases[i] for _, i in mejores)


def resumir_columna(df: pd.DataFrame, columna: str, nombre_salida: str = "resumen", max_frases: int = 3) -> pd.DataFrame:
    df = df.copy()
    df[nombre_salida] = df[columna].fillna("").astype(str).map(lambda t: resumir(t, max_frases))
    return df
