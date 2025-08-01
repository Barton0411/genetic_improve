#!/usr/bin/env python3
"""
PyInstaller Dependencies Configuration for Genetic Improvement System
This file contains all the hidden imports and dependencies needed for building the application.
"""

# Core Third-Party Dependencies (from requirements.txt)
REQUIREMENTS = [
    'PyQt6>=6.4.0',
    'sqlalchemy>=2.0.0', 
    'pymysql>=1.0.0',
    'cryptography>=3.4.0',
    'pandas>=1.5.0',
    'numpy>=1.21.0',
    'openpyxl>=3.0.0',
    'xlrd>=2.0.0',
    'python-pptx>=0.6.21',
    'matplotlib>=3.5.0',
    'seaborn>=0.12.0',
    'networkx>=2.8.0',
    'scikit-learn>=1.0.0',
    'opencv-python>=4.5.0',
    'python-dateutil>=2.8.0',
    'xlsxwriter>=3.0.0',  # Found in imports but not in requirements.txt
    'scipy>=1.7.0',  # Found in imports but not in requirements.txt
    'joblib>=1.0.0',  # Found in imports but not in requirements.txt
    'requests>=2.25.0',  # Found in imports but not in requirements.txt
    'Pillow>=8.0.0',  # PIL import
    'cffi>=1.14.0',  # Dependency of cryptography
]

# Hidden imports for PyInstaller
HIDDEN_IMPORTS = [
    # PyQt6 modules and backends
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtMultimedia',
    'PyQt6.QtMultimediaWidgets',
    'PyQt6.sip',
    
    # Database
    'sqlalchemy',
    'sqlalchemy.ext.declarative',
    'sqlalchemy.orm',
    'sqlalchemy.pool',
    'pymysql',
    'pymysql.cursors',
    
    # Cryptography
    'cryptography',
    'cryptography.fernet',
    'cryptography.hazmat',
    'cryptography.hazmat.primitives',
    'cryptography.hazmat.backends',
    
    # Data processing
    'pandas',
    'pandas._libs',
    'pandas._libs.tslibs.timedeltas',
    'pandas._libs.tslibs.timestamps',
    'pandas._libs.tslibs.np_datetime',
    'pandas._libs.tslibs.nattype',
    'pandas._libs.window',
    'pandas._libs.window.aggregations',
    'numpy',
    'numpy.core._multiarray_umath',
    'numpy.core._dtype_ctypes',
    'numpy.random._pickle',
    
    # Excel handling
    'openpyxl',
    'openpyxl.cell._writer',
    'openpyxl.worksheet._writer',
    'openpyxl.drawing.image',
    'xlrd',
    'xlsxwriter',
    
    # PowerPoint
    'pptx',
    'pptx.chart.data',
    'pptx.enum.chart',
    'pptx.enum.shapes',
    'pptx.enum.text',
    
    # Visualization
    'matplotlib',
    'matplotlib.pyplot',
    'matplotlib.figure',
    'matplotlib.backends.backend_qt5agg',
    'matplotlib.backends.backend_qtagg',
    'matplotlib._pylab_helpers',
    'seaborn',
    'seaborn.cm',
    'seaborn.palettes',
    'seaborn.categorical',
    'seaborn.distributions',
    
    # Network analysis
    'networkx',
    'networkx.algorithms',
    'networkx.classes',
    'networkx.drawing',
    
    # Machine learning
    'sklearn',
    'sklearn.base',
    'sklearn.utils',
    'sklearn.utils._weight_vector',
    'sklearn.utils._param_validation',
    'sklearn.utils.validation',
    'sklearn.neighbors',
    'sklearn.neighbors._typedefs',
    'sklearn.neighbors._quad_tree',
    'sklearn.neighbors._ball_tree',
    'sklearn.neighbors._kd_tree',
    'sklearn.tree',
    'sklearn.tree._utils',
    'sklearn.tree._tree',
    'sklearn.ensemble',
    'sklearn.ensemble._forest',
    'sklearn.preprocessing',
    'sklearn.preprocessing._encoders',
    'sklearn.preprocessing._data',
    'sklearn.metrics',
    'sklearn.metrics.cluster',
    'sklearn.metrics._classification',
    'sklearn.cluster',
    'sklearn.decomposition',
    'sklearn.linear_model',
    'sklearn.svm',
    
    # Scientific computing
    'scipy',
    'scipy.special',
    'scipy.special._ufuncs_cxx',
    'scipy.special._ufuncs',
    'scipy.sparse',
    'scipy.sparse.linalg',
    'scipy.sparse.csgraph',
    'scipy.spatial',
    'scipy.spatial.distance',
    'scipy.spatial.transform',
    'scipy.spatial.transform._rotation_groups',
    'scipy.stats',
    'scipy.stats._continuous_distns',
    'scipy.stats._discrete_distns',
    'scipy.optimize',
    'scipy.interpolate',
    'scipy.signal',
    'scipy.linalg',
    'scipy._lib',
    'scipy._lib.messagestream',
    
    # Computer vision
    'cv2',
    
    # Image processing
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PIL.ImageQt',
    'PIL._tkinter_finder',
    
    # Other utilities
    'joblib',
    'dateutil',
    'dateutil.parser',
    'dateutil.tz',
    'requests',
    'requests.adapters',
    'requests.models',
    'cffi',
    'cffi._pycparser',
    
    # Local modules
    'gui',
    'gui.main_window',
    'gui.login_dialog',
    'gui.splash_screen',
    'gui.dialogs',
    'gui.worker',
    'gui.progress',
    'gui.matching_worker',
    'gui.recommendation_worker',
    'gui.simple_recommendation_worker',
    'gui.db_update_worker',
    'gui.auto_grouping_dialog',
    'gui.allocation_dialog',
    
    'core',
    'core.data',
    'core.data.data_loader',
    'core.data.processor',
    'core.matching',
    'core.matching.models',
    'core.matching.individual_matcher',
    'core.matching.cycle_based_matcher',
    'core.matching.recommendation_generator',
    'core.matching.matrix_recommendation_generator',
    'core.matching.simple_recommendation_generator',
    'core.matching.complete_mating_executor',
    'core.matching.allocation_utils',
    'core.matching.group_preview_updater',
    'core.grouping',
    'core.grouping.group_manager',
    'core.services',
    'core.services.mating_service',
    'core.report',
    'core.report.ppt_generator',
    'core.report.data_generator',
    'core.report.data_adapter',
    'core.report.data_preparation',
    'core.report.data_validator',
    'core.report.analysis_text_generator',
    'core.report.slide_generators',
    'core.report.slide_generators.base',
    'core.report.slide_generators.title_toc',
    'core.report.slide_generators.genetic_evaluation',
    'core.report.slide_generators.linear_score',
    'core.report.slide_generators.pedigree_analysis',
    'core.report.slide_generators.bull_usage',
    'core.reporting',
    'core.reporting.ppt',
    'core.breeding_calc',
    'core.breeding_calc.pedigree_analysis',
    'core.inbreeding',
    'core.inbreeding.inbreeding_page',
    'core.inbreeding.pedigree_visualizer',
    'core.inbreeding.wright_inbreeding',
    'core.inbreeding.pedigree_tree_widget',
    
    'utils',
    'utils.file_manager',
    
    'aliyun_login_module',
    'aliyun_login_module.auth_service',
    'aliyun_login_module.database_config',
    'aliyun_login_module.login_dialog',
]

# Data files that need to be included
DATA_FILES = [
    # Add any data files, icons, videos, etc.
    # Format: (source_path, destination_folder)
    # Example: ('resources/icons', 'resources/icons'),
    # Example: ('data/templates', 'data/templates'),
]

# Binaries that need to be included
BINARIES = [
    # Add any binary dependencies
    # Format: (source_path, destination_folder)
]

# Additional PyInstaller options
PYINSTALLER_OPTIONS = {
    'name': 'GeneticImprove',
    'onefile': False,  # Create a single folder instead of single file
    'windowed': True,  # No console window
    'icon': None,  # Add path to .ico file if available
    'clean': True,
    'noconfirm': True,
    'strip': False,
    'noupx': True,
    'console': False,
    'disable_windowed_traceback': False,
    'argv_emulation': False,
}

# Runtime hooks
RUNTIME_HOOKS = [
    # Add any runtime hooks if needed
]

# Exclude these modules to reduce size
EXCLUDES = [
    'matplotlib.tests',
    'numpy.tests',
    'pandas.tests',
    'scipy.tests',
    'sklearn.tests',
    'PyQt6.QtBluetooth',
    'PyQt6.QtDBus',
    'PyQt6.QtDesigner',
    'PyQt6.QtHelp',
    'PyQt6.QtLocation',
    'PyQt6.QtNfc',
    'PyQt6.QtPositioning',
    'PyQt6.QtQml',
    'PyQt6.QtQuick',
    'PyQt6.QtQuick3D',
    'PyQt6.QtRemoteObjects',
    'PyQt6.QtSensors',
    'PyQt6.QtSerialPort',
    'PyQt6.QtTest',
    'PyQt6.QtWebChannel',
    'PyQt6.QtWebEngine',
    'PyQt6.QtWebSockets',
    'PyQt6.QtXml',
    'tkinter',
    'test',
    'tests',
    '_pytest',
    'pytest',
]

def generate_spec_file():
    """Generate a PyInstaller spec file with all dependencies."""
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries={BINARIES},
    datas={DATA_FILES},
    hiddenimports={HIDDEN_IMPORTS},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks={RUNTIME_HOOKS},
    excludes={EXCLUDES},
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
    name='{PYINSTALLER_OPTIONS['name']}',
    debug=False,
    bootloader_ignore_signals=False,
    strip={PYINSTALLER_OPTIONS['strip']},
    upx=not {PYINSTALLER_OPTIONS['noupx']},
    console={PYINSTALLER_OPTIONS['console']},
    disable_windowed_traceback={PYINSTALLER_OPTIONS['disable_windowed_traceback']},
    argv_emulation={PYINSTALLER_OPTIONS['argv_emulation']},
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip={PYINSTALLER_OPTIONS['strip']},
    upx=not {PYINSTALLER_OPTIONS['noupx']},
    upx_exclude=[],
    name='{PYINSTALLER_OPTIONS['name']}',
)
"""
    return spec_content

if __name__ == "__main__":
    print("PyInstaller Dependencies Configuration")
    print("=" * 60)
    print(f"Total hidden imports: {len(HIDDEN_IMPORTS)}")
    print(f"Total requirements: {len(REQUIREMENTS)}")
    print(f"Total excludes: {len(EXCLUDES)}")
    
    # Generate spec file
    spec_content = generate_spec_file()
    with open('genetic_improve.spec', 'w') as f:
        f.write(spec_content)
    print("\nGenerated genetic_improve.spec file!")
    
    # Update requirements.txt
    print("\nMissing from requirements.txt:")
    print("- xlsxwriter>=3.0.0")
    print("- scipy>=1.7.0")
    print("- joblib>=1.0.0")
    print("- requests>=2.25.0")
    print("- Pillow>=8.0.0")
    print("- cffi>=1.14.0")