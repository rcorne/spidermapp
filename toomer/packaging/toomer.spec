# -*- mode: python ; coding: utf-8 -*-
# Un spec para ambas plataformas: macOS produce Toomer.app, Windows Toomer.exe.
# PyInstaller solo compila para el SO donde corre: el .exe lo genera el runner
# windows-latest de .github/workflows/build-toomer.yml.
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

PROJECT_ROOT = os.path.join(SPECPATH, "..")
IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"
ICON_PATH = (os.path.join(SPECPATH, "icon", "Toomer.icns") if IS_MACOS
             else os.path.join(SPECPATH, "icon", "Toomer.ico") if IS_WINDOWS else None)

datas = [(os.path.join(PROJECT_ROOT, "toomer", "assets"), os.path.join("toomer", "assets"))]
binaries = []
hiddenimports = collect_submodules("scipy.special") + collect_submodules("googleapiclient") + ["openpyxl", "lxml", "bs4"]
for pkg in ("googleapiclient",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis([os.path.join(PROJECT_ROOT, "toomer", "main.py")], pathex=[PROJECT_ROOT], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[],
             excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtMultimedia",
                       "PySide6.QtCharts", "PySide6.QtQml", "PySide6.QtQuick", "tkinter", "matplotlib", "IPython"],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Toomer", debug=False, strip=False, upx=False,
          console=False, icon=ICON_PATH)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Toomer")

if IS_MACOS:
    app = BUNDLE(coll, name="Toomer.app", icon=ICON_PATH, bundle_identifier="com.toomer.app",
                 info_plist={"CFBundleName": "Toomer", "CFBundleDisplayName": "Toomer",
                             "CFBundleShortVersionString": "1.0.0", "CFBundleVersion": "1.0.0",
                             "NSHighResolutionCapable": True, "NSHumanReadableCopyright": "Toomer"})
