"""Herramientas SEO: robots.txt, sitemaps, autocompletado, PageSpeed, Knowledge Graph,
scraping de metadatos, páginas indexadas/SERPs y Google Search Console."""
from __future__ import annotations

import json
import re
import urllib.parse
from typing import Callable

import httpx
import pandas as pd
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
_cliente = httpx.Client(headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"}, timeout=30, follow_redirects=True)


def _get(url: str) -> httpx.Response:
    r = _cliente.get(url)
    r.raise_for_status()
    return r


# ---------------------------------------------------------------- robots.txt

def sitemaps_en_robots(url: str) -> list[str]:
    texto = _get(url).text
    return [l.split(":", 1)[1].strip() for l in texto.splitlines() if l.lower().startswith("sitemap:")]


def leer_robots(url: str) -> pd.DataFrame:
    texto = _get(url).text
    filas = []
    for l in texto.splitlines():
        l = l.strip()
        if not l or l.startswith("#") or ":" not in l:
            continue
        directiva, valor = l.split(":", 1)
        filas.append((directiva.strip(), valor.strip()))
    return pd.DataFrame(filas, columns=["directiva", "valor"])


# ---------------------------------------------------------------- Sitemaps

def _xml(url: str) -> BeautifulSoup:
    return BeautifulSoup(_get(url).content, "xml")


def leer_sitemap(url: str, progreso: Callable[[str], None] | None = None) -> pd.DataFrame:
    """Lee un sitemap XML (o un índice de sitemaps, recursivamente) a un DataFrame."""
    xml = _xml(url)
    if xml.find("sitemapindex"):
        partes = []
        for s in xml.find_all("sitemap"):
            loc = s.find("loc")
            if loc:
                if progreso:
                    progreso(loc.text.strip())
                partes.append(leer_sitemap(loc.text.strip(), progreso))
        return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    filas = []
    for u in xml.find_all("url"):
        loc = u.find("loc")
        if not loc:
            continue
        filas.append({
            "loc": loc.text.strip(),
            "lastmod": u.find("lastmod").text.strip() if u.find("lastmod") else "",
            "changefreq": u.find("changefreq").text.strip() if u.find("changefreq") else "",
            "priority": u.find("priority").text.strip() if u.find("priority") else "",
            "dominio": urllib.parse.urlparse(loc.text.strip()).netloc,
            "sitemap": url,
        })
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- Scraping de páginas

def _meta(soup, nombre):
    tag = soup.find("meta", attrs={"name": nombre})
    return tag.get("content", "").strip() if tag else ""


def analizar_pagina(url: str) -> dict:
    r = _get(url)
    soup = BeautifulSoup(r.text, "lxml")
    canonical = soup.find("link", rel="canonical")
    hreflang = [l.get("hreflang") for l in soup.find_all("link", rel="alternate") if l.get("hreflang")]
    parrafos = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    enlaces = {urllib.parse.urljoin(url, a["href"]) for a in soup.find_all("a", href=True)}
    return {
        "url": url,
        "estado": r.status_code,
        "titulo": soup.title.get_text(strip=True) if soup.title else "",
        "descripcion": _meta(soup, "description"),
        "canonical": canonical.get("href", "") if canonical else "",
        "robots": _meta(soup, "robots"),
        "generador": _meta(soup, "generator"),
        "hreflang": ", ".join(hreflang),
        "h1": " | ".join(h.get_text(" ", strip=True) for h in soup.find_all("h1")),
        "n_enlaces": len(enlaces),
        "n_parrafos": len(parrafos),
        "palabras": sum(len(p.split()) for p in parrafos),
        "texto": " ".join(parrafos),
    }


def analizar_sitio(urls: list[str], progreso: Callable[[int, int, str], None] | None = None) -> pd.DataFrame:
    filas = []
    for i, u in enumerate(urls, 1):
        if progreso:
            progreso(i, len(urls), u)
        try:
            filas.append(analizar_pagina(u))
        except Exception as e:  # noqa: BLE001
            filas.append({"url": u, "estado": 0, "titulo": f"Error: {e}"})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- Google Autocomplete

PREFIJOS = ["cómo", "qué", "cuál", "dónde", "por qué", "cuándo", "mejor", "barato", "comprar", "precio"]
SUFIJOS = list("abcdefghijklmnopqrstuvwxyz") + ["precio", "opiniones", "vs", "cerca", "online", "chile", "gratis"]


def _sugerencias(consulta: str, idioma: str = "es") -> list[dict]:
    url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(
        {"client": "chrome", "hl": idioma, "q": consulta})
    datos = json.loads(_get(url).text)
    sugerencias = datos[1]
    relevancias = datos[4].get("google:suggestrelevance", []) if len(datos) > 4 else []
    return [{"consulta": consulta, "sugerencia": s, "relevancia": relevancias[i] if i < len(relevancias) else 0}
            for i, s in enumerate(sugerencias)]


def autocompletar(consulta: str, expandir: bool = True, idioma: str = "es",
                  progreso: Callable[[int, int], None] | None = None) -> pd.DataFrame:
    terminos = [consulta]
    if expandir:
        terminos += [f"{p} {consulta}" for p in PREFIJOS] + [f"{consulta} {s}" for s in SUFIJOS]
    res = []
    for i, t in enumerate(terminos, 1):
        if progreso:
            progreso(i, len(terminos))
        try:
            res += _sugerencias(t, idioma)
        except Exception:  # noqa: BLE001
            continue
    df = pd.DataFrame(res, columns=["consulta", "sugerencia", "relevancia"])
    return df.drop_duplicates("sugerencia").sort_values("relevancia", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------- PageSpeed Insights

def core_web_vitals(api_key: str, urls: list[str], estrategia: str = "mobile",
                    progreso: Callable[[int, int, str], None] | None = None) -> pd.DataFrame:
    filas = []
    for i, u in enumerate(urls, 1):
        if progreso:
            progreso(i, len(urls), u)
        q = urllib.parse.urlencode({"url": u, "key": api_key, "strategy": estrategia, "category": "performance"})
        try:
            d = json.loads(_cliente.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed?" + q, timeout=120).text)
            lh = d.get("lighthouseResult", {})
            aud = lh.get("audits", {})
            campo = d.get("loadingExperience", {}).get("metrics", {})
            filas.append({
                "url": u, "estrategia": estrategia,
                "puntaje_rendimiento": round(lh.get("categories", {}).get("performance", {}).get("score", 0) * 100),
                "FCP_s": aud.get("first-contentful-paint", {}).get("numericValue", 0) / 1000,
                "LCP_s": aud.get("largest-contentful-paint", {}).get("numericValue", 0) / 1000,
                "TBT_ms": aud.get("total-blocking-time", {}).get("numericValue", 0),
                "CLS": aud.get("cumulative-layout-shift", {}).get("numericValue", 0),
                "Speed_Index_s": aud.get("speed-index", {}).get("numericValue", 0) / 1000,
                "campo_LCP_ms": campo.get("LARGEST_CONTENTFUL_PAINT_MS", {}).get("percentile", ""),
                "campo_INP_ms": campo.get("INTERACTION_TO_NEXT_PAINT", {}).get("percentile", ""),
                "campo_CLS": campo.get("CUMULATIVE_LAYOUT_SHIFT_SCORE", {}).get("percentile", ""),
                "error": d.get("error", {}).get("message", ""),
            })
        except Exception as e:  # noqa: BLE001
            filas.append({"url": u, "estrategia": estrategia, "error": str(e)})
    return pd.DataFrame(filas).round(2)


# ---------------------------------------------------------------- Knowledge Graph

def knowledge_graph(api_key: str, consulta: str, limite: int = 10, idioma: str = "es") -> pd.DataFrame:
    q = urllib.parse.urlencode({"query": consulta, "key": api_key, "limit": limite, "indent": True, "languages": idioma})
    d = json.loads(_get("https://kgsearch.googleapis.com/v1/entities:search?" + q).text)
    filas = []
    for e in d.get("itemListElement", []):
        r = e.get("result", {})
        filas.append({
            "nombre": r.get("name", ""), "tipos": ", ".join(r.get("@type", [])),
            "descripcion": r.get("description", ""),
            "detalle": r.get("detailedDescription", {}).get("articleBody", ""),
            "url": r.get("detailedDescription", {}).get("url", r.get("url", "")),
            "puntaje": e.get("resultScore", 0), "id": r.get("@id", ""),
        })
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- Google Search (scraping; frágil)

def _google_html(consulta: str, dominio: str = "google.com", inicio: int = 0) -> str:
    q = urllib.parse.urlencode({"q": consulta, "hl": "es", "num": 10, "start": inicio})
    return _get(f"https://www.{dominio}/search?{q}").text


def paginas_indexadas(urls: list[str], dominio: str = "google.com") -> pd.DataFrame:
    """Cantidad aproximada de páginas indexadas según `site:` (Google puede bloquear el scraping)."""
    filas = []
    for u in urls:
        try:
            html = _google_html(f"site:{u}", dominio)
            m = re.search(r"([\d.,]+)\s+resultados", html) or re.search(r"About\s+([\d.,]+)\s+results", html)
            n = int(re.sub(r"[.,]", "", m.group(1))) if m else 0
            filas.append({"url": u, "paginas_indexadas": n})
        except Exception as e:  # noqa: BLE001
            filas.append({"url": u, "paginas_indexadas": None, "error": str(e)})
    return pd.DataFrame(filas)


def serps(consulta: str, paginas: int = 1, dominio: str = "google.com") -> pd.DataFrame:
    """Resultados orgánicos de Google (título, enlace, snippet). Google puede bloquear o cambiar el HTML."""
    filas = []
    for p in range(paginas):
        soup = BeautifulSoup(_google_html(consulta, dominio, p * 10), "lxml")
        for bloque in soup.select("div.g, div[data-sokoban-container]"):
            a = bloque.find("a", href=True)
            h3 = bloque.find("h3")
            if not a or not h3:
                continue
            snippet = bloque.select_one("div[data-sncf], div.VwiC3b, span.aCOpRe")
            filas.append({"consulta": consulta, "posicion": len(filas) + 1, "titulo": h3.get_text(strip=True),
                          "enlace": a["href"], "snippet": snippet.get_text(" ", strip=True) if snippet else ""})
    return pd.DataFrame(filas, columns=["consulta", "posicion", "titulo", "enlace", "snippet"])


# ---------------------------------------------------------------- Google Search Console

def _servicio_gsc(ruta_clave: str):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    cred = service_account.Credentials.from_service_account_file(
        ruta_clave, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    return build("searchconsole", "v1", credentials=cred, cache_discovery=False)


def consultar_gsc(ruta_clave: str, sitio: str, carga: dict, todo: bool = False) -> pd.DataFrame:
    """Consulta la API de Search Console. `carga` sigue el formato de la API (startDate, endDate, dimensions…)."""
    servicio = _servicio_gsc(ruta_clave)
    carga = dict(carga)
    carga.setdefault("rowLimit", 25000)
    carga.setdefault("startRow", 0)
    filas = []
    while True:
        resp = servicio.searchanalytics().query(siteUrl=sitio, body=carga).execute()
        datos = resp.get("rows", [])
        for f in datos:
            fila = dict(zip(carga.get("dimensions", []), f.get("keys", [])))
            fila.update(clics=f.get("clicks"), impresiones=f.get("impressions"), ctr=f.get("ctr"), posicion=f.get("position"))
            filas.append(fila)
        if not todo or len(datos) < carga["rowLimit"]:
            break
        carga["startRow"] += carga["rowLimit"]
    return pd.DataFrame(filas)


def comparar_gsc(ruta_clave: str, sitio: str, carga_antes: dict, carga_despues: dict, todo: bool = False) -> pd.DataFrame:
    dims = carga_antes.get("dimensions", [])
    a = consultar_gsc(ruta_clave, sitio, carga_antes, todo)
    d = consultar_gsc(ruta_clave, sitio, carga_despues, todo)
    m = a.merge(d, on=dims, how="outer", suffixes=("_antes", "_despues")).fillna(0)
    for c in ("clics", "impresiones", "ctr", "posicion"):
        m[f"{c}_diff"] = m[f"{c}_despues"] - m[f"{c}_antes"]
    return m


def clasificar_abcd(df: pd.DataFrame, metrica: str = "clics") -> pd.DataFrame:
    """Clase ABCD por contribución acumulada a los clics (D = sin clics)."""
    d = df.sort_values(metrica, ascending=False).copy()
    total = d[metrica].sum() or 1
    d["acumulado_pct"] = d[metrica].cumsum() / total * 100
    d["participacion_pct"] = d[metrica] / total * 100

    def clase(p):
        return "A" if p <= 80 else "B" if p <= 90 else "C" if p < 100 else "D"

    d["clase"] = d["acumulado_pct"].apply(clase)
    d.loc[(d["clase"] == "D") & (d[metrica] > 0), "clase"] = "C"
    d["rango"] = d["acumulado_pct"].rank(method="first").astype(int)
    return d.round(2)


def resumen_abcd(df: pd.DataFrame, dimension: str = "page") -> pd.DataFrame:
    s = df.groupby("clase").agg(paginas=(dimension, "nunique"), impresiones=("impresiones", "sum"), clics=("clics", "sum"),
                                ctr_medio=("ctr", "mean"), posicion_media=("posicion", "mean")).reset_index()
    for c in ("paginas", "clics", "impresiones"):
        s[f"{c}_pct"] = (s[c] / s[c].sum() * 100).round(1)
    return s.round(2)
