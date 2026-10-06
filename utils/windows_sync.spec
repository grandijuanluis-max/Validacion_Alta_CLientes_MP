# -*- mode: python ; coding: utf-8 -*-
# Build desde carpeta utils:  pyinstaller --clean windows_sync.spec
import os

from PyInstaller.utils.hooks import collect_submodules

UTILS_DIR = SPECPATH
ROOT_DIR = os.path.dirname(UTILS_DIR)

_modulos_hidden = collect_submodules("modulos")

a = Analysis(
    [
        os.path.join(UTILS_DIR, "windows_sync.py"),
        os.path.join(UTILS_DIR, "dbi_clientes.py"),
        os.path.join(UTILS_DIR, "ventas_importer.py"),
        os.path.join(UTILS_DIR, "dbi_clientes_loader.py"),
        os.path.join(UTILS_DIR, "ventas_importer_loader.py"),
    ],
    pathex=[UTILS_DIR, ROOT_DIR],
    binaries=[],
    datas=[
        (os.path.join(UTILS_DIR, "windows_sync_config.json.example"), "."),
    ],
    hiddenimports=_modulos_hidden
    + [
        "dbf",
        "dbi_clientes",
        "ventas_importer",
        "dbi_clientes_loader",
        "ventas_importer_loader",
        "modulos.presea_db",
        "modulos.ramos_utils",
        "modulos.cuit_utils",
        "supabase",
        "httpx",
        "httpcore",
        "anyio",
        "certifi",
        "postgrest",
        "realtime",
        "storage3",
        "supabase_auth",
        "supabase_functions",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="windows_sync",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
