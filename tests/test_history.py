from spidermapp.core import history
from spidermapp.core.models import CrawlResult, IssueCategory, IssueSeverity, PageResult


def _result(seed, pages_specs):
    result = CrawlResult(seed_url=seed)
    for url, status, codes in pages_specs:
        page = PageResult(url=url, status_code=status)
        for code in codes:
            page.add_issue(IssueCategory.TITLES, IssueSeverity.WARNING, code, "msg")
        result.pages.append(page)
    return result


def test_save_and_list_snapshots(tmp_path):
    result = _result("https://example.com/", [("https://example.com/a", 200, ["title_missing"])])
    path = history.save_crawl(result, history_dir=tmp_path)
    assert path.exists()
    snapshots = history.list_snapshots("https://example.com/", history_dir=tmp_path)
    assert snapshots == [path]


def test_load_snapshot_roundtrip(tmp_path):
    result = _result("https://example.com/", [("https://example.com/a", 200, ["title_missing"])])
    path = history.save_crawl(result, history_dir=tmp_path)
    snapshot = history.load_snapshot(path)
    assert snapshot.seed_url == "https://example.com/"
    assert snapshot.pages == {"https://example.com/a": ["title_missing"]}


def test_load_previous_snapshot_returns_none_when_empty(tmp_path):
    assert history.load_previous_snapshot("https://example.com/", history_dir=tmp_path) is None


def test_load_previous_snapshot_returns_most_recent(tmp_path):
    older = _result("https://example.com/", [("https://example.com/a", 200, [])])
    newer = _result("https://example.com/", [("https://example.com/b", 200, [])])
    history.save_crawl(older, history_dir=tmp_path)
    import time

    time.sleep(0.01)
    history.save_crawl(newer, history_dir=tmp_path)

    latest = history.load_previous_snapshot("https://example.com/", history_dir=tmp_path)
    assert "https://example.com/b" in latest.pages


def test_diff_crawls_detects_new_and_resolved_issues():
    previous = history._snapshot_from_result(
        _result(
            "https://example.com/",
            [
                ("https://example.com/a", 200, ["title_missing"]),
                ("https://example.com/b", 200, []),
            ],
        )
    )
    current = _result(
        "https://example.com/",
        [
            ("https://example.com/a", 200, []),  # resolved title_missing
            ("https://example.com/b", 200, ["meta_description_missing"]),  # new issue
            ("https://example.com/c", 200, []),  # new page
        ],
    )

    diff = history.diff_crawls(previous, current)
    assert diff.resolved_issue_codes_by_url == {"https://example.com/a": ["title_missing"]}
    assert diff.new_issue_codes_by_url == {"https://example.com/b": ["meta_description_missing"]}
    assert diff.new_pages == ["https://example.com/c"]
    assert diff.removed_pages == []
    assert diff.new_issue_count == 1
    assert diff.resolved_issue_count == 1
    assert not diff.is_empty


def test_diff_crawls_empty_when_nothing_changed():
    previous = history._snapshot_from_result(
        _result("https://example.com/", [("https://example.com/a", 200, ["title_missing"])])
    )
    current = _result("https://example.com/", [("https://example.com/a", 200, ["title_missing"])])
    diff = history.diff_crawls(previous, current)
    assert diff.is_empty
