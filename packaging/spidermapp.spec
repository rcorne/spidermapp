# -*- mode: python ; coding: utf-8 -*-
# One spec for both platforms: macOS produces Pidge.app (a real bundle),
# Windows produces Pidge.exe in a folder. PyInstaller can only build for the
# OS it runs on, so the Windows binary is produced by the windows-latest
# runner in .github/workflows/build.yml — never cross-compiled from a Mac.
import os
import sys

from PyInstaller.utils.hooks import collect_all

PROJECT_ROOT = os.path.join(SPECPATH, "..")

IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

# .icns is macOS-only and .ico is Windows-only; handing PyInstaller the wrong
# one fails the build rather than being ignored.
if IS_MACOS:
    ICON_PATH = os.path.join(SPECPATH, "icon", "Spidermapp.icns")
elif IS_WINDOWS:
    ICON_PATH = os.path.join(SPECPATH, "icon", "Pidge.ico")
else:
    ICON_PATH = None

datas = [(os.path.join(PROJECT_ROOT, "spidermapp", "assets"), os.path.join("spidermapp", "assets"))]
binaries = []
hiddenimports = []

for pkg in ("playwright", "pptx"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    [os.path.join(PROJECT_ROOT, "spidermapp", "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Pidge",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=ICON_PATH,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Pidge",
)

if IS_MACOS:
    app = BUNDLE(
        coll,
        name="Pidge.app",
        icon=ICON_PATH,
        bundle_identifier="com.pidge.seoaudit",
        info_plist={
            "CFBundleName": "Pidge",
            "CFBundleDisplayName": "Pidge",
            "CFBundleShortVersionString": "2.0.0",
            "CFBundleVersion": "2.0.0",
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "Pidge",
        },
    )
