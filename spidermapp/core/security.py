from __future__ import annotations

import socket
import ssl
from datetime import datetime, timezone

from spidermapp.core.models import Issue, IssueCategory, IssueSeverity, TlsInfo

CERT_EXPIRY_WARNING_DAYS = 14


def get_tls_info(host: str, port: int = 443, timeout: float = 5.0) -> TlsInfo:
    """Connect to host:port and inspect the TLS certificate. Network I/O — call
    from the async crawler via a thread/executor, not directly in an event loop."""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as TlsInfo.error
        return TlsInfo(valid=False, error=str(exc))

    issuer_parts = dict(x[0] for x in cert.get("issuer", []))
    issuer = issuer_parts.get("organizationName", issuer_parts.get("commonName", ""))
    not_after = cert.get("notAfter", "")
    days_until_expiry = None
    expires_at = ""
    if not_after:
        try:
            expiry_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            expires_at = expiry_dt.isoformat()
            days_until_expiry = (expiry_dt - datetime.now(timezone.utc)).days
        except ValueError:
            pass

    return TlsInfo(valid=True, issuer=issuer, expires_at=expires_at, days_until_expiry=days_until_expiry)


def check_tls_validity(tls: TlsInfo | None) -> list[Issue]:
    if tls is None:
        return []
    issues: list[Issue] = []
    if not tls.valid:
        issues.append(
            Issue(
                IssueCategory.SECURITY,
                IssueSeverity.CRITICAL,
                "tls_invalid",
                f"Certificado HTTPS inválido o inalcanzable: {tls.error}",
            )
        )
        return issues
    if tls.days_until_expiry is not None and tls.days_until_expiry < 0:
        issues.append(
            Issue(IssueCategory.SECURITY, IssueSeverity.CRITICAL, "tls_expired", "El certificado HTTPS ya expiró.")
        )
    elif tls.days_until_expiry is not None and tls.days_until_expiry < CERT_EXPIRY_WARNING_DAYS:
        issues.append(
            Issue(
                IssueCategory.SECURITY,
                IssueSeverity.WARNING,
                "tls_expiring_soon",
                f"El certificado HTTPS expira en {tls.days_until_expiry} día(s).",
            )
        )
    return issues


def check_http_to_https_redirect(chain: list[tuple[str, int]], final_url: str) -> list[Issue]:
    """chain/final_url come from fetching the http:// version of a URL."""
    issues: list[Issue] = []
    if not final_url.startswith("https://"):
        issues.append(
            Issue(
                IssueCategory.SECURITY,
                IssueSeverity.CRITICAL,
                "http_not_redirected_to_https",
                "La versión HTTP no redirige a HTTPS.",
            )
        )
        return issues

    if not chain:
        issues.append(
            Issue(
                IssueCategory.SECURITY,
                IssueSeverity.WARNING,
                "https_no_redirect_detected",
                "No se detectó un redirect explícito de HTTP a HTTPS (verificar configuración del servidor).",
            )
        )
    elif any(status not in (301, 308) for _, status in chain):
        issues.append(
            Issue(
                IssueCategory.SECURITY,
                IssueSeverity.WARNING,
                "http_to_https_not_permanent",
                "El redirect de HTTP a HTTPS no usa un código permanente (301/308).",
            )
        )
    return issues
