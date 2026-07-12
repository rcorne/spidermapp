from spidermapp.core import sitemap


URLSET_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/a</loc></url>
  <url><loc>https://example.com/b</loc></url>
</urlset>
"""

SITEMAP_INDEX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-1.xml</loc></sitemap>
  <sitemap><loc>https://example.com/sitemap-2.xml</loc></sitemap>
</sitemapindex>
"""


def test_parse_urlset():
    parsed = sitemap.parse_sitemap_xml(URLSET_XML, "https://example.com/sitemap.xml")
    assert not parsed.is_index
    assert parsed.urls == ["https://example.com/a", "https://example.com/b"]
    assert parsed.parse_error == ""


def test_parse_sitemap_index():
    parsed = sitemap.parse_sitemap_xml(SITEMAP_INDEX_XML, "https://example.com/sitemap.xml")
    assert parsed.is_index
    assert parsed.child_sitemaps == [
        "https://example.com/sitemap-1.xml",
        "https://example.com/sitemap-2.xml",
    ]


def test_parse_invalid_xml_reports_error():
    parsed = sitemap.parse_sitemap_xml("<not valid xml", "https://example.com/sitemap.xml")
    assert parsed.parse_error != ""


def test_validate_sitemap_urls_flags_empty():
    codes = {i.code for i in sitemap.validate_sitemap_urls([], "https://example.com/")}
    assert "sitemap_empty" in codes


def test_validate_sitemap_urls_flags_off_domain():
    urls = ["https://example.com/a", "https://other.com/b"]
    codes = {i.code for i in sitemap.validate_sitemap_urls(urls, "https://example.com/")}
    assert "sitemap_off_domain_urls" in codes


def test_validate_sitemap_urls_flags_broken_status():
    urls = ["https://example.com/a", "https://example.com/dead"]
    status_by_url = {"https://example.com/a": 200, "https://example.com/dead": 404}
    codes = {
        i.code
        for i in sitemap.validate_sitemap_urls(urls, "https://example.com/", status_by_url=status_by_url)
    }
    assert "sitemap_broken_urls" in codes


def test_validate_sitemap_urls_flags_missing_crawled_urls():
    urls = ["https://example.com/a"]
    crawled = {"https://example.com/a", "https://example.com/orphan"}
    codes = {
        i.code
        for i in sitemap.validate_sitemap_urls(urls, "https://example.com/", crawled_urls=crawled)
    }
    assert "sitemap_missing_crawled_urls" in codes


def test_validate_sitemap_urls_clean_case_has_no_issues():
    urls = ["https://example.com/a"]
    status_by_url = {"https://example.com/a": 200}
    crawled = {"https://example.com/a"}
    assert (
        sitemap.validate_sitemap_urls(
            urls, "https://example.com/", status_by_url=status_by_url, crawled_urls=crawled
        )
        == []
    )
