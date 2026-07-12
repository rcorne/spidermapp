from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from spidermapp.core.models import CrawlResult

HISTORY_DIR = Path.home() / ".spidermapp" / "history"


def _domain_key(seed_url: str) -> str:
    host = urlparse(seed_url).netloc.lower()
    return host.replace(":", "_") or "unknown"


@dataclass
class CrawlSnapshot:
    seed_url: str
    timestamp: float
    pages: dict[str, list[str]] = field(default_factory=dict)
    status_by_url: dict[str, int | None] = field(default_factory=dict)


@dataclass
class CrawlDiff:
    previous_timestamp: float
    new_issue_codes_by_url: dict[str, list[str]]
    resolved_issue_codes_by_url: dict[str, list[str]]
    new_pages: list[str]
    removed_pages: list[str]

    @property
    def new_issue_count(self) -> int:
        return sum(len(v) for v in self.new_issue_codes_by_url.values())

    @property
    def resolved_issue_count(self) -> int:
        return sum(len(v) for v in self.resolved_issue_codes_by_url.values())

    @property
    def is_empty(self) -> bool:
        return not (self.new_issue_codes_by_url or self.resolved_issue_codes_by_url or self.new_pages or self.removed_pages)


def _snapshot_from_result(result: CrawlResult, timestamp: float | None = None) -> CrawlSnapshot:
    pages = {p.url: sorted({i.code for i in p.issues}) for p in result.pages}
    status = {p.url: p.status_code for p in result.pages}
    return CrawlSnapshot(
        seed_url=result.seed_url,
        timestamp=timestamp if timestamp is not None else time.time(),
        pages=pages,
        status_by_url=status,
    )


def save_crawl(result: CrawlResult, history_dir: Path = HISTORY_DIR) -> Path:
    snapshot = _snapshot_from_result(result)
    domain_dir = history_dir / _domain_key(result.seed_url)
    domain_dir.mkdir(parents=True, exist_ok=True)
    path = domain_dir / f"{int(snapshot.timestamp * 1000)}.json"
    path.write_text(
        json.dumps(
            {
                "seed_url": snapshot.seed_url,
                "timestamp": snapshot.timestamp,
                "pages": snapshot.pages,
                "status_by_url": snapshot.status_by_url,
            },
            indent=2,
        )
    )
    return path


def list_snapshots(seed_url: str, history_dir: Path = HISTORY_DIR) -> list[Path]:
    domain_dir = history_dir / _domain_key(seed_url)
    if not domain_dir.exists():
        return []
    return sorted(domain_dir.glob("*.json"))


def load_snapshot(path: Path) -> CrawlSnapshot:
    data = json.loads(path.read_text())
    return CrawlSnapshot(**data)


def load_previous_snapshot(
    seed_url: str, before: float | None = None, history_dir: Path = HISTORY_DIR
) -> CrawlSnapshot | None:
    """Most recent saved snapshot for this domain. Pass `before` (a unix
    timestamp) to exclude a snapshot that was just saved for the crawl
    currently being compared."""
    candidates = [load_snapshot(p) for p in list_snapshots(seed_url, history_dir)]
    if before is not None:
        candidates = [s for s in candidates if s.timestamp < before]
    if not candidates:
        return None
    return max(candidates, key=lambda s: s.timestamp)


def diff_crawls(previous: CrawlSnapshot, current: CrawlResult) -> CrawlDiff:
    current_snapshot = _snapshot_from_result(current)

    new_issues: dict[str, list[str]] = {}
    resolved_issues: dict[str, list[str]] = {}
    for url in set(previous.pages) | set(current_snapshot.pages):
        prev_codes = set(previous.pages.get(url, []))
        curr_codes = set(current_snapshot.pages.get(url, []))
        added = sorted(curr_codes - prev_codes)
        removed = sorted(prev_codes - curr_codes)
        if added:
            new_issues[url] = added
        if removed:
            resolved_issues[url] = removed

    return CrawlDiff(
        previous_timestamp=previous.timestamp,
        new_issue_codes_by_url=new_issues,
        resolved_issue_codes_by_url=resolved_issues,
        new_pages=sorted(set(current_snapshot.pages) - set(previous.pages)),
        removed_pages=sorted(set(previous.pages) - set(current_snapshot.pages)),
    )
