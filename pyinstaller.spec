# -*- mode: python ; coding: utf-8 -*-
import functools

block_cipher = None

# Set custom distpath for output
import os
distpath = os.path.join(os.path.dirname(os.path.abspath(SPECPATH)), 'dist')

Analysis = functools.partial(Analysis, distpath=distpath)

a = Analysis(
    ['src\\app.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Шаблон конфига (копируется в config/settings.json при первом запуске)
        ('config/settings.default.json', 'config'),
    ],
    hiddenimports=[
        # Внешние библиотеки
        'flask',
        'flask_cors',
        'psycopg2',
        'psycopg2._psycopg',
        'customtkinter',
        'PIL',
        'pystray',
        'cryptography',
        'cryptography.fernet',
        'pyperclip',
        # Внутренние модули проекта
        'src',
        'src.config',
        'src.api',
        'src.api.routes',
        'src.api.database',
        'src.gui',
        'src.gui.main_window',
    ],
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
    [],
    exclude_binaries=True,
    name='ApiPostgresConnector_v2',
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ApiPostgresConnector_v2',
    distpath=distpath,
)
