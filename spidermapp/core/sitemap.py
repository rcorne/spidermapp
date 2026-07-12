from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from spidermapp.core.models import Issue, IssueCategory, IssueSeverity
from spidermapp.core.url_utils import is_same_site

_SITEMAP_NS_CANDIDATES = (
    "{http://www.sitemaps.org/schemas/sitemap/0.9}",
    "",
)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


@dataclass
class ParsedSitemap:
    sitemap_url: str
    is_index: bool
    urls: list[str] = field(default_factory=list)
    child_sitemaps: list[str] = field(default_factory=list)
    parse_error: str = ""


def parse_sitemap_xml(content: str, sitemap_url: str) -> ParsedSitemap:
    """Pure parser for a single sitemap.xml document (urlset or sitemapindex)."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        return ParsedSitemap(sitemap_url=sitemap_url, is_index=False, parse_error=str(exc))

    root_tag = _local(root.tag)
    urls: list[str] = []
    child_sitemaps: list[str] = []

    if root_tag == "sitemapindex":
        for sitemap_el in root:
            if _local(sitemap_el.tag) != "sitemap":
                continue
            loc = _find_loc(sitemap_el)
            if loc:
                child_sitemaps.append(loc)
        return ParsedSitemap(sitemap_url=sitemap_url, is_index=True, child_sitemaps=child_sitemaps)

    if root_tag == "urlset":
        for url_el in root:
            if _local(url_el.tag) != "url":
                continue
            loc = _find_loc(url_el)
            if loc:
                urls.append(loc)
        return ParsedSitemap(sitemap_url=sitemap_url, is_index=False, urls=urls)

    return ParsedSitemap(
        sitemap_url=sitemap_url,
        is_index=False,
        parse_error=f"Elemento raíz inesperado: <{root_tag}>",
    )


def _find_loc(el: ET.Element) -> str:
    for child in el:
        if _local(child.tag) == "loc" and child.text:
            return child.text.strip()
    return ""


def validate_sitemap_urls(
    sitemap_urls: list[str],
    seed_url: str,
    status_by_url: dict[str, int] | None = None,
    crawled_urls: set[str] | None = None,
) -> list[Issue]:
    """Validate a flattened list of URLs collected from sitemap(s).

    status_by_url: known HTTP status codes for sitemap URLs (from the crawl), if available.
    crawled_urls: URLs discovered by crawling internal links, to flag sitemap/crawl mismatches.
    """
    issues: list[Issue] = []

    if not sitemap_urls:
        issues.append(
            Issue(
                IssueCategory.SITEMAP_ROBOTS,
                IssueSeverity.WARNING,
                "sitemap_empty",
                "El sitemap no contiene URLs.",
            )
        )
        return issues

    off_domain = [u for u in sitemap_urls if not is_same_site(u, seed_url, include_subdomains=True)]
    if off_domain:
        issues.append(
            Issue(
                IssueCategory.SITEMAP_ROBOTS,
                IssueSeverity.WARNING,
                "sitemap_off_domain_urls",
                f"El sitemap incluye {len(off_domain)} URL(s) de otro dominio.",
            )
        )

    if status_by_url:
        broken = [u for u in sitemap_urls if status_by_url.get(u, 200) >= 400]
        if broken:
            issues.append(
                Issue(
                    IssueCategory.SITEMAP_ROBOTS,
                    IssueSeverity.CRITICAL,
                    "sitemap_broken_urls",
                    f"El sitemap incluye {len(broken)} URL(s) que devuelven error 4xx/5xx.",
                )
            )

    if crawled_urls:
        missing_from_sitemap = crawled_urls - set(sitemap_urls)
        if missing_from_sitemap:
            issues.append(
                Issue(
                    IssueCategory.SITEMAP_ROBOTS,
                    IssueSeverity.INFO,
                    "sitemap_missing_crawled_urls",
                    f"{len(missing_from_sitemap)} URL(s) rastreadas no aparecen en el sitemap.",
                )
            )

    return issues
