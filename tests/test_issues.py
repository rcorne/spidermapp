from spidermapp.core import issues
from spidermapp.core.models import PageResult


def test_response_code_issues_404():
    assert issues.response_code_issues(404, "")[0].code == "error_404"


def test_response_code_issues_5xx():
    assert issues.response_code_issues(503, "")[0].code == "error_5xx"


def test_response_code_issues_fetch_error():
    assert issues.response_code_issues(None, "timeout")[0].code == "fetch_error"


def test_response_code_issues_ok():
    assert issues.response_code_issues(200, "") == []


def test_priority_url_indexation_issue_flags_noindex_priority_url():
    page = PageResult(url="https://example.com/importante", status_code=200, meta_robots="noindex")
    result = issues.priority_url_indexation_issue(page, {"https://example.com/importante"})
    assert result[0].code == "priority_url_not_indexable"


def test_priority_url_indexation_issue_ignored_for_non_priority_url():
    page = PageResult(url="https://example.com/otra", status_code=200, meta_robots="noindex")
    assert issues.priority_url_indexation_issue(page, {"https://example.com/importante"}) == []


def test_collect_page_issues_healthy_page_has_no_issues():
    page = PageResult(
        url="https://example.com/pagina",
        final_url="https://example.com/pagina",
        status_code=200,
        title="Un título de longitud razonable y correcta",
        meta_description="Una meta description con longitud suficiente para pasar los checks de tamaño mínimo y máximo permitido.",
        h1=["Encabezado principal"],
        h2=["Subtítulo de sección"],
        word_count=500,
    )
    assert issues.collect_page_issues(page) == []


def test_collect_page_issues_flags_missing_title_and_404():
    page = PageResult(url="https://example.com/roto", status_code=404)
    codes = {i.code for i in issues.collect_page_issues(page)}
    assert "error_404" in codes
