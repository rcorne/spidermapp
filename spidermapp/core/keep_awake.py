from __future__ import annotations

import ctypes
import subprocess
import sys

# Keeping the machine awake for the duration of a crawl, per platform.
#
# No process can keep *running* through a real system sleep — that's the OS
# suspending everything, and an app can't opt out. What it can do is ask the
# OS not to sleep in the first place while work is in flight. macOS exposes
# that as the `caffeinate` command; Windows as SetThreadExecutionState.
# (Crawl checkpoints in core/checkpoint.py cover the case where the machine
# sleeps anyway — belt and braces.)

# Windows ES_* flags (winbase.h). CONTINUOUS makes the request stick until
# it's explicitly cleared, rather than resetting the idle timer once.
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


class KeepAwake:
    """Best-effort "don't sleep while I work". Never raises: failing to
    prevent sleep must not take a crawl down with it."""

    def __init__(self) -> None:
        self._caffeinate: subprocess.Popen | None = None
        self._windows_state_set = False

    @property
    def active(self) -> bool:
        return self._caffeinate is not None or self._windows_state_set

    def start(self) -> None:
        if self.active:
            return
        if sys.platform == "darwin":
            self._start_macos()
        elif sys.platform == "win32":
            self._start_windows()
        # Linux has no single portable equivalent (it depends on the desktop
        # environment's idle inhibitor), so it's a deliberate no-op there.

    def stop(self) -> None:
        if self._caffeinate is not None:
            self._stop_macos()
        if self._windows_state_set:
            self._stop_windows()

    # -- macOS ---------------------------------------------------------

    def _start_macos(self) -> None:
        # -s: don't sleep on AC power. -i: don't idle-sleep. Deliberately not
        # -d — a background crawl has no reason to hold the display on.
        try:
            self._caffeinate = subprocess.Popen(
                ["caffeinate", "-s", "-i"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, ValueError):
            self._caffeinate = None

    def _stop_macos(self) -> None:
        process, self._caffeinate = self._caffeinate, None
        if process is None:
            return
        try:
            process.terminate()
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
        except OSError:
            pass

    # -- Windows -------------------------------------------------------

    def _start_windows(self) -> None:
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS | _ES_SYSTEM_REQUIRED)
            self._windows_state_set = True
        except (AttributeError, OSError):
            self._windows_state_set = False

    def _stop_windows(self) -> None:
        self._windows_state_set = False
        try:
            # Clearing the flags restores the machine's normal idle timers.
            ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
        except (AttributeError, OSError):
            pass
