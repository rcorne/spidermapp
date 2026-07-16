from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

SETTINGS_PATH = Path.home() / ".spidermapp" / "settings.json"


@dataclass
class AppSettings:
    default_max_pages: int = 500
    default_max_depth: int = 10
    default_concurrency: int = 8
    default_render_js: bool = False


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
