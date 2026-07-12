from __future__ import annotations

import difflib
from dataclasses import dataclass

from spidermapp.core.html_analysis import analyze_html
from spidermapp.core.models import Issue, IssueCategory, IssueSeverity, RenderInfo

DESKTOP_VIEWPORT = {"width": 1366, "height": 768}
MOBILE_VIEWPORT = {"width": 390, "height": 844}
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

TEXT_SIMILARITY_THRESHOLD = 0.85

_VITALS_INIT_SCRIPT = """
window.__spidermappVitals = { lcp: 0, cls: 0 };
try {
  new PerformanceObserver((list) => {
    const entries = list.getEntries();
    const last = entries[entries.length - 1];
    if (last) window.__spidermappVitals.lcp = last.renderTime || last.loadTime || 0;
  }).observe({ type: 'largest-contentful-paint', buffered: true });
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (!entry.hadRecentInput) window.__spidermappVitals.cls += entry.value;
    }
  }).observe({ type: 'layout-shift', buffered: true });
} catch (e) {}
"""


@dataclass
class RenderedPage:
    html: str = ""
    lcp_ms: float | None = None
    cls: float | None = None
    fcp_ms: float | None = None
    error: str = ""


def texts_match(a: str, b: str, threshold: float = TEXT_SIMILARITY_THRESHOLD) -> bool:
    if not a and not b:
        return True
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    return ratio >= threshold


async def render_with_browser(browser, url: str, viewport: dict, user_agent: str | None = None, timeout_ms: int = 15000) -> RenderedPage:
    """Render a URL with a Playwright Chromium browser instance and collect
    lab Core Web Vitals. `browser` is a playwright.async_api.Browser, owned
    and closed by the caller (the crawler) so it can be reused across pages."""
    context = None
    try:
        context = await browser.new_context(viewport=viewport, user_agent=user_agent)
        page = await context.new_page()
        await page.add_init_script(_VITALS_INIT_SCRIPT)
        await page.goto(url, timeout=timeout_ms, wait_until="networkidle")
        await page.wait_for_timeout(500)

        html = await page.content()
        vitals = await page.evaluate("() => window.__spidermappVitals")
        fcp = await page.evaluate(
            "() => performance.getEntriesByType('paint').find(e => e.name === 'first-contentful-paint')?.startTime || null"
        )
        return RenderedPage(
            html=html,
            lcp_ms=vitals.get("lcp") if vitals else None,
            cls=vitals.get("cls") if vitals else None,
            fcp_ms=fcp,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the user via RenderedPage.error
        return RenderedPage(error=str(exc))
    finally:
        if context is not None:
            await context.close()


def compare_raw_vs_rendered(
    raw_title: str,
    raw_description: str,
    raw_h1: list[str],
    rendered_html: str,
    page_url: str,
) -> RenderInfo:
    """Pure comparison: does the metadata visible in the raw HTML match what a
    browser actually renders (i.e. what a JS-executing crawler/bot would see)?"""
    rendered = analyze_html(rendered_html, page_url)
    return RenderInfo(
        rendered_html=rendered_html,
        raw_vs_rendered_title_match=(raw_title == rendered.title),
        raw_vs_rendered_desc_match=(raw_description == rendered.meta_description),
        raw_vs_rendered_h1_match=(raw_h1 == rendered.h1),
    )


def compare_mobile_desktop(desktop_text: str, mobile_text: str) -> bool:
    return texts_match(desktop_text, mobile_text)


def check_rendering(render: RenderInfo | None) -> list[Issue]:
    if render is None:
        return []
    issues: list[Issue] = []
    if render.error:
        issues.append(
            Issue(IssueCategory.RENDERING, IssueSeverity.WARNING, "render_failed", f"No se pudo renderizar la página: {render.error}")
        )
        return issues

    if not render.raw_vs_rendered_title_match:
        issues.append(
            Issue(
                IssueCategory.RENDERING,
                IssueSeverity.WARNING,
                "render_title_mismatch",
                "El title en el HTML crudo no coincide con el title renderizado (JS lo modifica).",
            )
        )
    if not render.raw_vs_rendered_desc_match:
        issues.append(
            Issue(
                IssueCategory.RENDERING,
                IssueSeverity.WARNING,
                "render_description_mismatch",
                "La meta description en el HTML crudo no coincide con la renderizada.",
            )
        )
    if not render.raw_vs_rendered_h1_match:
        issues.append(
            Issue(
                IssueCategory.RENDERING,
                IssueSeverity.WARNING,
                "render_h1_mismatch",
                "El H1 en el HTML crudo no coincide con el renderizado.",
            )
        )
    if not render.mobile_desktop_match:
        issues.append(
            Issue(
                IssueCategory.RENDERING,
                IssueSeverity.WARNING,
                "mobile_desktop_mismatch",
                "El contenido visible difiere significativamente entre mobile y desktop.",
            )
        )
    return issues
