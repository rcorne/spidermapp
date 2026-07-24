from __future__ import annotations

import os
from pathlib import Path

# Every setting here has a workable local default so `uvicorn
# pidge_server.main:app` runs out of the box for development/testing.
# Deploying for real, multi-machine use means overriding at least
# JWT_SECRET (and DATABASE_URL, if not using the default local SQLite
# file) via environment variables wherever the server actually runs.
DATA_DIR = Path(os.environ.get("PIDGE_DATA_DIR", Path.home() / ".pidge_server"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get("PIDGE_DATABASE_URL", f"sqlite:///{DATA_DIR / 'pidge.db'}")

JWT_SECRET = os.environ.get("PIDGE_JWT_SECRET", "dev-only-insecure-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MINUTES = int(os.environ.get("PIDGE_JWT_EXPIRES_MINUTES", "43200"))  # 30 days

DEFAULT_CHAT_CHANNEL = "general"
