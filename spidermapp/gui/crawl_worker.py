from __future__ import annotations

import asyncio
import subprocess
import sys
import threading

from PySide6.QtCore import QThread, Signal

from spidermapp.core import crawler
from spidermapp.core.models import CrawlConfig, CrawlResult, PageResult


class CrawlWorker(QThread):
    page_found = Signal(object)  # PageResult
    progress = Signal(int, int)  # done, max_pages
    status_changed = Signal(str)  # human-readable phase / current URL
    crawl_finished = Signal(object)  # CrawlResult
    crawl_error = Signal(str)

    def __init__(self, config: CrawlConfig, prevent_sleep: bool = True, parent=None):
        super().__init__(parent)
        self.config = config
        self._prevent_sleep = prevent_sleep
        self._stop_event = threading.Event()
        self._caffeinate: subprocess.Popen | None = None

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        self._start_caffeinate()
        try:
            result = asyncio.run(self._run_crawl())
            self.crawl_finished.emit(result)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user via the GUI
            self.crawl_error.emit(str(exc))
        finally:
            self._stop_caffeinate()

    def _start_caffeinate(self) -> None:
        """The OS suspends every process, this one included, when the
        machine sleeps — there's no way for an app to keep running through
        that. What `caffeinate` does instead is ask macOS not to sleep in
        the first place while it's running, so a laptop lid closing
        mid-crawl doesn't cut it off. `-s` (don't sleep on AC) + `-i`
        (don't idle-sleep) rather than `-d`, since there's no need to keep
        the display itself on for a background crawl."""
        if not self._prevent_sleep or sys.platform != "darwin":
            return
        try:
            self._caffeinate = subprocess.Popen(
                ["caffeinate", "-s", "-i"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except (OSError, FileNotFoundError):
            self._caffeinate = None

    def _stop_caffeinate(self) -> None:
        if self._caffeinate is None:
            return
        self._caffeinate.terminate()
        try:
            self._caffeinate.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._caffeinate.kill()
        self._caffeinate = None

    async def _run_crawl(self) -> CrawlResult:
        def on_page(page: PageResult) -> None:
            self.page_found.emit(page)

        def on_progress(done: int, total: int) -> None:
            self.progress.emit(done, total)

        def on_status(message: str) -> None:
            self.status_changed.emit(message)

        return await crawler.crawl(
            self.config,
            on_page=on_page,
            on_progress=on_progress,
            stop_flag=self._stop_event.is_set,
            on_status=on_status,
        )
