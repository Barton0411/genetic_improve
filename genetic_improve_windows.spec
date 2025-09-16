# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

block_cipher = None

# 获取项目根目录
ROOT_DIR = Path(SPECPATH).resolve()

# 收集所有Python模块
def collect_modules(root_path, module_name):
    """递归收集模块下的所有子模块"""
    modules = []
    module_path = root_path / module_name
    if module_path.exists():
        for item in module_path.rglob("*.py"):
            if item.name != "__init__.py":
                relative = item.relative_to(root_path)
                module = str(relative.with_suffix("")).replace(os.sep, ".")
                modules.append(module)
    return modules

# 收集所有项目模块
hidden_imports = [
    # 标准库和第三方库
    'pandas', 'numpy', 'openpyxl', 'matplotlib', 'matplotlib.backends.backend_qt5agg',
    'scipy', 'scipy.stats', 'sklearn', 'sklearn.preprocessing',
    'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PyQt6.QtMultimedia',
    'PyQt6.QtMultimediaWidgets',
    'sqlalchemy', 'sqlalchemy.sql.default_comparator',
    'cv2', 'cryptography', 'dateutil', 'networkx', 'seaborn',
    
    # 项目模块
    'gui', 'core', 'utils', 'config',
    'gui.main_window', 'gui.login_dialog', 'gui.splash_screen',
    'gui.dialogs', 'gui.progress', 'gui.worker',
    'gui.db_update_worker', 'gui.allocation_dialog',
    'gui.matching_worker', 'gui.recommendation_worker',
    'gui.simple_recommendation_worker', 'gui.auto_grouping_dialog',
    
    'core.data', 'core.data.uploader', 'core.data.processor',
    'core.data.update_manager', 'core.data.data_loader',
    
    'core.breeding_calc', 'core.breeding_calc.cow_traits_calc',
    'core.breeding_calc.bull_traits_calc', 'core.breeding_calc.index_page',
    'core.breeding_calc.mated_bull_traits_calc',
    
    'core.grouping', 'core.grouping.group_manager',
    
    'core.matching', 'core.matching.complete_mating_executor',
    'core.matching.cycle_based_matcher', 'core.matching.matrix_recommendation_generator',
    'core.matching.allocation_utils', 'core.matching.models',
    
    'core.inbreeding', 'core.inbreeding.inbreeding_page',
    'core.inbreeding.inbreeding_calculator', 'core.inbreeding.animal',
    
    'core.report', 'core.report.ppt_generator',
    
    'utils.file_manager', 'utils.database',
    'config.settings', 'config.index_library',
]

# 动态收集所有模块
for module in ['gui', 'core', 'utils', 'config']:
    hidden_imports.extend(collect_modules(ROOT_DIR, module))

# 去重
hidden_imports = list(set(hidden_imports))

a = Analysis(
    ['main.py'],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=[
        (str(ROOT_DIR / 'config'), 'config'),
        (str(ROOT_DIR / 'templates'), 'templates'),
        (str(ROOT_DIR / 'docs'), 'docs'),
        (str(ROOT_DIR / 'gui'), 'gui'),
        (str(ROOT_DIR / 'core'), 'core'),
        (str(ROOT_DIR / 'utils'), 'utils'),
        (str(ROOT_DIR / '*.mp4'), '.'),
        (str(ROOT_DIR / '*.jpg'), '.'),
        (str(ROOT_DIR / '*.ico'), '.'),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['test', 'tests', 'testing', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 单文件执行程序
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='遗传改良系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT_DIR / 'icon.ico') if (ROOT_DIR / 'icon.ico').exists() else None
)