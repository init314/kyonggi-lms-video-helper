# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import importlib.util


ROOT = Path(SPECPATH)
SRC_DIR = ROOT / "src"


block_cipher = None
HAS_TORCH = importlib.util.find_spec("torch") is not None


a = Analysis(
    [str(SRC_DIR / "main.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=[
        (str(ROOT / "licenses" / "study-ssalmeok-LICENSE.txt"), "licenses"),
        (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
    ],
    hiddenimports=[
        "faster_whisper",
        "transformers",
        "accelerate",
        "safetensors",
    ] + (["torch"] if HAS_TORCH else []),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "IPython",
        "matplotlib",
        "rich",
        "tensorflow",
        "typer",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)


pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StudySsalmeok",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)


coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="StudySsalmeok",
)
