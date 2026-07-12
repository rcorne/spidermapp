from spidermapp.core import security, tech_detect
from spidermapp.core.models import TlsInfo


def test_check_tls_validity_invalid():
    tls = TlsInfo(valid=False, error="handshake failed")
    assert security.check_tls_validity(tls)[0].code == "tls_invalid"


def test_check_tls_validity_expired():
    tls = TlsInfo(valid=True, days_until_expiry=-5)
    assert security.check_tls_validity(tls)[0].code == "tls_expired"


def test_check_tls_validity_expiring_soon():
    tls = TlsInfo(valid=True, days_until_expiry=3)
    assert security.check_tls_validity(tls)[0].code == "tls_expiring_soon"


def test_check_tls_validity_healthy():
    tls = TlsInfo(valid=True, days_until_expiry=200)
    assert security.check_tls_validity(tls) == []


def test_check_http_to_https_redirect_missing():
    issues = security.check_http_to_https_redirect([], "http://example.com/")
    assert issues[0].code == "http_not_redirected_to_https"


def test_check_http_to_https_redirect_no_chain_but_https_final():
    issues = security.check_http_to_https_redirect([], "https://example.com/")
    assert issues[0].code == "https_no_redirect_detected"


def test_check_http_to_https_redirect_temporary():
    chain = [("http://example.com/", 302)]
    issues = security.check_http_to_https_redirect(chain, "https://example.com/")
    assert issues[0].code == "http_to_https_not_permanent"


def test_check_http_to_https_redirect_healthy():
    chain = [("http://example.com/", 301)]
    assert security.check_http_to_https_redirect(chain, "https://example.com/") == []


def test_detect_tech_wordpress():
    html = '<link href="/wp-content/themes/x/style.css">'
    assert "WordPress" in tech_detect.detect_tech(html, {})


def test_detect_tech_from_headers():
    assert "Nginx" in tech_detect.detect_tech("", {"Server": "nginx/1.18"})


def test_detect_tech_generator_meta():
    html = '<meta name="generator" content="Hugo 0.111">'
    assert "Hugo 0.111" in tech_detect.detect_tech(html, {})


def test_detect_tech_no_match():
    assert tech_detect.detect_tech("<p>hola</p>", {}) == []
