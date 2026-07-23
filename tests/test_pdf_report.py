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


def test_default_pdf_filename_uses_bare_domain():
    assert pdf_report.default_pdf_filename("https://www.cruzverde.com.co/tienda") == "reporte_cruzverde.com.co.pdf"


def test_default_pdf_filename_falls_back_when_url_unparseable():
    assert pdf_report.default_pdf_filename("") == "reporte_sitio.pdf"


def test_generate_pdf_report_includes_error_pages(tmp_path):
    result = CrawlResult(seed_url="https://example.com/")
    result.pages.append(PageResult(url="https://example.com/", status_code=200))
    result.pages.append(PageResult(url="https://example.com/roto", status_code=404))
    result.pages.append(PageResult(url="https://example.com/caido", error="Connection refused"))
    out = tmp_path / "report.pdf"
    path = pdf_report.generate_pdf_report(result, out)
    assert path.exists()
    assert path.read_bytes().startswith(b"%PDF")


def test_generate_pdf_report_handles_large_crawl_with_truncation(tmp_path):
    result = CrawlResult(seed_url="https://example.com/")
    for i in range(pdf_report.MAX_URL_ROWS + 50):
        result.pages.append(PageResult(url=f"https://example.com/page-{i}", status_code=200))
    out = tmp_path / "big.pdf"
    path = pdf_report.generate_pdf_report(result, out)
    assert path.exists()
    assert path.read_bytes().startswith(b"%PDF")
