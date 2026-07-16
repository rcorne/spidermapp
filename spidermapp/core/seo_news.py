from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx

# Google News publishes a public, keyless RSS search feed — no API key
# needed, same "public signal" spirit as ai_visibility.py.
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"

DEFAULT_QUERY = (
    '"SEO" OR "posicionamiento web" OR "algoritmo de Google" OR "IA generativa" OR '
    '"búsqueda con IA" OR "LLM" OR "ChatGPT" OR "Google Search"'
)

# Google News' full-text search matches loosely (e.g. "SEO" hits the Korean
# actress name "Yoon-seo"), so results are filtered client-side. Unambiguous
# multi-word terms are matched case-insensitively; the bare 3-letter
# acronyms "SEO"/"LLM" are ambiguous as lowercase substrings of names, so
# those are only accepted written in caps, as real acronym usage almost
# always is.
RELEVANCE_TERMS = [
    "posicionamiento web", "algoritmo de google", "ia generativa",
    "busqueda con ia", "chatgpt", "google search", "motor de busqueda",
    "motores de busqueda", "inteligencia artificial", "buscador de google",
]
RELEVANCE_ACRONYMS = ["SEO", "LLM"]

_TIMEOUT = 10.0
_HEADERS = {"User-Agent": "Mozilla/5.0 (Spidermapp SEO/LLM news widget)"}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _is_relevant(title: str) -> bool:
    normalized = _normalize(title)
    if any(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized) for term in RELEVANCE_TERMS):
        return True
    return any(re.search(rf"\b{re.escape(acronym)}\b", title) for acronym in RELEVANCE_ACRONYMS)


@dataclass
class NewsItem:
    title: str
    link: str
    source: str = ""
    source_domain: str = ""
    published_at: str = ""  # raw RFC-822 pubDate, humanized for display by relative_time()


FAVICON_ENDPOINT = "https://www.google.com/s2/favicons"


def favicon_url(domain: str, size: int = 64) -> str:
    """Google's public favicon service — a legitimate, keyless way to give
    each news card a real image without scraping the article page (Google
    News' article links resolve to a JS-rendered redirect shell, not the
    publisher's HTML, so pulling a true article thumbnail isn't possible
    without a headless browser per item)."""
    return f"{FAVICON_ENDPOINT}?domain={domain}&sz={size}"


def fetch_favicon(domain: str, timeout: float = 5.0) -> bytes | None:
    if not domain:
        return None
    try:
        response = httpx.get(favicon_url(domain), timeout=timeout, follow_redirects=True)
        if response.status_code == 200 and response.content:
            return response.content
    except httpx.RequestError:
        pass
    return None


def relative_time(pubdate: str) -> str:
    """'hace 2 horas' style caption from an RSS pubDate string."""
    if not pubdate:
        return ""
    try:
        when = parsedate_to_datetime(pubdate)
    except (TypeError, ValueError):
        return ""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - when
    seconds = delta.total_seconds()
    if seconds < 0:
        return "hace un momento"
    if seconds < 3600:
        minutes = max(1, int(seconds // 60))
        return f"hace {minutes} min" if minutes > 1 else "hace 1 min"
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"hace {hours} horas" if hours > 1 else "hace 1 hora"
    days = int(seconds // 86400)
    return f"hace {days} días" if days > 1 else "hace 1 día"


def fetch_seo_llm_news(
    query: str = DEFAULT_QUERY,
    language: str = "es",
    country: str = "US",
    limit: int = 15,
    timeout: float = _TIMEOUT,
) -> list[NewsItem]:
    """Recent news about SEO and LLMs, straight from Google News' RSS search
    — no API key required. Network I/O; run off the UI thread."""
    response = httpx.get(
        GOOGLE_NEWS_RSS_URL,
        params={"q": query, "hl": language, "gl": country, "ceid": f"{country}:{language}"},
        headers=_HEADERS,
        timeout=timeout,
        follow_redirects=True,  # Google News redirects hl=es -> hl=es-419 etc.
    )
    response.raise_for_status()
    return _parse_rss(response.text, limit=limit)


def _parse_rss(xml_text: str, limit: int) -> list[NewsItem]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items: list[NewsItem] = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        if not _is_relevant(title):
            continue
        source_el = item.find("source")
        source = (source_el.text or "").strip() if source_el is not None and source_el.text else ""
        source_url = source_el.get("url", "") if source_el is not None else ""
        source_domain = urlparse(source_url).netloc if source_url else ""
        published_at = (item.findtext("pubDate") or "").strip()
        items.append(
            NewsItem(title=title, link=link, source=source, source_domain=source_domain, published_at=published_at)
        )
        if len(items) >= limit:
            break
    return items
