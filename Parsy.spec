# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

ROOT = Path(SPECPATH).resolve()
APP_NAME = "Parsy"

datas = [
    (str(ROOT / "app.py"), "."),
    (str(ROOT / "assets" / "parsy.ico"), "assets"),
    (str(ROOT / "assets" / "parsy.png"), "assets"),
]
binaries = []
hiddenimports = [
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "streamlit.web.cli",
    "streamlit.web.bootstrap",
    "clr",
    "pythonnet",
    "advisor",
    "history",
    "updater",
]

for package in ("streamlit", "demoparser2", "plotly"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

datas += collect_data_files("webview")
datas += collect_data_files("altair")

for distribution in (
    "streamlit",
    "pywebview",
    "demoparser2",
    "plotly",
    "pandas",
    "numpy",
    "pyarrow",
    "altair",
    "tornado",
    "bottle",
    "pythonnet",
    "clr-loader",
    "proxy-tools",
):
    try:
        datas += copy_metadata(distribution)
    except Exception:
        pass

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "cefpython3"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "parsy.ico"),
    version=str(ROOT / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
