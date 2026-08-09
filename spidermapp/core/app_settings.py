from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

SETTINGS_PATH = Path.home() / ".spidermapp" / "settings.json"

DEFAULT_USER_AGENT = "PidgeBot/0.1 (+https://example.invalid/bot)"


@dataclass
class AppSettings:
    default_max_pages: int = 500
    default_max_depth: int = 10
    default_concurrency: int = 8
    default_render_js: bool = False
    # Advanced crawl options, consolidated into Archivo → Preferencias so
    # every setting lives in one place instead of being scattered across
    # menus.
    default_respect_robots: bool = True
    default_include_subdomains: bool = False
    default_user_agent: str = DEFAULT_USER_AGENT
    default_max_url_length: int = 0
    default_request_timeout: float = 15.0
    default_exclude_patterns: list[str] = field(default_factory=list)
    default_priority_urls: list[str] = field(default_factory=list)
    default_limit_to_start_folder: bool = False
    default_follow_nofollow: bool = True
    default_max_query_params: int = 0
    default_max_links_per_page: int = 0
    # macOS suspends every process, including this one, when the machine
    # sleeps — there's no way around that from inside the app. What we CAN
    # do is ask the OS not to sleep while a crawl is running (via
    # `caffeinate`), so a laptop lid closing mid-crawl doesn't pause it.
    default_prevent_sleep: bool = True
    # pidge_server — the backend for accounts + chat. Defaults to a local
    # instance; point it at wherever the team actually deploys the server.
    backend_url: str = "http://127.0.0.1:8000"


def load_settings(path: Path = SETTINGS_PATH) -> AppSettings:
    defaults = asdict(AppSettings())
    if not path.exists():
        return AppSettings()
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return AppSettings()
    merged = {**defaults, **{k: v for k, v in data.items() if k in defaults}}
    return AppSettings(**merged)


def save_settings(settings: AppSettings, path: Path = SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2))
