from __future__ import annotations

from pathlib import Path


def default_downloads_dir() -> Path:
    """Where every export dialog starts by default. Falls back to the home
    directory on the rare setup where ~/Downloads doesn't exist."""
    downloads = Path.home() / "Downloads"
    return downloads if downloads.is_dir() else Path.home()


def default_export_path(filename: str) -> str:
    return str(default_downloads_dir() / filename)
