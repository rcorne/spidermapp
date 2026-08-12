from spidermapp.core.models import CrawlConfig
from spidermapp.gui.crawl_worker import CrawlWorker


def _worker(**kwargs):
    return CrawlWorker(CrawlConfig(seed_url="https://example.test/"), **kwargs)


def test_keep_awake_started_and_stopped_around_the_crawl(monkeypatch):
    """Sleep prevention should bracket the crawl: on before it starts, off
    once it's done, even though the crawl itself fails here."""
    events: list[str] = []
    worker = _worker(prevent_sleep=True)
    monkeypatch.setattr(worker._keep_awake, "start", lambda: events.append("start"))
    monkeypatch.setattr(worker._keep_awake, "stop", lambda: events.append("stop"))
    monkeypatch.setattr(worker, "_run_crawl", None)  # makes asyncio.run raise

    worker.run()
    assert events == ["start", "stop"]


def test_keep_awake_skipped_when_disabled(monkeypatch):
    events: list[str] = []
    worker = _worker(prevent_sleep=False)
    monkeypatch.setattr(worker._keep_awake, "start", lambda: events.append("start"))
    monkeypatch.setattr(worker._keep_awake, "stop", lambda: events.append("stop"))
    monkeypatch.setattr(worker, "_run_crawl", None)

    worker.run()
    assert "start" not in events


def test_pause_and_resume_toggle_the_flag():
    worker = _worker()
    assert not worker.is_paused
    worker.pause()
    assert worker.is_paused
    worker.resume_crawl()
    assert not worker.is_paused


def test_stop_also_clears_pause():
    """A paused crawl still has to be stoppable — otherwise it never reaches
    the stop check and quitting the app hangs on the thread."""
    worker = _worker()
    worker.pause()
    worker.stop()
    assert not worker.is_paused
    assert worker._stop_event.is_set()


def test_resume_flag_is_passed_through():
    assert _worker(resume=True).resume is True
    assert _worker().resume is False
