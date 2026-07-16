from __future__ import annotations

import os
import sys

# Must run before anything touches Playwright. When the app is bundled with
# PyInstaller, Playwright's Node driver ends up inside the .app's Resources
# folder and defaults to looking for the browser next to itself
# (.../Resources/playwright/driver/package/.local-browsers/...) instead of
# the shared OS cache where `playwright install chromium` actually put it.
# Pointing PLAYWRIGHT_BROWSERS_PATH at the real cache fixes that for both
# the packaged app and a normal `python -m spidermapp.main` run (setdefault
# is a no-op if the user already set it themselves).
if sys.platform == "darwin":
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.expanduser("~/Library/Caches/ms-playwright"))
elif sys.platform.startswith("linux"):
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.expanduser("~/.cache/ms-playwright"))
elif sys.platform == "win32":
    _local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join(_local_appdata, "ms-playwright"))

from PySide6.QtWidgets import QApplication

from spidermapp.gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Spidermapp")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
