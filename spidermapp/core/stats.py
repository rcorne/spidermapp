from __future__ import annotations

from dataclasses import dataclass

from spidermapp.core.models import IssueCategory, IssueSeverity, PageResult

SEVERITY_WEIGHT = {IssueSeverity.CRITICAL: 10, IssueSeverity.WARNING: 3, IssueSeverity.INFO: 1}
PRIORITY_URL_MULTIPLIER = 1.6


@dataclass
class CategoryBreakdown:
    category: IssueCategory
    critical: int = 0
    warning: int = 0
    info: int = 0

    @property
    def total(self) -> int:
        return self.critical + self.warning + self.info


@dataclass
class CrawlBudget:
    total_pages: int = 0
    ok_pages: int = 0
    error_pages: int = 0
    blocked_by_robots: int = 0
    duplicate_pages: int = 0
    orphan_pages: int = 0


def health_score(pages: list[PageResult], priority_urls: set[str] | None = None) -> int:
    """0-100, starting from 100 and subtracting a severity-weighted penalty per
    issue (heavier if the affected URL is one the user marked as priority),
    normalized by page count so larger sites aren't unfairly punished."""
    priority_urls = priority_urls or set()
    crawled = [p for p in pages if p.status_code is not None]
    if not crawled:
        return 100

    penalty = 0.0
    for page in crawled:
        multiplier = PRIORITY_URL_MULTIPLIER if (page.url in priority_urls or page.final_url in priority_urls) else 1.0
        for issue in page.issues:
            penalty += SEVERITY_WEIGHT[issue.severity] * multiplier

    normalized = penalty / len(crawled)
    score = 100 - normalized * 6
    return max(0, min(100, round(score)))


def category_breakdown(pages: list[PageResult]) -> list[CategoryBreakdown]:
    buckets = {category: CategoryBreakdown(category) for category in IssueCategory}
    for page in pages:
        for issue in page.issues:
            bucket = buckets[issue.category]
            if issue.severity == IssueSeverity.CRITICAL:
                bucket.critical += 1
            elif issue.severity == IssueSeverity.WARNING:
                bucket.warning += 1
            else:
                bucket.info += 1
    non_empty = [b for b in buckets.values() if b.total > 0]
    non_empty.sort(key=lambda b: b.total, reverse=True)
    return non_empty


def top_offenders(pages: list[PageResult], limit: int = 5) -> list[PageResult]:
    scored = [
        (sum(SEVERITY_WEIGHT[issue.severity] for issue in page.issues), page)
        for page in pages
        if page.issues
    ]
    scored.sort(key=lambda t: t[0], reverse=True)
    return [page for _, page in scored[:limit]]


def compute_crawl_budget(pages: list[PageResult]) -> CrawlBudget:
    budget = CrawlBudget(total_pages=len(pages))
    for page in pages:
        if any(issue.code == "blocked_by_robots" for issue in page.issues):
            budget.blocked_by_robots += 1
        elif page.status_code is None or page.status_code >= 400:
            budget.error_pages += 1
        else:
            budget.ok_pages += 1

        if any(issue.code == "duplicate_content" for issue in page.issues):
            budget.duplicate_pages += 1
        if page.is_orphan:
            budget.orphan_pages += 1
    return budget
