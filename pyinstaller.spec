# -*- mode: python ; coding: utf-8 -*-
import functools
import os
import sys

block_cipher = None

# Корень проекта (папка со spec-файлом)
ROOT_DIR = os.path.dirname(os.path.abspath(SPECPATH))

# Версия приложения — единый источник истины (src/version.py)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.version import APP_NAME, APP_VERSION, APP_VERSION_TUPLE

# Set custom distpath for output
distpath = os.path.join(ROOT_DIR, 'dist')

Analysis = functools.partial(Analysis, distpath=distpath)

# --- Ресурс версии для свойств EXE в Windows ---
# Файл генерируется из APP_VERSION, чтобы номер релиза не дублировался вручную
build_dir = os.path.join(ROOT_DIR, 'build')
os.makedirs(build_dir, exist_ok=True)
version_file = os.path.join(build_dir, 'version_info.txt')

with open(version_file, 'w', encoding='utf-8') as f:
    f.write(f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={APP_VERSION_TUPLE},
    prodvers={APP_VERSION_TUPLE},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', '{APP_NAME}'),
         StringStruct('FileDescription', 'REST API коннектор для PostgreSQL'),
         StringStruct('FileVersion', '{APP_VERSION}'),
         StringStruct('InternalName', '{APP_NAME}'),
         StringStruct('OriginalFilename', '{APP_NAME}.exe'),
         StringStruct('ProductName', '{APP_NAME}'),
         StringStruct('ProductVersion', '{APP_VERSION}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""")

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
        'src.version',
        'src.api',
        'src.api.routes',
        'src.api.database',
        'src.api.connections',
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

# Onefile-сборка: один самодостаточный EXE (библиотеки и ресурсы внутри).
# При запуске распаковываются во временную папку, пользовательский конфиг
# и app.log остаются рядом с EXE (get_base_dir() → Path(sys.executable).parent).
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
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
    version=version_file,
)
