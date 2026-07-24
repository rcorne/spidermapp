from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from pidge_server import auth_routes, chat_routes
from pidge_server.db import init_db


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Pidge Server", version="0.1.0", lifespan=_lifespan)
app.include_router(auth_routes.router)
app.include_router(chat_routes.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
