from __future__ import annotations

from spidermapp.core import fetch_errors, html_analysis, redirects, render_check, security, url_utils
from spidermapp.core.models import Issue, IssueCategory, IssueSeverity, PageResult
from spidermapp.core.soft_404 import check_soft_404


def response_code_issues(status_code: int | None, error: str, error_type: str = "") -> list[Issue]:
    if status_code is None:
        # One code per failure category, so the recommendation can name the
        # actual fix instead of "revisa la conexión".
        code = error_type or fetch_errors.CONNECTION_ERROR
        detail = f" ({error})" if error else ""
        return [
            Issue(
                IssueCategory.RESPONSE_CODES,
                IssueSeverity.CRITICAL,
                code,
                f"{fetch_errors.error_label(code)}{detail}.",
            )
        ]
    if status_code == 404:
        return [Issue(IssueCategory.RESPONSE_CODES, IssueSeverity.CRITICAL, "error_404", "La página devuelve 404.")]
    if 400 <= status_code < 500:
        return [
            Issue(
                IssueCategory.RESPONSE_CODES,
                IssueSeverity.CRITICAL,
                "error_4xx",
                f"La página devuelve un error del cliente ({status_code}).",
            )
        ]
    if status_code >= 500:
        return [
            Issue(
                IssueCategory.RESPONSE_CODES,
                IssueSeverity.CRITICAL,
                "error_5xx",
                f"La página devuelve un error del servidor ({status_code}).",
            )
        ]
    return []


def broken_image_issues(broken_images: list[str]) -> list[Issue]:
    if not broken_images:
        return []
    sample = ", ".join(broken_images[:3])
    more = f" (y {len(broken_images) - 3} más)" if len(broken_images) > 3 else ""
    return [
        Issue(
            IssueCategory.LINKS,
            IssueSeverity.WARNING,
            "broken_image",
            f"{len(broken_images)} imagen(es) no cargan: {sample}{more}.",
        )
    ]


def priority_url_indexation_issue(page: PageResult, priority_urls: set[str]) -> list[Issue]:
    if page.url not in priority_urls and page.final_url not in priority_urls:
        return []
    if not page.is_indexable:
        return [
            Issue(
                IssueCategory.DIRECTIVES,
                IssueSeverity.CRITICAL,
                "priority_url_not_indexable",
                "Esta URL fue marcada como importante pero no es indexable "
                "(noindex, canonical hacia otra URL, o no responde 200).",
            )
        ]
    return []


def collect_page_issues(page: PageResult, priority_urls: set[str] | None = None) -> list[Issue]:
    """Run every per-page check against an already-populated PageResult and
    return the combined list of issues. Site-wide checks (robots.txt,
    sitemap.xml, cross-page duplicates, URL consistency) are computed
    separately by the crawler once the full crawl is done."""
    priority_urls = priority_urls or set()
    found: list[Issue] = []

    found.extend(response_code_issues(page.status_code, page.error, page.error_type))
    found.extend(url_utils.check_url_conventions(page.url))
    found.extend(broken_image_issues(page.broken_images))

    if page.status_code == 200:
        found.extend(html_analysis.check_title(page.title))
        found.extend(html_analysis.check_meta_description(page.meta_description))
        found.extend(html_analysis.check_h1(page.h1))
        found.extend(html_analysis.check_h2(page.h2))
        found.extend(html_analysis.check_directives(page.meta_robots, page.x_robots_tag))
        found.extend(html_analysis.check_canonical(page.canonical, page.url, page.final_url, page.url in priority_urls))
        found.extend(html_analysis.check_thin_content(page.word_count))
        found.extend(html_analysis.check_images_alt(page.images_without_alt))
        found.extend(html_analysis.check_empty_anchors(page.empty_anchors))

    found.extend(check_soft_404(page.is_soft_404))

    if page.redirect_chain or page.status_code == 200:
        found.extend(redirects.check_redirect_chain(page.redirect_chain, html_of_final=page.raw_html))

    found.extend(security.check_tls_validity(page.tls))
    found.extend(render_check.check_rendering(page.render))
    found.extend(priority_url_indexation_issue(page, priority_urls))

    return found
