from __future__ import annotations

import re

from spidermapp.core.models import Issue, IssueCategory, IssueSeverity

_NOT_FOUND_PATTERNS = [
    r"p[aá]gina no encontrada",
    r"no se encontr[oó]",
    r"no existe esta p[aá]gina",
    r"contenido no disponible",
    r"page not found",
    r"not found",
    r"error 404",
    r"404 error",
    r"we can.?t find",
]
_NOT_FOUND_RE = re.compile("|".join(_NOT_FOUND_PATTERNS), re.IGNORECASE)

THIN_SOFT_404_WORD_THRESHOLD = 60


def detect_soft_404(status_code: int, title: str, visible_text_sample: str, word_count: int) -> bool:
    """Heuristic: a 200 response whose title/content looks like a not-found page,
    especially when combined with very little content."""
    if status_code != 200:
        return False

    haystack = f"{title} {visible_text_sample[:2000]}"
    looks_like_not_found = bool(_NOT_FOUND_RE.search(haystack))
    if not looks_like_not_found:
        return False

    return word_count <= THIN_SOFT_404_WORD_THRESHOLD or bool(_NOT_FOUND_RE.search(title))


def check_soft_404(is_soft_404: bool) -> list[Issue]:
    if is_soft_404:
        return [
            Issue(
                IssueCategory.RESPONSE_CODES,
                IssueSeverity.CRITICAL,
                "soft_404",
                "La página devuelve 200 pero su contenido indica que es una página de error (soft 404).",
            )
        ]
    return []
