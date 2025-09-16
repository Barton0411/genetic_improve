# -*- mode: python ; coding: utf-8 -*-
# Windows OneDir 打包配置 - 优化启动速度

import sys
from pathlib import Path

# 获取项目根目录
project_root = Path.cwd()

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # 添加资源文件
        ('gui/resources', 'gui/resources'),
        # 添加其他必要的数据文件夹
        ('core', 'core'),
        ('version.py', '.'),
    ],
    hiddenimports=[
        # PyQt6 相关模块
        'PyQt6.QtCore',
        'PyQt6.QtGui', 
        'PyQt6.QtWidgets',
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtOpenGL',
        'PyQt6.QtOpenGLWidgets',
        'PyQt6.QtPrintSupport',
        'PyQt6.QtSql',
        'PyQt6.QtSvg',
        'PyQt6.QtSvgWidgets',
        
        # 数据库相关
        'sqlalchemy',
        'pymysql',
        'cryptography',
        
        # 数据处理
        'pandas',
        'numpy',
        'openpyxl',
        'xlrd',
        'xlsxwriter',
        
        # 科学计算
        'scipy',
        'scikit-learn',
        'matplotlib',
        'seaborn',
        'networkx',
        
        # 其他
        'python-pptx',
        'opencv-python',
        'Pillow',
        'requests',
        'joblib',
        
        # 项目模块
        'gui.main_window',
        'gui.login_dialog', 
        'gui.splash_screen',
        'core.matching.complete_mating_executor',
        'core.grouping.group_manager',
        'aliyun_login_module.login_service',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除一些不需要的模块以减小大小
        'tkinter',
        'pdb',
        'doctest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# OneDir 构建 - 推荐用于Windows
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GeneticImprove',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加 .ico 图标文件
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GeneticImprove',
)