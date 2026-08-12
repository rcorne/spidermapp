from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from spidermapp.core.models import Issue, IssueCategory, IssueSeverity, LinkEdge
from spidermapp.core.url_utils import is_same_site, normalize_url

TITLE_MIN_LEN = 15
TITLE_MAX_LEN = 60
DESC_MIN_LEN = 50
DESC_MAX_LEN = 160
THIN_CONTENT_WORDS = 150


@dataclass
class HtmlAnalysis:
    title: str = ""
    meta_description: str = ""
    h1: list[str] = field(default_factory=list)
    h2: list[str] = field(default_factory=list)
    canonical: str = ""
    meta_robots: str = ""
    hreflang: list[tuple[str, str]] = field(default_factory=list)
    json_ld_types: list[str] = field(default_factory=list)
    word_count: int = 0
    outlinks: list[LinkEdge] = field(default_factory=list)
    content_hash: str = ""
    meta_keywords: str = ""
    images_without_alt: int = 0
    empty_anchors: int = 0
    visible_text: str = ""
    image_srcs: list[str] = field(default_factory=list)


def analyze_html(html: str, page_url: str) -> HtmlAnalysis:
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    meta_desc_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    meta_description = meta_desc_tag.get("content", "").strip() if meta_desc_tag else ""

    h1 = [el.get_text(strip=True) for el in soup.find_all("h1")]
    h2 = [el.get_text(strip=True) for el in soup.find_all("h2")]

    canonical_tag = soup.find("link", attrs={"rel": re.compile("^canonical$", re.I)})
    canonical = normalize_url(canonical_tag.get("href", "").strip(), base=page_url) if canonical_tag and canonical_tag.get("href") else ""

    meta_robots_tag = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    meta_robots = meta_robots_tag.get("content", "").strip() if meta_robots_tag else ""

    hreflang: list[tuple[str, str]] = []
    for link in soup.find_all("link", attrs={"rel": re.compile("^alternate$", re.I)}):
        lang = link.get("hreflang")
        href = link.get("href")
        if lang and href:
            hreflang.append((lang, normalize_url(href, base=page_url)))

    json_ld_types: list[str] = []
    for script in soup.find_all("script", attrs={"type": re.compile("^application/ld\\+json$", re.I)}):
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        json_ld_types.extend(_extract_ld_types(data))

    meta_kw_tag = soup.find("meta", attrs={"name": re.compile("^keywords$", re.I)})
    meta_keywords = meta_kw_tag.get("content", "").strip() if meta_kw_tag else ""

    images_without_alt = 0
    image_srcs: list[str] = []
    for img in soup.find_all("img"):
        if not (img.get("alt") or "").strip():
            images_without_alt += 1
        src = (img.get("src") or "").strip()
        # data: URIs are inline bytes — there's nothing to request, so
        # nothing that can 404.
        if src and not src.lower().startswith("data:"):
            resolved = urljoin(page_url, src)
            if resolved not in image_srcs:
                image_srcs.append(resolved)

    empty_anchors = 0
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        has_text = bool(a.get_text(strip=True)) or a.find("img") is not None
        if not href or not has_text:
            empty_anchors += 1

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    visible_text = soup.get_text(separator=" ", strip=True)
    word_count = len(visible_text.split())
    content_hash = hashlib.sha256(visible_text.encode("utf-8", errors="ignore")).hexdigest()

    outlinks = _extract_links(soup, page_url)

    return HtmlAnalysis(
        title=title,
        meta_description=meta_description,
        h1=h1,
        h2=h2,
        canonical=canonical,
        meta_robots=meta_robots,
        hreflang=hreflang,
        json_ld_types=json_ld_types,
        word_count=word_count,
        outlinks=outlinks,
        content_hash=content_hash,
        meta_keywords=meta_keywords,
        images_without_alt=images_without_alt,
        empty_anchors=empty_anchors,
        visible_text=visible_text,
        image_srcs=image_srcs,
    )


def _extract_ld_types(data) -> list[str]:
    types: list[str] = []
    items = data if isinstance(data, list) else [data]
    for item in items:
        if not isinstance(item, dict):
            continue
        t = item.get("@type")
        if isinstance(t, str):
            types.append(t)
        elif isinstance(t, list):
            types.extend(str(x) for x in t)
        if "@graph" in item and isinstance(item["@graph"], list):
            for sub in item["@graph"]:
                if isinstance(sub, dict) and isinstance(sub.get("@type"), str):
                    types.append(sub["@type"])
    return types


def _extract_links(soup: BeautifulSoup, page_url: str) -> list[LinkEdge]:
    links: list[LinkEdge] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        target = normalize_url(href, base=page_url)
        if urlparse(target).scheme not in ("http", "https"):
            continue
        rel = " ".join(a.get("rel", [])) if a.get("rel") else ""
        links.append(
            LinkEdge(
                source=page_url,
                target=target,
                anchor_text=a.get_text(strip=True),
                is_internal=is_same_site(page_url, target, include_subdomains=True),
                rel=rel,
            )
        )
    return links


def check_title(title: str) -> list[Issue]:
    issues: list[Issue] = []
    if not title:
        issues.append(Issue(IssueCategory.TITLES, IssueSeverity.CRITICAL, "title_missing", "Falta la etiqueta <title>."))
    elif len(title) < TITLE_MIN_LEN:
        issues.append(Issue(IssueCategory.TITLES, IssueSeverity.WARNING, "title_too_short", f"Title muy corto ({len(title)} caracteres)."))
    elif len(title) > TITLE_MAX_LEN:
        issues.append(Issue(IssueCategory.TITLES, IssueSeverity.WARNING, "title_too_long", f"Title muy largo ({len(title)} caracteres)."))
    return issues


def check_meta_description(description: str) -> list[Issue]:
    issues: list[Issue] = []
    if not description:
        issues.append(Issue(IssueCategory.META, IssueSeverity.WARNING, "meta_description_missing", "Falta la meta description."))
    elif len(description) < DESC_MIN_LEN:
        issues.append(Issue(IssueCategory.META, IssueSeverity.INFO, "meta_description_too_short", f"Meta description muy corta ({len(description)} caracteres)."))
    elif len(description) > DESC_MAX_LEN:
        issues.append(Issue(IssueCategory.META, IssueSeverity.INFO, "meta_description_too_long", f"Meta description muy larga ({len(description)} caracteres)."))
    return issues


def check_h1(h1_list: list[str]) -> list[Issue]:
    issues: list[Issue] = []
    if not h1_list:
        issues.append(Issue(IssueCategory.META, IssueSeverity.WARNING, "h1_missing", "Falta la etiqueta <h1>."))
    elif len(h1_list) > 1:
        issues.append(Issue(IssueCategory.META, IssueSeverity.INFO, "h1_multiple", f"Hay {len(h1_list)} etiquetas <h1> en la página."))
    return issues


def check_directives(meta_robots: str, x_robots_tag: str = "") -> list[Issue]:
    issues: list[Issue] = []
    combined = f"{meta_robots} {x_robots_tag}".lower()
    if "noindex" in combined:
        issues.append(Issue(IssueCategory.DIRECTIVES, IssueSeverity.CRITICAL, "noindex", "La página tiene la directiva noindex."))
    if "nofollow" in combined:
        issues.append(Issue(IssueCategory.DIRECTIVES, IssueSeverity.INFO, "nofollow_page", "La página tiene la directiva nofollow a nivel de página."))
    return issues


def check_canonical(canonical: str, page_url: str, final_url: str, is_priority_url: bool = False) -> list[Issue]:
    issues: list[Issue] = []
    if not canonical:
        return issues
    reference = final_url or page_url
    if canonical != reference and canonical != page_url:
        severity = IssueSeverity.CRITICAL if is_priority_url else IssueSeverity.WARNING
        issues.append(
            Issue(
                IssueCategory.CANONICALS,
                severity,
                "canonical_points_elsewhere",
                f"El canonical apunta a otra URL ({canonical}), lo que puede impedir la indexación de esta página.",
            )
        )
    return issues


def check_thin_content(word_count: int) -> list[Issue]:
    if word_count < THIN_CONTENT_WORDS:
        return [
            Issue(
                IssueCategory.META,
                IssueSeverity.INFO,
                "thin_content",
                f"Contenido posiblemente escaso ({word_count} palabras).",
            )
        ]
    return []


def check_h2(h2_list: list[str]) -> list[Issue]:
    if not h2_list:
        return [
            Issue(
                IssueCategory.META,
                IssueSeverity.INFO,
                "h2_missing",
                "La página no tiene ningún encabezado <h2>.",
            )
        ]
    return []


def check_images_alt(images_without_alt: int) -> list[Issue]:
    if images_without_alt > 0:
        return [
            Issue(
                IssueCategory.META,
                IssueSeverity.WARNING,
                "img_alt_missing",
                f"{images_without_alt} imagen(es) sin atributo alt.",
            )
        ]
    return []


def check_empty_anchors(empty_anchors: int) -> list[Issue]:
    if empty_anchors > 0:
        return [
            Issue(
                IssueCategory.LINKS,
                IssueSeverity.WARNING,
                "empty_anchors",
                f"{empty_anchors} etiqueta(s) <a> vacías (sin href o sin texto/imagen).",
            )
        ]
    return []


def check_sitemap_membership(in_sitemap: bool, sitemap_has_urls: bool, is_indexable: bool) -> list[Issue]:
    """Flag indexable pages that the sitemap doesn't declare (only meaningful
    when the site actually has a sitemap with URLs)."""
    if sitemap_has_urls and is_indexable and not in_sitemap:
        return [
            Issue(
                IssueCategory.SITEMAP_ROBOTS,
                IssueSeverity.INFO,
                "not_in_sitemap",
                "Página indexable que no aparece en el sitemap.xml.",
            )
        ]
    return []
