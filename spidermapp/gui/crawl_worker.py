from __future__ import annotations

import asyncio
import threading

from PySide6.QtCore import QThread, Signal

from spidermapp.core import crawler
from spidermapp.core.models import CrawlConfig, CrawlResult, PageResult


class CrawlWorker(QThread):
    page_found = Signal(object)  # PageResult
    progress = Signal(int, int)  # done, max_pages
    crawl_finished = Signal(object)  # CrawlResult
    crawl_error = Signal(str)

    def __init__(self, config: CrawlConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        try:
            result = asyncio.run(self._run_crawl())
            self.crawl_finished.emit(result)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user via the GUI
            self.crawl_error.emit(str(exc))

    async def _run_crawl(self) -> CrawlResult:
        def on_page(page: PageResult) -> None:
            self.page_found.emit(page)

        def on_progress(done: int, total: int) -> None:
            self.progress.emit(done, total)

        return await crawler.crawl(
            self.config,
            on_page=on_page,
            on_progress=on_progress,
            stop_flag=self._stop_event.is_set,
        )
