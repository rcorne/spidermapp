from spidermapp.core import robots


ROBOTS_TXT = """
User-agent: *
Disallow: /admin/
Sitemap: https://example.com/sitemap.xml
"""

ROBOTS_TXT_BLOCK_ALL = """
User-agent: *
Disallow: /
"""

ROBOTS_TXT_NO_SITEMAP = """
User-agent: *
Disallow: /admin/
"""


def test_parse_robots_extracts_sitemap_directive():
    info = robots.parse_robots_txt(ROBOTS_TXT, "https://example.com/robots.txt")
    assert info.found
    assert info.sitemap_urls == ["https://example.com/sitemap.xml"]


def test_is_allowed_respects_disallow_rules():
    info = robots.parse_robots_txt(ROBOTS_TXT, "https://example.com/robots.txt")
    assert robots.is_allowed(info, "https://example.com/blog/post", "SpidermappBot")
    assert not robots.is_allowed(info, "https://example.com/admin/secret", "SpidermappBot")


def test_is_allowed_when_robots_missing_defaults_to_allowed():
    info = robots.missing_robots("https://example.com/robots.txt", error="404")
    assert robots.is_allowed(info, "https://example.com/anything", "SpidermappBot")


def test_validate_robots_flags_missing_file():
    info = robots.missing_robots("https://example.com/robots.txt")
    codes = {i.code for i in robots.validate_robots(info, "https://example.com/")}
    assert "robots_missing" in codes


def test_validate_robots_flags_block_everything():
    info = robots.parse_robots_txt(ROBOTS_TXT_BLOCK_ALL, "https://example.com/robots.txt")
    codes = {i.code for i in robots.validate_robots(info, "https://example.com/")}
    assert "robots_blocks_everything" in codes


def test_validate_robots_flags_missing_sitemap_directive():
    info = robots.parse_robots_txt(ROBOTS_TXT_NO_SITEMAP, "https://example.com/robots.txt")
    codes = {i.code for i in robots.validate_robots(info, "https://example.com/")}
    assert "robots_no_sitemap_directive" in codes


def test_validate_robots_clean_case_has_no_issues():
    info = robots.parse_robots_txt(ROBOTS_TXT, "https://example.com/robots.txt")
    assert robots.validate_robots(info, "https://example.com/") == []
