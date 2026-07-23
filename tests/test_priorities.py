import time

from spidermapp.core import history, priorities
from spidermapp.core.models import CrawlResult, IssueCategory, IssueSeverity, PageResult


def _result(seed_url: str, timestamp: float) -> CrawlResult:
    result = CrawlResult(seed_url=seed_url, started_at=timestamp, finished_at=timestamp)
    page = PageResult(url=seed_url, status_code=404)
    page.add_issue(IssueCategory.RESPONSE_CODES, IssueSeverity.CRITICAL, "error_404", "404")
    result.pages.append(page)
    return result


def test_latest_full_snapshot_per_site_dedupes_to_most_recent(tmp_path):
    # save_crawl always stamps with the real wall-clock time (it ignores
    # CrawlResult.started_at/finished_at), so what's under test here is
    # dedup — one entry per domain — not a specific timestamp value.
    history.save_crawl(_result("https://ejemplo.com/", timestamp=100.0), history_dir=tmp_path)
    history.save_crawl(_result("https://ejemplo.com/", timestamp=200.0), history_dir=tmp_path)

    entries = priorities.latest_full_snapshot_per_site(history_dir=tmp_path)
    assert len(entries) == 1
    assert entries[0]["domain"] == "ejemplo.com"


def test_latest_full_snapshot_per_site_keeps_separate_domains(tmp_path):
    history.save_crawl(_result("https://a.com/", timestamp=100.0), history_dir=tmp_path)
    history.save_crawl(_result("https://b.com/", timestamp=100.0), history_dir=tmp_path)

    entries = priorities.latest_full_snapshot_per_site(history_dir=tmp_path)
    domains = {e["domain"] for e in entries}
    assert domains == {"a.com", "b.com"}


def test_gather_today_priorities_tags_each_finding_with_its_site(tmp_path):
    history.save_crawl(_result("https://ejemplo.com/", timestamp=time.time()), history_dir=tmp_path)
    result = priorities.gather_today_priorities(history_dir=tmp_path)
    assert len(result) == 1
    assert result[0].site == "ejemplo.com"
    assert result[0].code == "error_404"
    assert result[0].affected_pages == 1


def test_gather_today_priorities_sorts_critical_before_warning():
    # Build priorities directly rather than through real crawls, to isolate
    # the sort behavior from the opportunity-finding logic.
    crit = priorities.Priority("a.com", "Crítico", "", "", "critical", 1, "x", None)
    warn = priorities.Priority("b.com", "Advertencia", "", "", "warning", 100, "y", None)
    ranked = sorted([warn, crit], key=lambda p: (priorities._SEVERITY_ORDER.get(p.severity, 3), -p.affected_pages))
    assert ranked[0] is crit


def test_gather_today_priorities_sorts_by_affected_pages_within_same_severity():
    small = priorities.Priority("a.com", "Menor", "", "", "warning", 2, "x", None)
    big = priorities.Priority("b.com", "Mayor", "", "", "warning", 50, "y", None)
    ranked = sorted([small, big], key=lambda p: (priorities._SEVERITY_ORDER.get(p.severity, 3), -p.affected_pages))
    assert ranked[0] is big


def test_gather_today_priorities_empty_history_returns_empty_list(tmp_path):
    assert priorities.gather_today_priorities(history_dir=tmp_path) == []
