import base64
import json

import httpx
import pytest

from spidermapp.core import auth


def test_generate_pkce_pair_challenge_matches_verifier():
    import hashlib

    verifier, challenge = auth.generate_pkce_pair()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected
    assert len(verifier) >= 43  # RFC 7636 minimum length


def test_generate_pkce_pair_is_random_each_call():
    v1, _ = auth.generate_pkce_pair()
    v2, _ = auth.generate_pkce_pair()
    assert v1 != v2


def test_build_authorize_url_includes_pkce_and_state():
    provider = auth.PROVIDERS["google"]
    url = auth.build_authorize_url(provider, "client-123", "state-abc", "challenge-xyz")
    assert url.startswith(provider.authorize_url + "?")
    params = httpx.URL(url).params
    assert params["client_id"] == "client-123"
    assert params["state"] == "state-abc"
    assert params["code_challenge"] == "challenge-xyz"
    assert params["code_challenge_method"] == "S256"
    assert params["redirect_uri"] == auth.REDIRECT_URI


def test_build_authorize_url_includes_provider_extra_params():
    provider = auth.PROVIDERS["apple"]
    url = auth.build_authorize_url(provider, "client-123", "state-abc", "challenge-xyz")
    assert "response_mode=form_post" in url


def test_decode_jwt_payload_extracts_claims():
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"email": "ana@example.com"}).encode()).rstrip(b"=").decode()
    token = f"{header}.{payload}.sig"
    assert auth.decode_jwt_payload(token) == {"email": "ana@example.com"}


def test_decode_jwt_payload_returns_empty_for_garbage():
    assert auth.decode_jwt_payload("not-a-jwt") == {}


def test_exchange_code_sends_pkce_verifier_and_parses_response(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read().decode()
        return httpx.Response(200, json={"access_token": "tok123", "id_token": "abc.def.ghi"})

    def fake_post(url, data=None, headers=None, timeout=None):
        return httpx.Client(transport=httpx.MockTransport(handler)).post(url, data=data, headers=headers)

    monkeypatch.setattr(auth.httpx, "post", fake_post)
    tokens = auth._exchange_code(auth.PROVIDERS["google"], "cid", "", "code-1", "verifier-1")
    assert tokens["access_token"] == "tok123"
    assert "code_verifier=verifier-1" in captured["body"]
    assert "code=code-1" in captured["body"]


def test_exchange_code_raises_on_error_response(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="invalid_grant")

    def fake_post(url, data=None, headers=None, timeout=None):
        return httpx.Client(transport=httpx.MockTransport(handler)).post(url, data=data, headers=headers)

    monkeypatch.setattr(auth.httpx, "post", fake_post)
    with pytest.raises(auth.AuthError):
        auth._exchange_code(auth.PROVIDERS["google"], "cid", "", "bad-code", "verifier-1")


def test_fetch_profile_uses_userinfo_endpoint_when_available(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer tok123"
        return httpx.Response(200, json={"name": "Ana Torres", "email": "ana@example.com", "picture": "https://x/y.png"})

    def fake_get(url, headers=None, timeout=None):
        return httpx.Client(transport=httpx.MockTransport(handler)).get(url, headers=headers)

    monkeypatch.setattr(auth.httpx, "get", fake_get)
    profile = auth._fetch_profile(auth.PROVIDERS["google"], {"access_token": "tok123"})
    assert profile == {"name": "Ana Torres", "email": "ana@example.com", "picture": "https://x/y.png", "subject": ""}


def test_fetch_profile_decodes_id_token_for_apple():
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"email": "cliente@icloud.com"}).encode()).rstrip(b"=").decode()
    token = f"{header}.{payload}.sig"
    profile = auth._fetch_profile(auth.PROVIDERS["apple"], {"id_token": token})
    assert profile["email"] == "cliente@icloud.com"
    assert profile["name"] == "cliente"


def test_run_login_flow_rejects_missing_client_id():
    with pytest.raises(auth.AuthError):
        auth.run_login_flow("google", client_id="")


def test_run_login_flow_rejects_missing_required_secret():
    with pytest.raises(auth.AuthError):
        auth.run_login_flow("github", client_id="cid", client_secret="")


def test_run_login_flow_rejects_unknown_provider():
    with pytest.raises(auth.AuthError):
        auth.run_login_flow("facebook", client_id="cid")


def test_generate_apple_client_secret_produces_valid_es256_jwt():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    token = auth.generate_apple_client_secret("TEAM123", "com.example.app", "KEY123", pem)
    header_b64, payload_b64, sig_b64 = token.split(".")

    padded = header_b64 + "=" * (-len(header_b64) % 4)
    header = json.loads(base64.urlsafe_b64decode(padded))
    assert header == {"alg": "ES256", "kid": "KEY123"}

    payload = auth.decode_jwt_payload(token)
    assert payload["iss"] == "TEAM123"
    assert payload["sub"] == "com.example.app"
    assert payload["aud"] == "https://appleid.apple.com"

    # Signature actually verifies against the public key.
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    raw_sig = base64.urlsafe_b64decode(sig_b64 + "=" * (-len(sig_b64) % 4))
    r = int.from_bytes(raw_sig[:32], "big")
    s = int.from_bytes(raw_sig[32:], "big")
    der_sig = encode_dss_signature(r, s)
    from cryptography.hazmat.primitives import hashes

    key.public_key().verify(der_sig, f"{header_b64}.{payload_b64}".encode(), ec.ECDSA(hashes.SHA256()))


def test_generate_apple_client_secret_raises_on_bad_key():
    with pytest.raises(auth.AuthError):
        auth.generate_apple_client_secret("TEAM123", "com.example.app", "KEY123", "not a pem key")


def test_session_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "SESSION_PATH", tmp_path / "session.json")
    assert auth.load_session() is None
    session = {"provider": "google", "profile": {"email": "a@b.com"}, "connected_at": 1.0}
    auth.save_session(session)
    assert auth.load_session() == session
    auth.clear_session()
    assert auth.load_session() is None


def test_provider_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "CONFIG_PATH", tmp_path / "auth_providers.json")
    assert auth.load_provider_config() == {}
    config = {"google": {"client_id": "abc"}}
    auth.save_provider_config(config)
    assert auth.load_provider_config() == config
