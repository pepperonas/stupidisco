# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['stupidisco.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.png', '.')],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='stupidisco',
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
    icon=['icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='stupidisco',
)
app = BUNDLE(
    coll,
    name='stupidisco.app',
    icon='icon.icns',
    bundle_identifier='io.celox.stupidisco',
    version='0.0.8',
    info_plist={
        'NSMicrophoneUsageDescription': 'stupidisco benötigt Mikrofonzugriff für die Live-Transkription von Interview-Fragen.',
        'NSHighResolutionCapable': True,
        'CFBundleShortVersionString': '0.0.8',
    },
)
