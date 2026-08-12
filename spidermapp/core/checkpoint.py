from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from spidermapp.core import url_utils

# Inspired by LibreCrawl's crawl checkpointing (MIT, © 2025 Phiality — see
# THIRD_PARTY_LICENSES.md). Theirs writes queue state to SQLite from a
# background thread; this writes a single JSON file per site, since Pidge is
# a desktop app with one crawl at a time and no database.
#
# Why this exists: `caffeinate` only *prevents* the Mac from sleeping. It
# can't help if the machine sleeps anyway, the app is quit, or the crawl
# crashes at page 8,000 of 10,000. A checkpoint means that work isn't lost —
# the next run picks up the frontier where it stopped.

CHECKPOINT_DIR = Path.home() / ".spidermapp" / "checkpoints"

# Anything older than this is stale enough that the site has probably
# changed underneath it; resuming would mix old and new data.
MAX_AGE_SECONDS = 7 * 24 * 3600


@dataclass
class CrawlCheckpoint:
    seed_url: str
    visited: list[str] = field(default_factory=list)
    frontier: list[tuple[str, int]] = field(default_factory=list)
    pages_done: int = 0
    sitemap_total: int = 0
    saved_at: float = field(default_factory=time.time)

    @property
    def is_resumable(self) -> bool:
        """Only worth offering if there's actually pending work left."""
        return bool(self.frontier) and not self.is_stale

    @property
    def is_stale(self) -> bool:
        return (time.time() - self.saved_at) > MAX_AGE_SECONDS

    @property
    def age_seconds(self) -> float:
        return time.time() - self.saved_at


def _slug_for(seed_url: str) -> str:
    domain = url_utils.strip_www(url_utils.registrable_domain(seed_url)) or "sitio"
    return "".join(ch if ch.isalnum() or ch in "-." else "_" for ch in domain)


def checkpoint_path(seed_url: str, checkpoint_dir: Path = CHECKPOINT_DIR) -> Path:
    return checkpoint_dir / f"{_slug_for(seed_url)}.json"


def save(checkpoint: CrawlCheckpoint, checkpoint_dir: Path = CHECKPOINT_DIR) -> Path:
    """Atomic write: a checkpoint truncated by a crash mid-write is worse
    than no checkpoint at all, so build it beside the target and rename."""
    path = checkpoint_path(checkpoint.seed_url, checkpoint_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "seed_url": checkpoint.seed_url,
        "visited": checkpoint.visited,
        "frontier": [[url, depth] for url, depth in checkpoint.frontier],
        "pages_done": checkpoint.pages_done,
        "sitemap_total": checkpoint.sitemap_total,
        "saved_at": checkpoint.saved_at,
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload))
    tmp.replace(path)
    return path


def load(seed_url: str, checkpoint_dir: Path = CHECKPOINT_DIR) -> CrawlCheckpoint | None:
    path = checkpoint_path(seed_url, checkpoint_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return CrawlCheckpoint(
            seed_url=data["seed_url"],
            visited=list(data.get("visited", [])),
            frontier=[(url, int(depth)) for url, depth in data.get("frontier", [])],
            pages_done=int(data.get("pages_done", 0)),
            sitemap_total=int(data.get("sitemap_total", 0)),
            saved_at=float(data.get("saved_at", 0.0)),
        )
    except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
        # A corrupt checkpoint should never block a fresh crawl.
        return None


def clear(seed_url: str, checkpoint_dir: Path = CHECKPOINT_DIR) -> None:
    path = checkpoint_path(seed_url, checkpoint_dir)
    if path.exists():
        path.unlink()


def find_resumable(checkpoint_dir: Path = CHECKPOINT_DIR) -> list[CrawlCheckpoint]:
    """Every unfinished, non-stale crawl — used to offer a resume at launch."""
    if not checkpoint_dir.exists():
        return []
    found: list[CrawlCheckpoint] = []
    for path in sorted(checkpoint_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        candidate = load(data.get("seed_url", ""), checkpoint_dir)
        if candidate is not None and candidate.is_resumable:
            found.append(candidate)
    return sorted(found, key=lambda c: c.saved_at, reverse=True)
