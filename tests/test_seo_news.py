from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx

from spidermapp.core import seo_news

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://www.google.com/rss">
<channel>
<title>Google News</title>
<item>
  <title>Nuevo algoritmo de Google afecta el posicionamiento web - El Diario</title>
  <link>https://news.google.com/articles/abc123</link>
  <pubDate>Wed, 16 Jul 2025 10:00:00 GMT</pubDate>
  <source url="https://eldiario.com">El Diario</source>
</item>
<item>
  <title>Cómo los LLM están cambiando el SEO - TechCrunch</title>
  <link>https://news.google.com/articles/def456</link>
  <source url="https://techcrunch.com">TechCrunch</source>
</item>
<item>
  <title>Las mejores películas de Roh Yoon-seo</title>
  <link>https://news.google.com/articles/ghi789</link>
</item>
</channel>
</rss>"""


def test_is_relevant_matches_multiword_terms_case_insensitively():
    assert seo_news._is_relevant("nuevo algoritmo de Google llega a los buscadores")
    assert seo_news._is_relevant("La IA generativa transforma el marketing")


def test_is_relevant_matches_uppercase_acronyms():
    assert seo_news._is_relevant("Guía de SEO para 2026")
    assert seo_news._is_relevant("Cómo usar LLM en tu empresa")


def test_is_relevant_rejects_lowercase_acronym_inside_a_name():
    # "Yoon-seo" contains "seo" as a hyphen-bounded substring, which a naive
    # word-boundary regex would treat as a standalone word — this is exactly
    # the false positive the case-sensitive acronym check exists to avoid.
    assert not seo_news._is_relevant("Las mejores películas de Roh Yoon-seo")


def test_is_relevant_rejects_unrelated_title():
    assert not seo_news._is_relevant("El clima de mañana en Bogotá")


def test_parse_rss_extracts_relevant_items_only():
    items = seo_news._parse_rss(SAMPLE_RSS, limit=10)
    assert len(items) == 2
    assert items[0].title == "Nuevo algoritmo de Google afecta el posicionamiento web - El Diario"
    assert items[0].source == "El Diario"
    assert items[0].source_domain == "eldiario.com"
    assert items[0].published_at == "Wed, 16 Jul 2025 10:00:00 GMT"
    assert items[1].source == "TechCrunch"
    assert items[1].source_domain == "techcrunch.com"


def test_parse_rss_respects_limit():
    items = seo_news._parse_rss(SAMPLE_RSS, limit=1)
    assert len(items) == 1


def test_parse_rss_handles_malformed_xml():
    assert seo_news._parse_rss("not xml at all <<<", limit=10) == []


def test_parse_rss_skips_items_missing_title_or_link():
    xml = """<rss><channel>
    <item><title>Guía de SEO</title></item>
    <item><link>https://example.com</link></item>
    </channel></rss>"""
    assert seo_news._parse_rss(xml, limit=10) == []


def test_fetch_seo_llm_news_parses_response(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "SEO" in request.url.params.get("q", "")
        return httpx.Response(200, content=SAMPLE_RSS, headers={"content-type": "application/xml"})

    def fake_get(url, params=None, headers=None, timeout=None, follow_redirects=False):
        return httpx.Client(transport=httpx.MockTransport(handler)).get(url, params=params)

    monkeypatch.setattr(seo_news.httpx, "get", fake_get)
    items = seo_news.fetch_seo_llm_news(limit=2)
    assert len(items) == 2
    assert items[0].source == "El Diario"


def test_favicon_url_includes_domain_and_size():
    url = seo_news.favicon_url("techcrunch.com", size=32)
    assert "domain=techcrunch.com" in url
    assert "sz=32" in url


def test_fetch_favicon_returns_none_for_empty_domain():
    assert seo_news.fetch_favicon("") is None


def test_fetch_favicon_returns_bytes_on_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"\x89PNG\r\n", headers={"content-type": "image/png"})

    def fake_get(url, timeout=None, follow_redirects=False):
        return httpx.Client(transport=httpx.MockTransport(handler)).get(url)

    monkeypatch.setattr(seo_news.httpx, "get", fake_get)
    data = seo_news.fetch_favicon("techcrunch.com")
    assert data == b"\x89PNG\r\n"


def test_fetch_favicon_returns_none_on_request_error(monkeypatch):
    def fake_get(url, timeout=None, follow_redirects=False):
        raise httpx.RequestError("boom")

    monkeypatch.setattr(seo_news.httpx, "get", fake_get)
    assert seo_news.fetch_favicon("techcrunch.com") is None


def test_relative_time_empty_string_for_missing_pubdate():
    assert seo_news.relative_time("") == ""


def test_relative_time_minutes_ago():
    when = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert seo_news.relative_time(format_datetime(when)) == "hace 5 min"


def test_relative_time_hours_ago():
    when = datetime.now(timezone.utc) - timedelta(hours=3)
    assert seo_news.relative_time(format_datetime(when)) == "hace 3 horas"


def test_relative_time_days_ago():
    when = datetime.now(timezone.utc) - timedelta(days=2)
    assert seo_news.relative_time(format_datetime(when)) == "hace 2 días"


def test_relative_time_handles_garbage_input():
    assert seo_news.relative_time("not a date") == ""
