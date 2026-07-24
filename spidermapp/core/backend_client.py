from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

# The desktop-side client for pidge_server (see pidge_server/ at the repo
# root). REST calls (signup/login/oauth-link/history) go through this
# module; the live chat websocket connection is handled separately by
# spidermapp/gui/chat_view.py's background QThread, since it needs its own
# asyncio event loop.

PIDGE_SESSION_PATH = Path.home() / ".spidermapp" / "pidge_session.json"


class BackendError(Exception):
    pass


@dataclass
class PidgeUser:
    id: int
    email: str
    display_name: str


@dataclass
class PidgeSession:
    token: str
    user: PidgeUser
    server_url: str


class BackendClient:
    def __init__(self, server_url: str, timeout: float = 15.0):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, json_body: dict, token: str = "") -> dict:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            response = httpx.post(f"{self.server_url}{path}", json=json_body, headers=headers, timeout=self.timeout)
        except httpx.RequestError as exc:
            raise BackendError(f"No se pudo contactar al servidor Pidge en {self.server_url}: {exc}") from exc
        if response.status_code >= 400:
            raise BackendError(_extract_detail(response))
        return response.json()

    def _get(self, path: str, token: str = "", params: Optional[dict] = None) -> dict | list:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            response = httpx.get(f"{self.server_url}{path}", headers=headers, params=params, timeout=self.timeout)
        except httpx.RequestError as exc:
            raise BackendError(f"No se pudo contactar al servidor Pidge en {self.server_url}: {exc}") from exc
        if response.status_code >= 400:
            raise BackendError(_extract_detail(response))
        return response.json()

    def signup(self, email: str, password: str, display_name: str = "") -> PidgeSession:
        data = self._post("/auth/signup", {"email": email, "password": password, "display_name": display_name})
        return self._to_session(data)

    def login(self, email: str, password: str) -> PidgeSession:
        data = self._post("/auth/login", {"email": email, "password": password})
        return self._to_session(data)

    def oauth_link(self, provider: str, subject: str, email: str, display_name: str = "") -> PidgeSession:
        data = self._post(
            "/auth/oauth/link",
            {"provider": provider, "subject": subject, "email": email, "display_name": display_name},
        )
        return self._to_session(data)

    def chat_history(self, channel: str, token: str, limit: int = 50) -> list[dict]:
        return self._get(f"/chat/{channel}/history", token=token, params={"limit": limit})

    def _to_session(self, data: dict) -> PidgeSession:
        user = PidgeUser(**data["user"])
        return PidgeSession(token=data["token"], user=user, server_url=self.server_url)


def _extract_detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
        if detail:
            return str(detail)
    except (json.JSONDecodeError, ValueError):
        pass
    return f"El servidor respondió {response.status_code}."


def save_pidge_session(session: PidgeSession) -> None:
    PIDGE_SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    PIDGE_SESSION_PATH.write_text(
        json.dumps(
            {
                "token": session.token,
                "server_url": session.server_url,
                "user": {"id": session.user.id, "email": session.user.email, "display_name": session.user.display_name},
            },
            indent=2,
        )
    )
    os.chmod(PIDGE_SESSION_PATH, 0o600)


def load_pidge_session() -> Optional[PidgeSession]:
    if not PIDGE_SESSION_PATH.exists():
        return None
    try:
        data = json.loads(PIDGE_SESSION_PATH.read_text())
        return PidgeSession(token=data["token"], user=PidgeUser(**data["user"]), server_url=data["server_url"])
    except (json.JSONDecodeError, OSError, KeyError, TypeError):
        return None


def clear_pidge_session() -> None:
    if PIDGE_SESSION_PATH.exists():
        PIDGE_SESSION_PATH.unlink()
