# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the OpenAVC macOS menu-bar app.

Build: pyinstaller installer/menubar.spec
Output: dist/openavc-menubar/openavc-menubar

The macOS counterpart to tray.spec. build-macos.sh copies the resulting
binary + its _internal into OpenAVC.app/Contents/MacOS/.
"""

from pathlib import Path

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).parent
INSTALLER_DIR = PROJECT_ROOT / 'installer'

a = Analysis(
    [str(INSTALLER_DIR / 'menubar.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[
        'rumps',
        # rumps pulls these in dynamically via PyObjC's lazy framework loader,
        # which PyInstaller's static analysis misses.
        'objc',
        'Foundation',
        'AppKit',
        'PyObjCTools',
        'PyObjCTools.AppHelper',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'test',
        'numpy',
        'scipy',
        'matplotlib',
        'pandas',
        'PIL',
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='openavc-menubar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # menu-bar accessory app, no terminal window
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='openavc-menubar',
)
