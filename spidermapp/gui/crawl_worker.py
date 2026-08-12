from __future__ import annotations

import asyncio
import threading

from PySide6.QtCore import QThread, Signal

from spidermapp.core import crawler
from spidermapp.core.keep_awake import KeepAwake
from spidermapp.core.models import CrawlConfig, CrawlResult, PageResult


class CrawlWorker(QThread):
    page_found = Signal(object)  # PageResult
    progress = Signal(int, int)  # done, estimated total
    status_changed = Signal(str)  # human-readable phase / current URL
    crawl_finished = Signal(object)  # CrawlResult
    crawl_error = Signal(str)

    def __init__(self, config: CrawlConfig, prevent_sleep: bool = True, resume: bool = False, parent=None):
        super().__init__(parent)
        self.config = config
        self.resume = resume
        self._prevent_sleep = prevent_sleep
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._keep_awake = KeepAwake()

    def stop(self) -> None:
        # Un-pause on the way out, or a paused crawl would never reach the
        # stop check and the thread would hang on quit.
        self._pause_event.clear()
        self._stop_event.set()

    def pause(self) -> None:
        self._pause_event.set()

    def resume_crawl(self) -> None:
        self._pause_event.clear()

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    def run(self) -> None:
        if self._prevent_sleep:
            self._keep_awake.start()
        try:
            result = asyncio.run(self._run_crawl())
            self.crawl_finished.emit(result)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user via the GUI
            self.crawl_error.emit(str(exc))
        finally:
            self._keep_awake.stop()

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
            pause_flag=self._pause_event.is_set,
            resume=self.resume,
        )
