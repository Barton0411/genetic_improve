# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('gui', 'gui'),
        ('core', 'core'),
        ('utils', 'utils'),
        ('config', 'config'),
        ('templates', 'templates'),
        ('*.mp4', '.'),
        ('*.jpg', '.'),
        ('*.ico', '.'),
    ],
    hiddenimports=[
        'json',
        'pandas',
        'numpy',
        'sqlalchemy',
        'sqlalchemy.sql.default_comparator',
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'cv2',
        'pathlib',
        'datetime',
        'shutil',
        'warnings',
        'traceback',
        'time',
        'openpyxl',
        'xlrd',
        'pymysql',
        'cryptography',
        'requests',
        'bs4',
        'lxml',
        'scipy',
        'sklearn',
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
    name='genetic_improve',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 改为 True 以便查看错误信息
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='genetic_improve',
)
