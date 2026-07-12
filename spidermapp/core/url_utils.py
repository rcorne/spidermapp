from __future__ import annotations

import re
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

from spidermapp.core.models import Issue, IssueCategory, IssueSeverity

_ALLOWED_PATH_CHARS = re.compile(r"^[a-z0-9\-/._~%]*$")
_MULTI_SLASH = re.compile(r"//+")
_NUMERIC_OR_SPECIAL = re.compile(r"[0-9]|[^a-zA-Z0-9\-/._~%:]")


def normalize_url(url: str, base: str | None = None) -> str:
    """Resolve relative URLs against a base and strip the fragment."""
    resolved = urljoin(base, url) if base else url
    resolved, _frag = urldefrag(resolved)
    return resolved


def get_host(url: str) -> str:
    return urlparse(url).netloc.lower()


def get_path(url: str) -> str:
    return urlparse(url).path


def is_https(url: str) -> bool:
    return urlparse(url).scheme == "https"


def is_www(url: str) -> bool:
    return get_host(url).startswith("www.")


def strip_www(host: str) -> str:
    return host[4:] if host.lower().startswith("www.") else host


def registrable_domain(url: str) -> str:
    """Best-effort registrable domain without an external PSL dependency call at import time."""
    try:
        import tldextract

        ext = tldextract.extract(url)
        return ".".join(part for part in (ext.domain, ext.suffix) if part)
    except Exception:
        host = strip_www(get_host(url))
        return host


def is_same_site(url_a: str, url_b: str, include_subdomains: bool = False) -> bool:
    if include_subdomains:
        return registrable_domain(url_a) == registrable_domain(url_b)
    return strip_www(get_host(url_a)) == strip_www(get_host(url_b))


def has_trailing_slash(url: str) -> bool:
    path = get_path(url)
    return path != "" and path != "/" and path.endswith("/")


def swap_scheme(url: str, scheme: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(scheme=scheme))


def swap_www(url: str, want_www: bool) -> str:
    parsed = urlparse(url)
    host = parsed.netloc
    bare = strip_www(host)
    new_host = f"www.{bare}" if want_www else bare
    return urlunparse(parsed._replace(netloc=new_host))


def toggle_trailing_slash(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path
    if path.endswith("/") and path != "/":
        new_path = path[:-1]
    elif path == "":
        new_path = "/"
    else:
        new_path = path + "/"
    return urlunparse(parsed._replace(path=new_path))


def check_url_conventions(url: str) -> list[Issue]:
    """Flag URL-hygiene problems: uppercase, underscores, doubled slashes,
    digits/special characters, and inconsistent trailing slash."""
    issues: list[Issue] = []
    path = get_path(url)

    if path != path.lower():
        issues.append(
            Issue(
                IssueCategory.URL_CONVENTIONS,
                IssueSeverity.WARNING,
                "url_uppercase",
                "La URL contiene mayúsculas.",
            )
        )

    if "_" in path:
        issues.append(
            Issue(
                IssueCategory.URL_CONVENTIONS,
                IssueSeverity.WARNING,
                "url_underscore",
                "La URL contiene guion bajo (usar guiones medios).",
            )
        )

    if _MULTI_SLASH.search(path):
        issues.append(
            Issue(
                IssueCategory.URL_CONVENTIONS,
                IssueSeverity.WARNING,
                "url_multi_slash",
                "La URL contiene barras (/) duplicadas.",
            )
        )

    segments = [seg for seg in path.split("/") if seg]
    if any(_NUMERIC_OR_SPECIAL.search(seg) for seg in segments):
        issues.append(
            Issue(
                IssueCategory.URL_CONVENTIONS,
                IssueSeverity.INFO,
                "url_numeric_or_special",
                "La URL contiene números o caracteres especiales.",
            )
        )

    return issues


def check_site_wide_url_consistency(sample_urls: list[str]) -> list[Issue]:
    """Given a sample of crawled URLs, detect mixed www/non-www, mixed
    http/https, or mixed trailing-slash usage across the site."""
    issues: list[Issue] = []
    if not sample_urls:
        return issues

    hosts = {get_host(u) for u in sample_urls}
    www_variants = {h.startswith("www.") for h in hosts}
    if len(www_variants) > 1:
        issues.append(
            Issue(
                IssueCategory.SECURITY,
                IssueSeverity.CRITICAL,
                "mixed_www",
                "El sitio responde tanto en versión www como sin www sin redirigir a una sola.",
            )
        )

    schemes = {urlparse(u).scheme for u in sample_urls}
    if len(schemes) > 1:
        issues.append(
            Issue(
                IssueCategory.SECURITY,
                IssueSeverity.CRITICAL,
                "mixed_scheme",
                "El sitio responde tanto en HTTP como en HTTPS sin redirigir a una sola versión.",
            )
        )

    with_slash = 0
    without_slash = 0
    for u in sample_urls:
        path = get_path(u)
        if path in ("", "/"):
            continue
        if path.endswith("/"):
            with_slash += 1
        else:
            without_slash += 1
    if with_slash > 0 and without_slash > 0:
        issues.append(
            Issue(
                IssueCategory.URL_CONVENTIONS,
                IssueSeverity.WARNING,
                "mixed_trailing_slash",
                "El sitio mezcla URLs con y sin barra final sin una convención consistente.",
            )
        )

    return issues
