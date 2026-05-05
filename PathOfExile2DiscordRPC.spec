# PyInstaller spec file for poe2-rpc.
#
# Build:
#   pyinstaller PathOfExile2DiscordRPC.spec
#
# Output: dist/PathOfExile2DiscordRPC.exe (Windows --onefile binary).
# Validated downstream by F-3 (CI smoke: `validate-config --no-discord` exit 0)
# and F-4 (cold-start benchmark: p95 <= 8s).

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hiddenimports = [
    "watchdog.observers.read_directory_changes",
    "watchdog.observers.winapi",
    "pydantic_core._pydantic_core",
    "pydantic._internal._model_construction",
    "pydantic_settings.sources.providers.toml",
    "structlog._log_levels",
    "tenacity",
]
for pkg in (
    "pydantic",
    "pydantic_settings",
    "structlog",
    "watchdog",
    "tenacity",
    "pypresence",
):
    hiddenimports += collect_submodules(pkg)

a = Analysis(
    ["src/poe2_rpc/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=[("src/poe2_rpc/locations.json", "poe2_rpc")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="PathOfExile2DiscordRPC",
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
