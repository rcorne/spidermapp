from spidermapp.core import connectors, history, keywords, llm_visibility, reports, site_structure
from spidermapp.core.models import CrawlResult, IssueCategory, IssueSeverity, LinkEdge, PageResult


# ---------------------------------------------------------------- keywords

def test_extract_keywords_prefers_title_terms():
    result = keywords.extract_keywords(
        title="Farmacia online de medicamentos",
        h1_list=["Farmacia online"],
        meta_description="Compra medicamentos en nuestra farmacia online.",
        visible_text="catálogo de medicamentos y productos de farmacia " * 5,
    )
    assert result
    assert any("farmacia" in kw for kw in result)


def test_extract_keywords_ignores_stopwords():
    result = keywords.extract_keywords("Los mejores para todos", [], "", "")
    assert all(kw not in ("los", "para", "todos") for kw in result)


def test_extract_keywords_empty_page():
    assert keywords.extract_keywords("", [], "", "") == []


# ---------------------------------------------------------- site structure

def test_build_site_tree_groups_by_host_and_path():
    pages = [
        PageResult(url="https://example.com/", final_url="https://example.com/", status_code=200),
        PageResult(url="https://example.com/cat/prod", final_url="https://example.com/cat/prod", status_code=200),
    ]
    pages[0].outlinks.append(
        LinkEdge(source="https://example.com/", target="https://blog.example.com/post", is_internal=True)
    )
    tree = site_structure.build_site_tree(pages, "https://example.com/")

    assert "example.com" in tree.children
    assert "blog.example.com" in tree.children  # linked subdomain appears without being crawled
    host = tree.children["example.com"]
    assert "cat" in host.children
    assert "prod" in host.children["cat"].children


def test_build_site_tree_excludes_external_domains():
    pages = [PageResult(url="https://example.com/", status_code=200)]
    pages[0].outlinks.append(
        LinkEdge(source="https://example.com/", target="https://otro-dominio.com/x", is_internal=False)
    )
    tree = site_structure.build_site_tree(pages, "https://example.com/")
    assert "otro-dominio.com" not in tree.children


# -------------------------------------------------------------- connectors

def test_connectors_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(connectors, "CONFIG_PATH", tmp_path / "connectors.json")
    connectors.save_config({"pagespeed": "test-key"})
    assert connectors.get_key("pagespeed") == "test-key"
    assert connectors.is_configured("pagespeed")
    assert not connectors.is_configured("openai")


def test_connectors_require_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(connectors, "CONFIG_PATH", tmp_path / "connectors.json")
    import pytest

    with pytest.raises(connectors.ConnectorNotConfigured):
        connectors._require("openai")


# ---------------------------------------------------------- llm visibility

def test_domain_mentioned_detects_brand_and_domain():
    assert llm_visibility.domain_mentioned("Te recomiendo Cruz Verde (cruzverde.com.co)", "https://www.cruzverde.com.co")
    assert llm_visibility.domain_mentioned("El sitio cruzverde.com.co es popular", "https://www.cruzverde.com.co")
    assert not llm_visibility.domain_mentioned("Te recomiendo Farmatodo y La Rebaja", "https://www.cruzverde.com.co")


def test_domain_mentioned_does_not_match_substrings_of_other_words():
    assert not llm_visibility.domain_mentioned("La vercruzada del mercado", "https://cruz.co")


def test_build_queries_skips_brand_keywords():
    queries = llm_visibility.build_queries(
        ["cruzverde ofertas", "farmacia online", "medicamentos"], "https://cruzverde.com.co"
    )
    assert all("cruzverde" not in q for q in queries)
    assert any("farmacia online" in q for q in queries)


def test_run_visibility_check_without_keys_reports_unconfigured(tmp_path, monkeypatch):
    monkeypatch.setattr(connectors, "CONFIG_PATH", tmp_path / "connectors.json")
    report = llm_visibility.run_visibility_check("https://example.com", ["farmacia online"])
    assert report.providers_checked == []
    assert set(report.providers_unconfigured) == set(connectors.LLM_PROVIDERS)
    assert report.results == []


# ------------------------------------------------------------ area reports

def _result_with_issues():
    result = CrawlResult(seed_url="https://example.com/")
    page = PageResult(url="https://example.com/a", status_code=404)
    page.add_issue(IssueCategory.RESPONSE_CODES, IssueSeverity.CRITICAL, "error_404", "404")
    result.pages.append(page)
    page2 = PageResult(url="https://example.com/b", status_code=200, title="")
    page2.add_issue(IssueCategory.TITLES, IssueSeverity.CRITICAL, "title_missing", "sin title")
    result.pages.append(page2)
    return result


def test_generate_area_reports_writes_one_pdf_per_area_with_findings(tmp_path):
    written = reports.generate_area_reports(_result_with_issues(), tmp_path)
    names = {p.name for p in written}
    assert "informe_response_codes.pdf" in names
    assert "informe_titles.pdf" in names
    assert all(p.read_bytes().startswith(b"%PDF") for p in written)
    # areas without findings must not produce a file
    assert not (tmp_path / "informe_security.pdf").exists()


# ------------------------------------------------------- full crawl history

def test_save_and_load_full_crawl_roundtrip(tmp_path):
    result = _result_with_issues()
    result.pages[0].keywords = ["farmacia online"]
    result.pages[0].is_orphan = True
    path = history.save_crawl(result, history_dir=tmp_path)

    loaded = history.load_full_crawl(path)
    assert loaded is not None
    assert loaded.seed_url == "https://example.com/"
    assert len(loaded.pages) == 2

    restored = next(p for p in loaded.pages if p.url == "https://example.com/a")
    assert restored.status_code == 404
    assert restored.is_orphan
    assert restored.keywords == ["farmacia online"]
    assert [i.code for i in restored.issues] == ["error_404"]


def test_list_all_snapshots_returns_metadata(tmp_path):
    history.save_crawl(_result_with_issues(), history_dir=tmp_path)
    entries = history.list_all_snapshots(history_dir=tmp_path)
    assert len(entries) == 1
    assert entries[0]["seed_url"] == "https://example.com/"
    assert entries[0]["page_count"] == 2
    assert entries[0]["has_full"]
