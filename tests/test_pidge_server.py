import os
import tempfile

# Must run before the first `from pidge_server...` import anywhere in the
# process — config.py and db.py read these env vars at import time to pick
# the database file, so setting them up front keeps tests off the real
# ~/.pidge_server/pidge.db a developer might have from running the server
# locally.
_tmp_dir = tempfile.mkdtemp()
os.environ["PIDGE_DATA_DIR"] = _tmp_dir
os.environ["PIDGE_DATABASE_URL"] = f"sqlite:///{_tmp_dir}/test_pidge.db"
os.environ["PIDGE_JWT_SECRET"] = "test-secret-at-least-32-bytes-long-ok"

from fastapi.testclient import TestClient  # noqa: E402

from pidge_server.db import init_db  # noqa: E402
from pidge_server.main import app  # noqa: E402

init_db()
client = TestClient(app)


def _signup(email: str, password: str = "supersecret123", display_name: str = "") -> dict:
    response = client.post("/auth/signup", json={"email": email, "password": password, "display_name": display_name})
    assert response.status_code == 201, response.text
    return response.json()


def test_signup_creates_user_and_returns_token():
    data = _signup("alice@example.com", display_name="Alice")
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["display_name"] == "Alice"
    assert data["token"]


def test_signup_defaults_display_name_from_email():
    data = _signup("noname@example.com")
    assert data["user"]["display_name"] == "noname"


def test_signup_duplicate_email_conflicts():
    _signup("dup@example.com")
    response = client.post("/auth/signup", json={"email": "dup@example.com", "password": "supersecret123"})
    assert response.status_code == 409


def test_signup_rejects_short_password():
    response = client.post("/auth/signup", json={"email": "short@example.com", "password": "abc"})
    assert response.status_code == 422


def test_login_success():
    _signup("bob@example.com")
    response = client.post("/auth/login", json={"email": "bob@example.com", "password": "supersecret123"})
    assert response.status_code == 200
    assert response.json()["token"]


def test_login_wrong_password_rejected():
    _signup("carol@example.com")
    response = client.post("/auth/login", json={"email": "carol@example.com", "password": "wrongpass"})
    assert response.status_code == 401


def test_login_unknown_email_rejected():
    response = client.post("/auth/login", json={"email": "ghost@example.com", "password": "whatever123"})
    assert response.status_code == 401


def test_me_requires_token():
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user():
    data = _signup("dave@example.com", display_name="Dave")
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {data['token']}"})
    assert response.status_code == 200
    assert response.json()["email"] == "dave@example.com"


def test_oauth_link_creates_new_account():
    response = client.post(
        "/auth/oauth/link",
        json={"provider": "github", "subject": "gh-123", "email": "oauth1@example.com", "display_name": "GH User"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["display_name"] == "GH User"


def test_oauth_link_reuses_account_for_same_provider_subject():
    first = client.post(
        "/auth/oauth/link",
        json={"provider": "google", "subject": "g-999", "email": "oauth2@example.com", "display_name": "First"},
    )
    second = client.post(
        "/auth/oauth/link",
        json={"provider": "google", "subject": "g-999", "email": "oauth2@example.com", "display_name": "First"},
    )
    assert first.json()["user"]["id"] == second.json()["user"]["id"]


def test_chat_history_requires_auth():
    response = client.get("/chat/general/history")
    assert response.status_code == 401


def test_chat_websocket_broadcasts_and_persists():
    sender = _signup("sender@example.com", display_name="Sender")
    receiver = _signup("receiver@example.com", display_name="Receiver")
    channel = "test-channel"

    with client.websocket_connect(f"/ws/chat/{channel}?token={sender['token']}") as ws_sender:
        with client.websocket_connect(f"/ws/chat/{channel}?token={receiver['token']}") as ws_receiver:
            ws_sender.send_json({"text": "hola desde sender"})
            at_sender = ws_sender.receive_json()
            at_receiver = ws_receiver.receive_json()

    assert at_sender["text"] == "hola desde sender"
    assert at_sender["author_name"] == "Sender"
    assert at_receiver == at_sender

    history = client.get(f"/chat/{channel}/history", headers={"Authorization": f"Bearer {sender['token']}"})
    assert history.status_code == 200
    texts = [m["text"] for m in history.json()]
    assert "hola desde sender" in texts


def test_chat_websocket_rejects_invalid_token():
    import pytest
    import starlette.websockets

    with pytest.raises(starlette.websockets.WebSocketDisconnect):
        with client.websocket_connect("/ws/chat/general?token=not-a-real-token"):
            pass
