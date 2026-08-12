import asyncio
import time

from spidermapp.core.rate_limiter import RateLimiter


def test_disabled_by_default():
    limiter = RateLimiter()
    assert not limiter.enabled


async def test_acquire_is_a_noop_when_disabled():
    limiter = RateLimiter(0)
    start = time.monotonic()
    for _ in range(5):
        await limiter.acquire()
    assert time.monotonic() - start < 0.05


async def test_spaces_sequential_calls_by_the_interval():
    limiter = RateLimiter(requests_per_second=20)  # 50ms apart
    start = time.monotonic()
    for _ in range(3):
        await limiter.acquire()
    elapsed = time.monotonic() - start
    # First call is free, the next two each wait one interval.
    assert elapsed >= 0.09


async def test_concurrent_callers_are_spread_not_bunched():
    """The whole point of reserving slots under the lock: N workers hitting
    acquire() at once should come out staggered, not all at t=0."""
    limiter = RateLimiter(requests_per_second=50)  # 20ms apart
    stamps: list[float] = []

    async def worker():
        await limiter.acquire()
        stamps.append(time.monotonic())

    start = time.monotonic()
    await asyncio.gather(*(worker() for _ in range(4)))

    assert len(stamps) == 4
    # Last one should be ~3 intervals out, not immediate.
    assert max(stamps) - start >= 0.05


async def test_update_rate_takes_effect():
    limiter = RateLimiter(0)
    assert not limiter.enabled
    limiter.update_rate(10)
    assert limiter.enabled
    limiter.update_rate(0)
    assert not limiter.enabled
