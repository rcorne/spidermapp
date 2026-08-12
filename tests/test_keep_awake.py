import subprocess

from spidermapp.core import keep_awake
from spidermapp.core.keep_awake import KeepAwake


class _FakeProcess:
    def __init__(self):
        self.terminated = False

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


def test_macos_spawns_caffeinate_and_cleans_up(monkeypatch):
    monkeypatch.setattr(keep_awake.sys, "platform", "darwin")
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    guard = KeepAwake()
    guard.start()
    assert captured["cmd"] == ["caffeinate", "-s", "-i"]
    assert guard.active

    guard.stop()
    assert not guard.active


def test_windows_sets_and_clears_execution_state(monkeypatch):
    monkeypatch.setattr(keep_awake.sys, "platform", "win32")
    calls: list[int] = []

    class _FakeKernel32:
        @staticmethod
        def SetThreadExecutionState(flags):  # noqa: N802 - mirrors the Win32 name
            calls.append(flags)
            return 1

    class _FakeWindll:
        kernel32 = _FakeKernel32()

    monkeypatch.setattr(keep_awake.ctypes, "windll", _FakeWindll(), raising=False)

    guard = KeepAwake()
    guard.start()
    assert calls == [keep_awake._ES_CONTINUOUS | keep_awake._ES_SYSTEM_REQUIRED]
    assert guard.active

    guard.stop()
    # Clearing back to CONTINUOUS alone restores normal idle timers.
    assert calls[-1] == keep_awake._ES_CONTINUOUS
    assert not guard.active


def test_linux_is_a_noop(monkeypatch):
    monkeypatch.setattr(keep_awake.sys, "platform", "linux")

    def fake_popen(cmd, **kwargs):
        raise AssertionError("must not shell out on Linux")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    guard = KeepAwake()
    guard.start()
    assert not guard.active
    guard.stop()  # must not raise


def test_missing_caffeinate_binary_is_tolerated(monkeypatch):
    monkeypatch.setattr(keep_awake.sys, "platform", "darwin")

    def fake_popen(cmd, **kwargs):
        raise FileNotFoundError("no caffeinate here")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    guard = KeepAwake()
    guard.start()  # failing to prevent sleep must not kill the crawl
    assert not guard.active


def test_windows_api_failure_is_tolerated(monkeypatch):
    monkeypatch.setattr(keep_awake.sys, "platform", "win32")

    class _Boom:
        @property
        def kernel32(self):
            raise OSError("no kernel32")

    monkeypatch.setattr(keep_awake.ctypes, "windll", _Boom(), raising=False)

    guard = KeepAwake()
    guard.start()
    assert not guard.active


def test_start_is_idempotent(monkeypatch):
    monkeypatch.setattr(keep_awake.sys, "platform", "darwin")
    spawns = {"n": 0}

    def fake_popen(cmd, **kwargs):
        spawns["n"] += 1
        return _FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    guard = KeepAwake()
    guard.start()
    guard.start()
    assert spawns["n"] == 1


def test_stop_without_start_is_safe():
    KeepAwake().stop()
