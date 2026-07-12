from spidermapp.core import export
from spidermapp.core.models import Issue, IssueCategory, IssueSeverity, PageResult


def _sample_page():
    page = PageResult(url="https://example.com/", status_code=200, title="Inicio", h1=["Bienvenido"])
    page.issues.append(Issue(IssueCategory.TITLES, IssueSeverity.WARNING, "title_too_short", "Título corto"))
    return page


def test_pages_to_dataframe_has_expected_columns():
    df = export.pages_to_dataframe([_sample_page()])
    assert "URL" in df.columns
    assert "Status Code" in df.columns
    assert df.iloc[0]["URL"] == "https://example.com/"
    assert df.iloc[0]["Issue Count"] == 1


def test_export_csv_writes_file(tmp_path):
    path = tmp_path / "crawl.csv"
    export.export_csv([_sample_page()], path)
    assert path.exists()
    assert "example.com" in path.read_text()


def test_export_xlsx_writes_file(tmp_path):
    path = tmp_path / "crawl.xlsx"
    export.export_xlsx([_sample_page()], path)
    assert path.exists()
    assert path.stat().st_size > 0
