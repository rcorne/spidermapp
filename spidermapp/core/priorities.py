from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from spidermapp.core import history, recommendations, stats, url_utils
from spidermapp.core.models import Issue

# The "Hoy" view: a single priority feed spanning every audited site, ranked
# by severity then reach — not a per-site drill-down. Reuses the crawl
# history already saved to disk (~/.spidermapp/history/) rather than adding
# a second "sites" concept; a "site" here just means the most recent full
# crawl saved for a given domain.

_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


@dataclass
class Priority:
    site: str
    title: str
    why: str
    fix_step: str
    severity: str
    affected_pages: int
    code: str
    snapshot_path: Path


def latest_full_snapshot_per_site(history_dir: Path = history.HISTORY_DIR) -> list[dict]:
    """One entry per site (registrable domain) — the most recent crawl that
    saved full page data, skipping comparison-only snapshots. Relies on
    list_all_snapshots() already being sorted newest-first."""
    seen: set[str] = set()
    latest: list[dict] = []
    for entry in history.list_all_snapshots(history_dir):
        if not entry["has_full"]:
            continue
        domain = url_utils.strip_www(url_utils.registrable_domain(entry["seed_url"])) or entry["seed_url"]
        if domain in seen:
            continue
        seen.add(domain)
        latest.append({**entry, "domain": domain})
    return latest


def gather_today_priorities(limit_per_site: int = 6, history_dir: Path = history.HISTORY_DIR) -> list[Priority]:
    """Cross-site ranked list: every site's top opportunities, merged and
    sorted by severity then how many pages each affects — the same question
    an analyst asks first thing each day: what matters most right now,
    across every client, not per site."""
    priorities: list[Priority] = []
    for entry in latest_full_snapshot_per_site(history_dir):
        result = history.load_full_crawl(entry["path"])
        if result is None:
            continue
        for opp in stats.find_opportunities(result.pages, limit=limit_per_site):
            rec = recommendations.get_recommendation(Issue(opp.category, opp.severity, opp.code, ""))
            priorities.append(
                Priority(
                    site=entry["domain"],
                    title=rec.title,
                    why=rec.why,
                    fix_step=rec.fix_steps[0] if rec.fix_steps else "",
                    severity=opp.severity.value,
                    affected_pages=opp.affected_pages,
                    code=opp.code,
                    snapshot_path=entry["path"],
                )
            )

    priorities.sort(key=lambda p: (_SEVERITY_ORDER.get(p.severity, 3), -p.affected_pages))
    return priorities
