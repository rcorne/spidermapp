from spidermapp.core import pdf_report
from spidermapp.core.models import CrawlResult, IssueCategory, IssueSeverity, PageResult


def _result():
    result = CrawlResult(seed_url="https://example.com/")
    page = PageResult(url="https://example.com/", status_code=200)
    page.add_issue(IssueCategory.TITLES, IssueSeverity.CRITICAL, "title_missing", "Falta el title.")
    result.pages.append(page)
    return result


def test_generate_pdf_report_writes_valid_pdf(tmp_path):
    out = tmp_path / "report.pdf"
    path = pdf_report.generate_pdf_report(_result(), out)
    assert path == out
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF")


def test_generate_pdf_report_handles_empty_crawl(tmp_path):
    out = tmp_path / "empty.pdf"
    result = CrawlResult(seed_url="https://example.com/")
    pdf_report.generate_pdf_report(result, out)
    assert out.exists()
