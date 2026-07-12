from __future__ import annotations

from collections import defaultdict

from spidermapp.core.models import Issue, IssueCategory, IssueSeverity


def _group_duplicates(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
    """pairs: list of (url, key). Returns {key: [urls]} only for keys shared by >1 url,
    ignoring empty keys."""
    groups: dict[str, list[str]] = defaultdict(list)
    for url, key in pairs:
        if key:
            groups[key].append(url)
    return {key: urls for key, urls in groups.items() if len(urls) > 1}


def find_duplicate_content(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
    """pairs: list of (url, content_hash)."""
    return _group_duplicates(pairs)


def find_duplicate_titles(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
    """pairs: list of (url, title)."""
    return _group_duplicates(pairs)


def find_duplicate_meta_descriptions(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
    """pairs: list of (url, meta_description)."""
    return _group_duplicates(pairs)


def issues_for_url(
    url: str,
    duplicate_content_groups: dict[str, list[str]],
    duplicate_title_groups: dict[str, list[str]],
    duplicate_meta_groups: dict[str, list[str]],
) -> list[Issue]:
    issues: list[Issue] = []

    for urls in duplicate_content_groups.values():
        if url in urls:
            others = len(urls) - 1
            issues.append(
                Issue(
                    IssueCategory.DUPLICATES,
                    IssueSeverity.CRITICAL,
                    "duplicate_content",
                    f"Contenido duplicado con otras {others} URL(s).",
                )
            )
            break

    for urls in duplicate_title_groups.values():
        if url in urls:
            others = len(urls) - 1
            issues.append(
                Issue(
                    IssueCategory.DUPLICATES,
                    IssueSeverity.WARNING,
                    "duplicate_title",
                    f"Title duplicado con otras {others} URL(s).",
                )
            )
            break

    for urls in duplicate_meta_groups.values():
        if url in urls:
            others = len(urls) - 1
            issues.append(
                Issue(
                    IssueCategory.DUPLICATES,
                    IssueSeverity.INFO,
                    "duplicate_meta_description",
                    f"Meta description duplicada con otras {others} URL(s).",
                )
            )
            break

    return issues
