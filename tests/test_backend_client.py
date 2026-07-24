import httpx
import pytest

from spidermapp.core import backend_client


def _client_with_handler(handler, monkeypatch):
    def fake_request(method, url, **kwargs):
        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as c:
            return c.request(method, url, **kwargs)

    def fake_post(url, json=None, headers=None, timeout=None):
        return fake_request("POST", url, json=json, headers=headers)

    def fake_get(url, headers=None, params=None, timeout=None):
        return fake_request("GET", url, headers=headers, params=params)

    monkeypatch.setattr(backend_client.httpx, "post", fake_post)
    monkeypatch.setattr(backend_client.httpx, "get", fake_get)


def test_signup_returns_session(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/signup"
        return httpx.Response(201, json={"token": "tok", "user": {"id": 1, "email": "a@b.com", "display_name": "A"}})

    _client_with_handler(handler, monkeypatch)
    client = backend_client.BackendClient("http://127.0.0.1:8000")
    session = client.signup("a@b.com", "supersecret123", "A")
    assert session.token == "tok"
    assert session.user.email == "a@b.com"


def test_login_raises_backend_error_on_401(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Email o contraseña incorrectos."})

    _client_with_handler(handler, monkeypatch)
    client = backend_client.BackendClient("http://127.0.0.1:8000")
    with pytest.raises(backend_client.BackendError, match="incorrectos"):
        client.login("a@b.com", "wrong")


def test_oauth_link_sends_provider_and_subject(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"token": "tok2", "user": {"id": 2, "email": "g@b.com", "display_name": "G"}})

    _client_with_handler(handler, monkeypatch)
    client = backend_client.BackendClient("http://127.0.0.1:8000")
    session = client.oauth_link("google", "sub-1", "g@b.com", "G")
    assert session.user.id == 2
    assert b'"provider":"google"' in captured["body"]


def test_request_error_raised_when_server_unreachable(monkeypatch):
    def fake_post(url, json=None, headers=None, timeout=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(backend_client.httpx, "post", fake_post)
    client = backend_client.BackendClient("http://127.0.0.1:9999")
    with pytest.raises(backend_client.BackendError, match="No se pudo contactar"):
        client.login("a@b.com", "whatever123")


def test_save_and_load_pidge_session_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(backend_client, "PIDGE_SESSION_PATH", tmp_path / "pidge_session.json")
    session = backend_client.PidgeSession(
        token="tok3",
        user=backend_client.PidgeUser(id=3, email="c@d.com", display_name="C"),
        server_url="http://127.0.0.1:8000",
    )
    backend_client.save_pidge_session(session)
    loaded = backend_client.load_pidge_session()
    assert loaded.token == "tok3"
    assert loaded.user.email == "c@d.com"

    backend_client.clear_pidge_session()
    assert backend_client.load_pidge_session() is None


def test_load_pidge_session_missing_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(backend_client, "PIDGE_SESSION_PATH", tmp_path / "nope.json")
    assert backend_client.load_pidge_session() is None
