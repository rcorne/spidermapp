from spidermapp.core import redirects


def test_detect_meta_refresh():
    html = '<meta http-equiv="refresh" content="0; url=https://example.com/nueva">'
    assert redirects.detect_meta_refresh(html) == "https://example.com/nueva"
    assert redirects.detect_meta_refresh("<p>sin refresh</p>") == ""


def test_detect_js_redirect():
    assert redirects.detect_js_redirect("<script>window.location.href='/x'</script>")
    assert redirects.detect_js_redirect("<script>window.location.replace('/x')</script>")
    assert not redirects.detect_js_redirect("<script>console.log('hi')</script>")


def test_check_redirect_chain_flags_temporary_redirect():
    chain = [("https://example.com/old", 302)]
    codes = {i.code for i in redirects.check_redirect_chain(chain)}
    assert "temporary_redirect_should_be_permanent" in codes


def test_check_redirect_chain_flags_too_long():
    chain = [("https://example.com/a", 301), ("https://example.com/b", 301), ("https://example.com/c", 301)]
    codes = {i.code for i in redirects.check_redirect_chain(chain)}
    assert "redirect_chain_too_long" in codes


def test_check_redirect_chain_flags_loop():
    chain = [("https://example.com/a", 301), ("https://example.com/b", 301), ("https://example.com/a", 301)]
    codes = {i.code for i in redirects.check_redirect_chain(chain)}
    assert "redirect_loop" in codes


def test_check_redirect_chain_single_301_has_no_issues():
    chain = [("https://example.com/old", 301)]
    assert redirects.check_redirect_chain(chain) == []


def test_check_redirect_chain_flags_meta_refresh_and_js():
    html = '<meta http-equiv="refresh" content="0; url=/x"><script>window.location="/y"</script>'
    codes = {i.code for i in redirects.check_redirect_chain([], html_of_final=html)}
    assert "meta_refresh_redirect" in codes
    assert "js_redirect" in codes
