from __future__ import annotations

import asyncio
import time

# Adapted from LibreCrawl's src/core/rate_limiter.py (MIT, © 2025 Phiality —
# see THIRD_PARTY_LICENSES.md). Theirs is a threading.Lock + blocking
# time.sleep, which would stall this crawler's whole event loop; this is the
# asyncio equivalent, so waiting for a slot yields to other in-flight
# requests instead of freezing them.


class RateLimiter:
    """Spaces requests evenly instead of firing a whole batch at once.

    This is the polite counterpart to the 429/503 backoff already in the
    crawler: backoff reacts *after* a site complains, this keeps the
    steady-state rate low enough that it has less to complain about.
    """

    def __init__(self, requests_per_second: float = 0.0):
        # 0 (or less) disables limiting entirely — the default, since most
        # crawls of your own site want full speed.
        self.requests_per_second = max(0.0, requests_per_second)
        self._min_interval = 1.0 / self.requests_per_second if self.requests_per_second > 0 else 0.0
        self._next_slot = 0.0
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return self._min_interval > 0.0

    async def acquire(self) -> None:
        """Wait until this caller's turn. Reserving the slot inside the lock
        (rather than sleeping inside it) is what keeps N concurrent workers
        spread across N intervals instead of all waking at once."""
        if not self.enabled:
            return
        async with self._lock:
            now = time.monotonic()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self._min_interval
        delay = slot - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)

    def update_rate(self, requests_per_second: float) -> None:
        self.requests_per_second = max(0.0, requests_per_second)
        self._min_interval = 1.0 / self.requests_per_second if self.requests_per_second > 0 else 0.0
