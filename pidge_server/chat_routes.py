from __future__ import annotations

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from pidge_server import models, schemas
from pidge_server.db import SessionLocal, get_session
from pidge_server.deps import get_current_user, get_user_from_token
from pidge_server.ws_manager import manager

router = APIRouter(tags=["chat"])


@router.get("/chat/{channel}/history", response_model=list[schemas.ChatMessageOut])
def chat_history(
    channel: str,
    limit: int = Query(default=50, le=200),
    session: Session = Depends(get_session),
    _user: models.User = Depends(get_current_user),
) -> list[models.ChatMessage]:
    rows = session.scalars(
        select(models.ChatMessage)
        .where(models.ChatMessage.channel == channel)
        .order_by(models.ChatMessage.created_at.desc())
        .limit(limit)
    ).all()
    return list(reversed(rows))


@router.websocket("/ws/chat/{channel}")
async def chat_socket(websocket: WebSocket, channel: str, token: str = Query(...)) -> None:
    session = SessionLocal()
    try:
        user = get_user_from_token(token, session)
        if user is None:
            await websocket.close(code=4401)
            return

        await manager.connect(channel, websocket)
        try:
            while True:
                data = await websocket.receive_json()
                text = str(data.get("text", "")).strip()[:4000]
                if not text:
                    continue
                message = models.ChatMessage(channel=channel, author_id=user.id, author_name=user.display_name, text=text)
                session.add(message)
                session.commit()
                session.refresh(message)
                await manager.broadcast(
                    channel,
                    {
                        "id": message.id,
                        "channel": message.channel,
                        "author_id": message.author_id,
                        "author_name": message.author_name,
                        "text": message.text,
                        "created_at": message.created_at,
                    },
                )
        except WebSocketDisconnect:
            pass
        finally:
            manager.disconnect(channel, websocket)
    finally:
        session.close()
