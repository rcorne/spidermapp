import socket
import ssl

import httpx

from spidermapp.core import fetch_errors


def test_dns_error_from_exception_chain():
    inner = socket.gaierror(8, "nodename nor servname provided")
    outer = httpx.ConnectError("connection failed")
    outer.__cause__ = inner
    assert fetch_errors.classify_fetch_error(outer) == fetch_errors.DNS_NOT_FOUND


def test_timeout_from_httpx_exception():
    assert fetch_errors.classify_fetch_error(httpx.ReadTimeout("timed out")) == fetch_errors.TIMEOUT


def test_connection_refused_from_exception_chain():
    inner = ConnectionRefusedError(61, "Connection refused")
    outer = httpx.ConnectError("connection failed")
    outer.__cause__ = inner
    assert fetch_errors.classify_fetch_error(outer) == fetch_errors.CONNECTION_REFUSED


def test_ssl_error_from_exception_chain():
    inner = ssl.SSLError("certificate verify failed")
    outer = httpx.ConnectError("connect error")
    outer.__cause__ = inner
    assert fetch_errors.classify_fetch_error(outer) == fetch_errors.SSL_ERROR


def test_bare_connect_error_is_generic():
    assert fetch_errors.classify_fetch_error(httpx.ConnectError("nope")) == fetch_errors.CONNECTION_ERROR


def test_dns_from_plain_string():
    # Playwright reports failures as strings, not typed exceptions.
    assert fetch_errors.classify_fetch_error("net::ERR_NAME_NOT_RESOLVED") == fetch_errors.DNS_NOT_FOUND


def test_refused_from_plain_string():
    assert fetch_errors.classify_fetch_error("net::ERR_CONNECTION_REFUSED") == fetch_errors.CONNECTION_REFUSED


def test_tls_from_plain_string():
    assert fetch_errors.classify_fetch_error("net::ERR_CERT_DATE_INVALID") == fetch_errors.SSL_ERROR


def test_timeout_from_plain_string():
    assert fetch_errors.classify_fetch_error("Navigation timed out after 30000ms") == fetch_errors.TIMEOUT


def test_unknown_string_falls_back_to_connection_error():
    assert fetch_errors.classify_fetch_error("something weird happened") == fetch_errors.CONNECTION_ERROR


def test_every_code_has_a_human_label():
    for code in (
        fetch_errors.DNS_NOT_FOUND,
        fetch_errors.TIMEOUT,
        fetch_errors.CONNECTION_REFUSED,
        fetch_errors.SSL_ERROR,
        fetch_errors.CONNECTION_ERROR,
    ):
        assert fetch_errors.error_label(code)


def test_unknown_code_label_falls_back():
    assert fetch_errors.error_label("not-a-real-code") == fetch_errors.error_label(fetch_errors.CONNECTION_ERROR)


def test_cycle_in_exception_chain_terminates():
    """A __cause__ loop must not hang the classifier."""
    a = httpx.ConnectError("a")
    b = httpx.ConnectError("b")
    a.__cause__ = b
    b.__cause__ = a
    assert fetch_errors.classify_fetch_error(a) == fetch_errors.CONNECTION_ERROR
