from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OAuthLinkRequest(BaseModel):
    """The desktop app already completed a real OAuth PKCE flow directly
    against Google/GitHub/Apple (see spidermapp/core/auth.py) and holds a
    verified provider profile. This endpoint trusts that client-attested
    profile to get-or-create the matching Pidge account and mint a
    session — it does not re-run the OAuth handshake server-side."""

    provider: str
    subject: str
    email: EmailStr
    display_name: str = ""


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str

    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    token: str
    user: UserOut


class ChatMessageOut(BaseModel):
    id: int
    channel: str
    author_id: int
    author_name: str
    text: str
    created_at: float

    model_config = {"from_attributes": True}


class ChatMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
