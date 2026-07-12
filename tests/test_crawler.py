import httpx
import pytest

from spidermapp.core import crawler as crawler_mod
from spidermapp.core import render_check, security
from spidermapp.core.models import CrawlConfig, TlsInfo

PAGE_HOME = """
<html><head><title>Inicio del sitio de prueba</title>
<meta name="description" content="Descripción de la página de inicio con longitud suficiente para el check."></head>
<body><h1>Bienvenido</h1>
<a href="/about">Acerca</a>
<a href="/contact">Contacto</a>
</body></html>
"""

PAGE_ABOUT = """
<html><head><title>Página Acerca de nosotros y el equipo</title>
<meta name="description" content="Descripción de la página about con longitud suficiente para pasar el check."></head>
<body><h1>Acerca</h1>
<a href="/">Inicio</a>
<a href="/missing">Roto</a>
</body></html>
"""

PAGE_CONTACT = """
<html><head><title>Contáctanos por aquí para más información</title>
<meta name="description" content="Descripción de la página de contacto con longitud suficiente para el check."></head>
<body><h1>Contacto</h1></body></html>
"""


def _handler(request: httpx.Request) -> httpx.Response:
    url = request.url
    if url.scheme == "http" and url.host == "example.test" and url.path == "/":
        return httpx.Response(301, headers={"Location": "https://example.test/"})
    if url.host != "example.test":
        return httpx.Response(404)

    if url.path == "/robots.txt":
        return httpx.Response(404)
    if url.path == "/sitemap.xml":
        return httpx.Response(404)
    if url.path == "/":
        return httpx.Response(200, content=PAGE_HOME, headers={"content-type": "text/html"})
    if url.path == "/about":
        return httpx.Response(200, content=PAGE_ABOUT, headers={"content-type": "text/html"})
    if url.path == "/contact":
        return httpx.Response(200, content=PAGE_CONTACT, headers={"content-type": "text/html"})
    return httpx.Response(404, content="<html><body>not found</body></html>", headers={"content-type": "text/html"})


@pytest.fixture(autouse=True)
def _no_real_tls(monkeypatch):
    monkeypatch.setattr(security, "get_tls_info", lambda host, **kwargs: TlsInfo(valid=True, days_until_expiry=200))


@pytest.fixture(autouse=True)
def _mock_transport(monkeypatch):
    transport = httpx.MockTransport(_handler)
    original_client = httpx.AsyncClient

    def patched_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(crawler_mod.httpx, "AsyncClient", patched_client)


async def test_crawl_discovers_all_internal_pages():
    config = CrawlConfig(seed_url="https://example.test/", max_pages=50, max_depth=5, concurrency=4)
    result = await crawler_mod.crawl(config)

    urls = {p.url for p in result.pages}
    assert "https://example.test/" in urls
    assert "https://example.test/about" in urls
    assert "https://example.test/contact" in urls
    assert "https://example.test/missing" in urls


async def test_crawl_flags_404_page():
    config = CrawlConfig(seed_url="https://example.test/", max_pages=50)
    result = await crawler_mod.crawl(config)
    missing = next(p for p in result.pages if p.url == "https://example.test/missing")
    assert missing.status_code == 404
    assert any(i.code == "error_404" for i in missing.issues)


async def test_crawl_respects_max_pages():
    config = CrawlConfig(seed_url="https://example.test/", max_pages=1)
    result = await crawler_mod.crawl(config)
    assert len(result.pages) == 1
    assert result.stopped_early


async def test_crawl_healthy_pages_are_indexable():
    config = CrawlConfig(seed_url="https://example.test/", max_pages=50)
    result = await crawler_mod.crawl(config)
    home = next(p for p in result.pages if p.url == "https://example.test/")
    assert home.status_code == 200
    assert home.is_indexable
    assert home.title == "Inicio del sitio de prueba"


async def test_crawl_site_issues_include_missing_robots_and_sitemap():
    config = CrawlConfig(seed_url="https://example.test/", max_pages=50)
    result = await crawler_mod.crawl(config)
    codes = {i.code for i in result.site_issues}
    assert "robots_missing" in codes
    assert "sitemap_empty" in codes


async def test_crawl_tracks_inlinks():
    config = CrawlConfig(seed_url="https://example.test/", max_pages=50)
    result = await crawler_mod.crawl(config)
    about = next(p for p in result.pages if p.url == "https://example.test/about")
    assert "https://example.test/" in about.inlinks


async def test_crawl_with_render_js_discovers_links_only_in_rendered_dom(monkeypatch):
    """Regression test for SPA sites (e.g. Angular/React shells) whose raw
    HTML has no <a href> at all: with render_js on, the crawler must follow
    links found in the rendered DOM, not just the raw HTML."""

    async def fake_start_browser(self):
        self._browser = object()

    async def fake_stop_browser(self):
        self._browser = None

    async def fake_render_with_browser(browser, url, viewport, user_agent=None, timeout_ms=15000):
        if url == "https://example.test/":
            html = (
                "<html><head><title>Inicio del sitio de prueba</title>"
                '<meta name="description" content="Descripción de la página de inicio con longitud suficiente para el check."></head>'
                '<body><h1>Bienvenido</h1><a href="/rendered-only">Solo visible tras ejecutar JS</a></body></html>'
            )
        else:
            html = "<html><head><title>Página renderizada</title></head><body><h1>Renderizada</h1></body></html>"
        return render_check.RenderedPage(html=html, lcp_ms=100, cls=0.0, fcp_ms=80)

    monkeypatch.setattr(crawler_mod.Crawler, "_start_browser", fake_start_browser)
    monkeypatch.setattr(crawler_mod.Crawler, "_stop_browser", fake_stop_browser)
    monkeypatch.setattr(crawler_mod.render_check, "render_with_browser", fake_render_with_browser)

    config = CrawlConfig(seed_url="https://example.test/", max_pages=50, render_js=True)
    result = await crawler_mod.crawl(config)

    urls = {p.url for p in result.pages}
    assert "https://example.test/rendered-only" in urls
    assert "https://example.test/about" in urls
