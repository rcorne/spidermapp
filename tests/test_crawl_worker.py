import subprocess

from spidermapp.core.models import CrawlConfig
from spidermapp.gui.crawl_worker import CrawlWorker


class _FakeProcess:
    def __init__(self):
        self.terminated = False
        self.waited = False

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        self.waited = True

    def kill(self):
        pass


def test_start_caffeinate_spawns_process_on_macos(monkeypatch):
    monkeypatch.setattr("spidermapp.gui.crawl_worker.sys.platform", "darwin")
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    worker = CrawlWorker(CrawlConfig(seed_url="https://example.test/"), prevent_sleep=True)
    worker._start_caffeinate()
    assert captured["cmd"] == ["caffeinate", "-s", "-i"]
    assert worker._caffeinate is not None
    worker._stop_caffeinate()
    assert worker._caffeinate is None


def test_start_caffeinate_skipped_when_disabled(monkeypatch):
    monkeypatch.setattr("spidermapp.gui.crawl_worker.sys.platform", "darwin")

    def fake_popen(cmd, **kwargs):
        raise AssertionError("should not spawn caffeinate when prevent_sleep is False")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    worker = CrawlWorker(CrawlConfig(seed_url="https://example.test/"), prevent_sleep=False)
    worker._start_caffeinate()
    assert worker._caffeinate is None


def test_start_caffeinate_skipped_on_non_macos(monkeypatch):
    monkeypatch.setattr("spidermapp.gui.crawl_worker.sys.platform", "linux")

    def fake_popen(cmd, **kwargs):
        raise AssertionError("should not spawn caffeinate on non-macOS platforms")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    worker = CrawlWorker(CrawlConfig(seed_url="https://example.test/"), prevent_sleep=True)
    worker._start_caffeinate()
    assert worker._caffeinate is None


def test_start_caffeinate_missing_binary_is_tolerated(monkeypatch):
    monkeypatch.setattr("spidermapp.gui.crawl_worker.sys.platform", "darwin")

    def fake_popen(cmd, **kwargs):
        raise FileNotFoundError("no caffeinate")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    worker = CrawlWorker(CrawlConfig(seed_url="https://example.test/"), prevent_sleep=True)
    worker._start_caffeinate()
    assert worker._caffeinate is None
