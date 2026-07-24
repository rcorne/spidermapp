from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket


class ChatConnectionManager:
    """In-memory registry of live websocket connections per channel. One
    process, one instance — fine for a small team's self-hosted server;
    scaling to multiple server processes would need a shared pub/sub
    (Redis, etc.) instead, out of scope for this project's size."""

    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._channels[channel].add(websocket)

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        self._channels[channel].discard(websocket)
        if not self._channels[channel]:
            self._channels.pop(channel, None)

    async def broadcast(self, channel: str, payload: dict) -> None:
        dead: list[WebSocket] = []
        for connection in self._channels.get(channel, ()):
            try:
                await connection.send_json(payload)
            except Exception:  # noqa: BLE001 - connection dropped mid-broadcast
                dead.append(connection)
        for connection in dead:
            self.disconnect(channel, connection)


manager = ChatConnectionManager()
