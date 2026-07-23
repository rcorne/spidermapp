from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import queue
import secrets
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

import httpx

# OAuth 2.0 Authorization Code + PKCE, the standard flow for native/desktop
# apps (RFC 8252): open the system browser, catch the redirect on a local
# loopback server, exchange the code for tokens server-to-server. No secret
# is required on the wire for the browser leg — only in the token exchange,
# and only for providers that mandate one (LinkedIn; Apple via a signed JWT).
#
# Spidermapp cannot register OAuth apps on the user's behalf — each provider
# requires its own developer console entry with this exact redirect URI.

CONFIG_PATH = Path.home() / ".spidermapp" / "auth_providers.json"
SESSION_PATH = Path.home() / ".spidermapp" / "session.json"

REDIRECT_PORT = 53682
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/callback"

_CALLBACK_HTML = (
    b"<html><body style='font-family:-apple-system,sans-serif;padding:48px;text-align:center;color:#111827;'>"
    b"<h2>Listo</h2><p>Ya puedes cerrar esta ventana y volver a Spidermapp.</p></body></html>"
)


@dataclass(frozen=True)
class ProviderSpec:
    key: str
    label: str
    authorize_url: str
    token_url: str
    scope: str
    userinfo_url: str = ""  # empty => profile comes from the id_token instead
    extra_authorize_params: dict = field(default_factory=dict)
    requires_secret: bool = False
    help_url: str = ""


PROVIDERS: dict[str, ProviderSpec] = {
    "google": ProviderSpec(
        key="google",
        label="Google",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scope="openid email profile",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        extra_authorize_params={"access_type": "offline", "prompt": "consent"},
        help_url="https://console.cloud.google.com/apis/credentials",
    ),
    "linkedin": ProviderSpec(
        key="linkedin",
        label="LinkedIn",
        authorize_url="https://www.linkedin.com/oauth/v2/authorization",
        token_url="https://www.linkedin.com/oauth/v2/accessToken",
        scope="openid profile email",
        userinfo_url="https://api.linkedin.com/v2/userinfo",
        requires_secret=True,
        help_url="https://www.linkedin.com/developers/apps",
    ),
    "apple": ProviderSpec(
        key="apple",
        label="Apple",
        authorize_url="https://appleid.apple.com/auth/authorize",
        token_url="https://appleid.apple.com/auth/token",
        scope="name email",
        userinfo_url="",
        extra_authorize_params={"response_mode": "form_post"},
        requires_secret=True,
        help_url="https://developer.apple.com/account/resources/identifiers/list/serviceId",
    ),
}


class AuthError(Exception):
    pass


# ---------------------------------------------------------------------------
# PKCE
# ---------------------------------------------------------------------------


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_pkce_pair() -> tuple[str, str]:
    """(code_verifier, code_challenge) per RFC 7636, S256 method."""
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def build_authorize_url(provider: ProviderSpec, client_id: str, state: str, code_challenge: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": provider.scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    params.update(provider.extra_authorize_params)
    return f"{provider.authorize_url}?{urllib.parse.urlencode(params)}"


# ---------------------------------------------------------------------------
# Local redirect server — catches both GET (Google/LinkedIn) and POST
# (Apple, which mandates response_mode=form_post whenever name/email scopes
# are requested).
# ---------------------------------------------------------------------------


def _make_handler(result_q: "queue.Queue[dict]"):
    class Handler(http.server.BaseHTTPRequestHandler):
        def _respond(self, params: dict) -> None:
            result_q.put(params)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_CALLBACK_HTML)

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            parsed = urllib.parse.urlparse(self.path)
            self._respond({k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()})

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            self._respond({k: v[0] for k, v in urllib.parse.parse_qs(body).items()})

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - silence default stderr logging
            pass

    return Handler


def _wait_for_redirect(timeout: float) -> dict:
    result_q: "queue.Queue[dict]" = queue.Queue()
    server = http.server.HTTPServer(("127.0.0.1", REDIRECT_PORT), _make_handler(result_q))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        return result_q.get(timeout=timeout)
    except queue.Empty:
        raise AuthError("No se recibió respuesta del proveedor a tiempo. Intenta de nuevo.") from None
    finally:
        server.shutdown()
        thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Token exchange + profile
# ---------------------------------------------------------------------------


def _exchange_code(provider: ProviderSpec, client_id: str, client_secret: str, code: str, verifier: str) -> dict:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    if client_secret:
        data["client_secret"] = client_secret
    response = httpx.post(provider.token_url, data=data, timeout=20.0)
    if response.status_code >= 400:
        raise AuthError(f"El proveedor rechazó el intercambio de token: {response.text[:300]}")
    return response.json()


def decode_jwt_payload(token: str) -> dict:
    """Decodes (without verifying) the payload of a JWT — used only to read
    display claims (email/name) from an id_token; the actual trust anchor is
    the token exchange itself (server-to-server, TLS)."""
    try:
        payload_b64 = token.split(".")[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        return {}


def _fetch_profile(provider: ProviderSpec, tokens: dict) -> dict:
    if provider.userinfo_url:
        access_token = tokens.get("access_token", "")
        response = httpx.get(
            provider.userinfo_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=15.0
        )
        if response.status_code >= 400:
            raise AuthError(f"No se pudo obtener el perfil: {response.text[:300]}")
        data = response.json()
        return {
            "name": data.get("name") or data.get("given_name", ""),
            "email": data.get("email", ""),
            "picture": data.get("picture", ""),
        }

    claims = decode_jwt_payload(tokens.get("id_token", ""))
    email = claims.get("email", "")
    return {"name": email.split("@")[0] if email else "Usuario de Apple", "email": email, "picture": ""}


# ---------------------------------------------------------------------------
# Apple's client_secret must be a JWT signed with the Sign in with Apple
# private key (ES256) — not a plain string like Google/LinkedIn use.
# ---------------------------------------------------------------------------


def generate_apple_client_secret(
    team_id: str, client_id: str, key_id: str, private_key_pem: str, expires_in: int = 15777000
) -> str:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

    header = {"alg": "ES256", "kid": key_id}
    now = int(time.time())
    payload = {"iss": team_id, "iat": now, "exp": now + expires_in, "aud": "https://appleid.apple.com", "sub": client_id}
    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()

    try:
        private_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    except Exception as exc:
        raise AuthError(f"No se pudo leer la clave privada de Apple (.p8): {exc}") from exc

    der_signature = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der_signature)
    raw_signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"{header_b64}.{payload_b64}.{_b64url(raw_signature)}"


# ---------------------------------------------------------------------------
# Full flow
# ---------------------------------------------------------------------------


def run_login_flow(provider_key: str, client_id: str, client_secret: str = "", timeout: float = 180.0) -> dict:
    """Blocking end-to-end login. Run from a background thread — never the
    UI thread, since it waits on the browser and the local redirect."""
    if provider_key not in PROVIDERS:
        raise AuthError(f"Proveedor desconocido: {provider_key}")
    provider = PROVIDERS[provider_key]
    if not client_id:
        raise AuthError(f"Falta el Client ID de {provider.label}.")
    if provider.requires_secret and not client_secret:
        raise AuthError(f"{provider.label} requiere un client secret configurado.")

    verifier, challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(16)

    url = build_authorize_url(provider, client_id, state, challenge)
    webbrowser.open(url)
    params = _wait_for_redirect(timeout)

    if params.get("state") != state:
        raise AuthError("El parámetro state no coincide (posible interferencia). Intenta de nuevo.")
    if "error" in params:
        raise AuthError(f"El proveedor rechazó la autorización: {params.get('error_description', params['error'])}")
    code = params.get("code")
    if not code:
        raise AuthError("No se recibió un código de autorización.")

    tokens = _exchange_code(provider, client_id, client_secret, code, verifier)
    profile = _fetch_profile(provider, tokens)
    session = {"provider": provider_key, "profile": profile, "connected_at": time.time()}
    save_session(session)
    return session


# ---------------------------------------------------------------------------
# Local persistence
# ---------------------------------------------------------------------------


def load_provider_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_provider_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    os.chmod(CONFIG_PATH, 0o600)


def save_session(session: dict) -> None:
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_PATH.write_text(json.dumps(session, indent=2))
    os.chmod(SESSION_PATH, 0o600)


def load_session() -> dict | None:
    if not SESSION_PATH.exists():
        return None
    try:
        return json.loads(SESSION_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def clear_session() -> None:
    if SESSION_PATH.exists():
        SESSION_PATH.unlink()
