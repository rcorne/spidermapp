from __future__ import annotations

import re

from spidermapp.core.models import Issue, IssueCategory, IssueSeverity

_META_REFRESH_RE = re.compile(
    r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]*content=["\']?\s*\d+\s*;\s*url=([^"\'>]+)',
    re.IGNORECASE,
)
_JS_REDIRECT_RE = re.compile(
    r"(window\.location(\.href)?\s*=|window\.location\.replace\s*\(|document\.location\s*=)",
    re.IGNORECASE,
)

PERMANENT_CODES = {301, 308}
TEMPORARY_CODES = {302, 303, 307}
MAX_HEALTHY_CHAIN_LENGTH = 2


def detect_meta_refresh(html: str) -> str:
    match = _META_REFRESH_RE.search(html)
    return match.group(1).strip() if match else ""


def detect_js_redirect(html: str) -> bool:
    return bool(_JS_REDIRECT_RE.search(html))


def check_redirect_chain(chain: list[tuple[str, int]], html_of_final: str = "") -> list[Issue]:
    """chain is a list of (url, status_code) hops, in order, excluding the final 2xx page."""
    issues: list[Issue] = []

    if chain:
        temporary_hops = [hop for hop in chain if hop[1] in TEMPORARY_CODES]
        if temporary_hops:
            issues.append(
                Issue(
                    IssueCategory.REDIRECTS,
                    IssueSeverity.WARNING,
                    "temporary_redirect_should_be_permanent",
                    f"{len(temporary_hops)} redirect(s) usan código temporal (302/303/307) para lo que "
                    "parece ser un movimiento permanente; considerar 301.",
                )
            )

        if len(chain) > MAX_HEALTHY_CHAIN_LENGTH:
            issues.append(
                Issue(
                    IssueCategory.REDIRECTS,
                    IssueSeverity.WARNING,
                    "redirect_chain_too_long",
                    f"Cadena de redirects de {len(chain)} saltos; debería resolverse en un solo salto.",
                )
            )

        urls_in_chain = [hop[0] for hop in chain]
        if len(urls_in_chain) != len(set(urls_in_chain)):
            issues.append(
                Issue(
                    IssueCategory.REDIRECTS,
                    IssueSeverity.CRITICAL,
                    "redirect_loop",
                    "Se detectó un bucle de redirects (la misma URL aparece más de una vez en la cadena).",
                )
            )

    if html_of_final:
        meta_target = detect_meta_refresh(html_of_final)
        if meta_target:
            issues.append(
                Issue(
                    IssueCategory.REDIRECTS,
                    IssueSeverity.WARNING,
                    "meta_refresh_redirect",
                    f"La página usa un redirect por meta-refresh hacia {meta_target} en vez de un 301 HTTP.",
                )
            )
        if detect_js_redirect(html_of_final):
            issues.append(
                Issue(
                    IssueCategory.REDIRECTS,
                    IssueSeverity.WARNING,
                    "js_redirect",
                    "La página parece redirigir mediante JavaScript en vez de un 301 HTTP.",
                )
            )

    return issues
