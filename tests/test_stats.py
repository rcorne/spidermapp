from spidermapp.core import stats
from spidermapp.core.models import Issue, IssueCategory, IssueSeverity, PageResult


def _page(url, status=200, issues=None, is_orphan=False):
    page = PageResult(url=url, status_code=status, is_orphan=is_orphan)
    for category, severity, code in issues or []:
        page.add_issue(category, severity, code, "msg")
    return page


def test_health_score_perfect_site_is_100():
    pages = [_page("https://x.com/a"), _page("https://x.com/b")]
    assert stats.health_score(pages) == 100


def test_health_score_drops_with_critical_issues():
    pages = [
        _page("https://x.com/a", issues=[(IssueCategory.RESPONSE_CODES, IssueSeverity.CRITICAL, "error_404")]),
        _page("https://x.com/b"),
    ]
    assert stats.health_score(pages) < 100


def test_health_score_weighs_priority_urls_more_heavily():
    issue = [(IssueCategory.CANONICALS, IssueSeverity.WARNING, "canonical_points_elsewhere")]
    pages_normal = [_page("https://x.com/a", issues=issue)]
    pages_priority = [_page("https://x.com/a", issues=issue)]
    score_normal = stats.health_score(pages_normal)
    score_priority = stats.health_score(pages_priority, priority_urls={"https://x.com/a"})
    assert score_priority < score_normal


def test_health_score_no_crawled_pages_is_100():
    assert stats.health_score([]) == 100


def test_category_breakdown_counts_by_severity():
    pages = [
        _page("https://x.com/a", issues=[(IssueCategory.TITLES, IssueSeverity.CRITICAL, "title_missing")]),
        _page("https://x.com/b", issues=[(IssueCategory.TITLES, IssueSeverity.WARNING, "title_too_long")]),
    ]
    breakdown = stats.category_breakdown(pages)
    titles = next(b for b in breakdown if b.category == IssueCategory.TITLES)
    assert titles.critical == 1
    assert titles.warning == 1
    assert titles.total == 2


def test_category_breakdown_excludes_empty_categories():
    pages = [_page("https://x.com/a")]
    assert stats.category_breakdown(pages) == []


def test_top_offenders_sorted_by_weighted_severity():
    pages = [
        _page("https://x.com/light", issues=[(IssueCategory.META, IssueSeverity.INFO, "thin_content")]),
        _page(
            "https://x.com/heavy",
            issues=[
                (IssueCategory.RESPONSE_CODES, IssueSeverity.CRITICAL, "error_404"),
                (IssueCategory.CANONICALS, IssueSeverity.CRITICAL, "canonical_points_elsewhere"),
            ],
        ),
    ]
    top = stats.top_offenders(pages, limit=2)
    assert top[0].url == "https://x.com/heavy"


def test_compute_crawl_budget_categorizes_pages():
    pages = [
        _page("https://x.com/ok"),
        _page("https://x.com/error", status=500),
        _page("https://x.com/dup", issues=[(IssueCategory.DUPLICATES, IssueSeverity.CRITICAL, "duplicate_content")]),
        _page("https://x.com/orphan", is_orphan=True),
    ]
    pages[2].add_issue(IssueCategory.SITEMAP_ROBOTS, IssueSeverity.INFO, "blocked_by_robots", "msg")
    budget = stats.compute_crawl_budget(pages)
    assert budget.total_pages == 4
    assert budget.error_pages == 1
    assert budget.blocked_by_robots == 1
    assert budget.orphan_pages == 1


def test_find_opportunities_groups_by_issue_code_not_by_page():
    pages = [
        _page("https://x.com/a", issues=[(IssueCategory.TITLES, IssueSeverity.CRITICAL, "title_missing")]),
        _page("https://x.com/b", issues=[(IssueCategory.TITLES, IssueSeverity.CRITICAL, "title_missing")]),
        _page("https://x.com/c", issues=[(IssueCategory.META, IssueSeverity.INFO, "thin_content")]),
    ]
    opportunities = stats.find_opportunities(pages)
    title_opp = next(o for o in opportunities if o.code == "title_missing")
    assert title_opp.affected_pages == 2
    thin_opp = next(o for o in opportunities if o.code == "thin_content")
    assert thin_opp.affected_pages == 1


def test_find_opportunities_counts_each_page_once_even_with_duplicate_issue():
    page = _page("https://x.com/a")
    page.add_issue(IssueCategory.TITLES, IssueSeverity.CRITICAL, "title_missing", "msg")
    page.add_issue(IssueCategory.TITLES, IssueSeverity.CRITICAL, "title_missing", "msg (duplicate)")
    opportunities = stats.find_opportunities([page])
    assert opportunities[0].affected_pages == 1


def test_find_opportunities_ranked_by_severity_weighted_reach():
    pages = [
        _page("https://x.com/a", issues=[(IssueCategory.META, IssueSeverity.INFO, "thin_content")]),
        _page("https://x.com/b", issues=[(IssueCategory.RESPONSE_CODES, IssueSeverity.CRITICAL, "error_404")]),
    ]
    opportunities = stats.find_opportunities(pages)
    assert opportunities[0].code == "error_404"


def test_find_opportunities_empty_when_no_issues():
    assert stats.find_opportunities([_page("https://x.com/a")]) == []


def test_summarize_site_infrastructure_healthy_site():
    infra = stats.summarize_site_infrastructure(["https://x.com/a", "https://x.com/b"], [])
    assert infra.robots_found
    assert infra.robots_allows_crawling
    assert infra.robots_declares_sitemap
    assert infra.sitemap_found
    assert infra.sitemap_url_count == 2
    assert infra.other_findings == []


def test_summarize_site_infrastructure_missing_robots_and_sitemap():
    site_issues = [
        Issue(IssueCategory.SITEMAP_ROBOTS, IssueSeverity.INFO, "robots_missing", "msg"),
        Issue(IssueCategory.SITEMAP_ROBOTS, IssueSeverity.WARNING, "sitemap_empty", "msg"),
    ]
    infra = stats.summarize_site_infrastructure([], site_issues)
    assert not infra.robots_found
    assert not infra.sitemap_found
    assert infra.sitemap_url_count == 0


def test_summarize_site_infrastructure_separates_other_findings():
    site_issues = [
        Issue(IssueCategory.SITEMAP_ROBOTS, IssueSeverity.INFO, "robots_missing", "msg"),
        Issue(IssueCategory.SECURITY, IssueSeverity.CRITICAL, "mixed_www", "msg"),
    ]
    infra = stats.summarize_site_infrastructure(["https://x.com/a"], site_issues)
    assert [i.code for i in infra.other_findings] == ["mixed_www"]
