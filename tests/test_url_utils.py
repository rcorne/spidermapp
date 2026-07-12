from spidermapp.core import url_utils


def test_normalize_url_resolves_relative_and_strips_fragment():
    assert (
        url_utils.normalize_url("/foo?x=1#section", base="https://example.com/bar/")
        == "https://example.com/foo?x=1"
    )


def test_is_same_site_default_ignores_www_only():
    assert url_utils.is_same_site("https://example.com/a", "https://www.example.com/b")
    assert not url_utils.is_same_site("https://example.com/a", "https://sub.example.com/b")


def test_is_same_site_include_subdomains():
    assert url_utils.is_same_site(
        "https://example.com/a", "https://sub.example.com/b", include_subdomains=True
    )
    assert not url_utils.is_same_site(
        "https://example.com/a", "https://other.com/b", include_subdomains=True
    )


def test_has_trailing_slash():
    assert url_utils.has_trailing_slash("https://example.com/foo/")
    assert not url_utils.has_trailing_slash("https://example.com/foo")
    assert not url_utils.has_trailing_slash("https://example.com/")


def test_swap_scheme_and_www():
    assert url_utils.swap_scheme("http://example.com/x", "https") == "https://example.com/x"
    assert url_utils.swap_www("https://example.com/x", True) == "https://www.example.com/x"
    assert url_utils.swap_www("https://www.example.com/x", False) == "https://example.com/x"


def test_check_url_conventions_flags_uppercase_underscore_and_double_slash():
    codes = {i.code for i in url_utils.check_url_conventions("https://example.com/Foo_Bar//baz")}
    assert "url_uppercase" in codes
    assert "url_underscore" in codes
    assert "url_multi_slash" in codes


def test_check_url_conventions_clean_url_has_no_issues():
    assert url_utils.check_url_conventions("https://example.com/foo-bar") == []


def test_check_site_wide_url_consistency_detects_mixed_www_and_scheme():
    urls = [
        "https://example.com/a",
        "https://www.example.com/b",
        "http://example.com/c",
    ]
    codes = {i.code for i in url_utils.check_site_wide_url_consistency(urls)}
    assert "mixed_www" in codes
    assert "mixed_scheme" in codes


def test_check_site_wide_url_consistency_detects_mixed_trailing_slash():
    urls = ["https://example.com/a/", "https://example.com/b"]
    codes = {i.code for i in url_utils.check_site_wide_url_consistency(urls)}
    assert "mixed_trailing_slash" in codes


def test_check_site_wide_url_consistency_clean_site_has_no_issues():
    urls = ["https://example.com/a", "https://example.com/b"]
    assert url_utils.check_site_wide_url_consistency(urls) == []
