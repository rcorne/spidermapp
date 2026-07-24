from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from pidge_server import models, security
from pidge_server.db import get_session

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    session: Session = Depends(get_session),
) -> models.User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token de sesión.")
    try:
        payload = security.decode_token(credentials.credentials)
    except security.InvalidToken as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado.") from exc

    user = session.get(models.User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no encontrado.")
    return user


def get_user_from_token(token: str, session: Session) -> Optional[models.User]:
    """Same lookup as get_current_user, but callable outside FastAPI's
    dependency injection — the websocket endpoint receives its token as a
    query param, not an Authorization header, so it can't use Depends()."""
    try:
        payload = security.decode_token(token)
    except security.InvalidToken:
        return None
    return session.get(models.User, int(payload["sub"]))
