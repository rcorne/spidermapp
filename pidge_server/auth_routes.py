from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pidge_server import models, schemas, security
from pidge_server.db import get_session
from pidge_server.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=schemas.SessionOut, status_code=status.HTTP_201_CREATED)
def signup(payload: schemas.SignupRequest, session: Session = Depends(get_session)) -> schemas.SessionOut:
    existing = session.scalar(select(models.User).where(models.User.email == payload.email))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese email.")

    user = models.User(
        email=payload.email,
        display_name=payload.display_name or payload.email.split("@")[0],
        password_hash=security.hash_password(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return schemas.SessionOut(token=security.create_token(user.id, user.email), user=user)


@router.post("/login", response_model=schemas.SessionOut)
def login(payload: schemas.LoginRequest, session: Session = Depends(get_session)) -> schemas.SessionOut:
    user = session.scalar(select(models.User).where(models.User.email == payload.email))
    if user is None or not user.password_hash or not security.verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email o contraseña incorrectos.")
    return schemas.SessionOut(token=security.create_token(user.id, user.email), user=user)


@router.post("/oauth/link", response_model=schemas.SessionOut)
def oauth_link(payload: schemas.OAuthLinkRequest, session: Session = Depends(get_session)) -> schemas.SessionOut:
    """Get-or-create a user from a provider profile the desktop client
    already verified via a real OAuth PKCE flow (see the docstring on
    OAuthLinkRequest). Links by (provider, subject) first, falling back to
    email so a user who signed up locally and later uses "Continuar con
    Google" lands on the same account instead of a duplicate."""
    user = session.scalar(
        select(models.User).where(
            models.User.oauth_provider == payload.provider,
            models.User.oauth_subject == payload.subject,
        )
    )
    if user is None:
        user = session.scalar(select(models.User).where(models.User.email == payload.email))
    if user is None:
        user = models.User(
            email=payload.email,
            display_name=payload.display_name or payload.email.split("@")[0],
        )
        session.add(user)
    user.oauth_provider = payload.provider
    user.oauth_subject = payload.subject
    session.commit()
    session.refresh(user)
    return schemas.SessionOut(token=security.create_token(user.id, user.email), user=user)


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)) -> models.User:
    return user
