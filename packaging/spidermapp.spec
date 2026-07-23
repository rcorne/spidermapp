# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.hooks import collect_all

PROJECT_ROOT = os.path.join(SPECPATH, "..")
ICON_PATH = os.path.join(SPECPATH, "icon", "Spidermapp.icns")

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
    name="Spidermapp",
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
    name="Spidermapp",
)

app = BUNDLE(
    coll,
    name="Spidermapp.app",
    icon=ICON_PATH,
    bundle_identifier="com.spidermapp.seoaudit",
    info_plist={
        "CFBundleName": "Spidermapp",
        "CFBundleDisplayName": "Spidermapp",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Spidermapp",
    },
)
