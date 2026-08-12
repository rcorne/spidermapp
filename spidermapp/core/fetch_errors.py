from __future__ import annotations

import socket
import ssl

import httpx

# Adapted from LibreCrawl's classify_fetch_error (MIT, © 2025 Phiality — see
# THIRD_PARTY_LICENSES.md). Theirs targets requests/urllib3 exception types;
# this maps the same categories onto httpx's hierarchy, and keeps their
# message-marker fallback for errors that arrive as plain strings (which is
# how Playwright reports them during the Chromium fallback path).
#
# The point: "no se pudo conectar" is not one problem. A DNS typo, a firewall
# refusing the port, and an expired certificate need three different fixes,
# so they get three different issue codes and three different recommendations.

DNS_NOT_FOUND = "dns_not_found"
TIMEOUT = "timeout"
CONNECTION_REFUSED = "connection_refused"
SSL_ERROR = "ssl_error"
CONNECTION_ERROR = "connection_error"

_DNS_MARKERS = (
    "getaddrinfo failed",
    "name or service not known",
    "name resolution",
    "nodename nor servname",
    "no address associated",
    "name does not resolve",
    "temporary failure in name resolution",
    "name_not_resolved",
    "err_name_not_resolved",
    "nxdomain",
)

_LABELS = {
    DNS_NOT_FOUND: "El dominio no existe o no resuelve (DNS)",
    TIMEOUT: "El servidor no respondió a tiempo",
    CONNECTION_REFUSED: "El servidor rechazó la conexión",
    SSL_ERROR: "Falló la conexión segura (certificado/TLS)",
    CONNECTION_ERROR: "No se pudo conectar con el servidor",
}


def classify_fetch_error(exc_or_msg: BaseException | str) -> str:
    """Coarse category for a failed fetch, from an exception or a raw string.

    Walks the __cause__/__context__ chain first, because httpx wraps the
    underlying socket/ssl error — the useful detail is never the outermost
    exception. Falls back to matching the message when there's no typed
    exception to inspect."""
    if isinstance(exc_or_msg, BaseException):
        seen: set[int] = set()
        current: BaseException | None = exc_or_msg
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if isinstance(current, socket.gaierror):
                return DNS_NOT_FOUND
            if isinstance(current, (ssl.SSLError, httpx.ConnectError)) and _looks_like_tls(current):
                return SSL_ERROR
            if isinstance(current, ConnectionRefusedError):
                return CONNECTION_REFUSED
            if isinstance(current, (socket.timeout, httpx.TimeoutException)):
                return TIMEOUT
            current = current.__cause__ or current.__context__

    return _classify_message(str(exc_or_msg))


def _looks_like_tls(exc: BaseException) -> bool:
    if isinstance(exc, ssl.SSLError):
        return True
    lowered = str(exc).lower()
    return any(marker in lowered for marker in ("ssl", "certificate", "tls", "err_cert"))


def _classify_message(message: str) -> str:
    lowered = message.lower()
    if any(marker in lowered for marker in _DNS_MARKERS):
        return DNS_NOT_FOUND
    if "timed out" in lowered or "timeout" in lowered:
        return TIMEOUT
    if "refused" in lowered or "err_connection_refused" in lowered:
        return CONNECTION_REFUSED
    if any(marker in lowered for marker in ("ssl", "certificate", "err_cert", "tls")):
        return SSL_ERROR
    return CONNECTION_ERROR


def error_label(code: str) -> str:
    return _LABELS.get(code, _LABELS[CONNECTION_ERROR])
