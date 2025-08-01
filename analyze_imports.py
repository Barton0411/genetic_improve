#!/usr/bin/env python3
import os
import re
import ast
from pathlib import Path
from collections import defaultdict

def extract_imports_from_file(file_path):
    """Extract all imports from a Python file."""
    imports = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the AST
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
    except Exception as e:
        # Fallback to regex if AST parsing fails
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Match import statements
            import_pattern = r'^import\s+([a-zA-Z_][a-zA-Z0-9_\.]*)'
            from_pattern = r'^from\s+([a-zA-Z_][a-zA-Z0-9_\.]*)\s+import'
            
            for line in content.split('\n'):
                line = line.strip()
                
                match = re.match(import_pattern, line)
                if match:
                    imports.add(match.group(1).split('.')[0])
                
                match = re.match(from_pattern, line)
                if match:
                    imports.add(match.group(1).split('.')[0])
        except:
            pass
    
    return imports

def analyze_project_imports(root_dir):
    """Analyze all Python files in the project."""
    root_path = Path(root_dir)
    all_imports = defaultdict(set)
    
    # Directories to exclude
    exclude_dirs = {'test', 'tests', 'other_py', '__pycache__', '.git', 'build', 'dist'}
    
    for py_file in root_path.rglob('*.py'):
        # Skip excluded directories
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue
        
        imports = extract_imports_from_file(py_file)
        for imp in imports:
            all_imports[imp].add(str(py_file.relative_to(root_path)))
    
    return all_imports

def categorize_imports(imports):
    """Categorize imports into standard library, third-party, and local."""
    # Standard library modules (Python 3.9+)
    stdlib = {
        'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
        'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'binhex', 'bisect', 'builtins',
        'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code', 'codecs',
        'codeop', 'collections', 'colorsys', 'compileall', 'concurrent', 'configparser',
        'contextlib', 'contextvars', 'copy', 'copyreg', 'cProfile', 'crypt', 'csv',
        'ctypes', 'curses', 'dataclasses', 'datetime', 'dbm', 'decimal', 'difflib',
        'dis', 'distutils', 'doctest', 'email', 'encodings', 'ensurepip', 'enum',
        'errno', 'faulthandler', 'fcntl', 'filecmp', 'fileinput', 'fnmatch', 'formatter',
        'fractions', 'ftplib', 'functools', 'gc', 'getopt', 'getpass', 'gettext',
        'glob', 'grp', 'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http', 'imaplib',
        'imghdr', 'imp', 'importlib', 'inspect', 'io', 'ipaddress', 'itertools', 'json',
        'keyword', 'lib2to3', 'linecache', 'locale', 'logging', 'lzma', 'mailbox',
        'mailcap', 'marshal', 'math', 'mimetypes', 'mmap', 'modulefinder', 'msilib',
        'msvcrt', 'multiprocessing', 'netrc', 'nis', 'nntplib', 'numbers', 'operator',
        'optparse', 'os', 'ossaudiodev', 'parser', 'pathlib', 'pdb', 'pickle', 'pickletools',
        'pipes', 'pkgutil', 'platform', 'plistlib', 'poplib', 'posix', 'posixpath',
        'pprint', 'profile', 'pstats', 'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc',
        'queue', 'quopri', 'random', 're', 'readline', 'reprlib', 'resource', 'rlcompleter',
        'runpy', 'sched', 'secrets', 'select', 'selectors', 'shelve', 'shlex', 'shutil',
        'signal', 'site', 'smtpd', 'smtplib', 'sndhdr', 'socket', 'socketserver', 'spwd',
        'sqlite3', 'ssl', 'stat', 'statistics', 'string', 'stringprep', 'struct', 'subprocess',
        'sunau', 'symbol', 'symtable', 'sys', 'sysconfig', 'syslog', 'tabnanny', 'tarfile',
        'telnetlib', 'tempfile', 'termios', 'test', 'textwrap', 'threading', 'time',
        'timeit', 'tkinter', 'token', 'tokenize', 'trace', 'traceback', 'tracemalloc',
        'tty', 'turtle', 'types', 'typing', 'unicodedata', 'unittest', 'urllib', 'uu',
        'uuid', 'venv', 'warnings', 'wave', 'weakref', 'webbrowser', 'winreg', 'winsound',
        'wsgiref', 'xdrlib', 'xml', 'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib',
        '_thread', 'gc'
    }
    
    # Known third-party modules in this project
    third_party = {
        'PyQt6', 'pandas', 'numpy', 'sklearn', 'scipy', 'seaborn', 'matplotlib',
        'networkx', 'cv2', 'openpyxl', 'xlsxwriter', 'pptx', 'PIL', 'pymysql',
        'cryptography', 'requests', 'urllib3', 'certifi', 'chardet', 'idna',
        'setuptools', 'pip', 'wheel', 'psutil', 'pytz', 'dateutil', 'six',
        'joblib', 'threadpoolctl', 'tqdm', 'colorama', 'click', 'flask',
        'werkzeug', 'jinja2', 'itsdangerous', 'markupsafe', 'sqlalchemy',
        'alembic', 'mako', 'greenlet', 'cffi', 'pycparser', 'bcrypt',
        'pyasn1', 'rsa', 'oauthlib', 'requests_oauthlib', 'google', 'proto',
        'grpc', 'h5py', 'tables', 'numexpr', 'bottleneck', 'patsy', 'statsmodels',
        'xgboost', 'lightgbm', 'catboost', 'tensorflow', 'keras', 'torch',
        'torchvision', 'transformers', 'datasets', 'tokenizers', 'sentencepiece',
        'sacremoses', 'nltk', 'spacy', 'gensim', 'textblob', 'pattern',
        'beautifulsoup4', 'lxml', 'html5lib', 'scrapy', 'selenium', 'pyautogui',
        'pyperclip', 'keyboard', 'mouse', 'pynput', 'plyer', 'kivy', 'kivymd',
        'reportlab', 'fpdf', 'pdfkit', 'wkhtmltopdf', 'docx', 'python', 'et_xmlfile',
        'jdcal', 'pillow', 'packaging', 'pyparsing', 'cycler', 'kiwisolver',
        'fonttools', 'contourpy', 'importlib_resources', 'zipp', 'more_itertools',
        'attrs', 'jsonschema', 'pyrsistent', 'iniconfig', 'pluggy', 'py', 'toml',
        'coverage', 'hypothesis', 'faker', 'factory_boy', 'freezegun', 'responses',
        'mock', 'parameterized', 'nose', 'behave', 'lettuce', 'sure', 'expects',
        'pyhamcrest', 'doublex', 'mamba', 'expects', 'pyshould', 'couleur',
        'steadymark', 'misaka', 'pygments', 'docutils', 'sphinx', 'alabaster',
        'babel', 'imagesize', 'snowballstemmer', 'sphinx_rtd_theme', 'recommonmark',
        'numpydoc', 'autodocsumm', 'autodoc', 'm2r', 'nbsphinx', 'nbconvert',
        'nbformat', 'jupyter', 'ipython', 'ipykernel', 'notebook', 'jupyterlab',
        'ipywidgets', 'widgetsnbextension', 'qtconsole', 'spyder', 'pyqt5',
        'pyside2', 'pyside6', 'sip', 'shiboken2', 'shiboken6', 'qdarkstyle',
        'qtpy', 'qtawesome', 'qscintilla', 'pyqtgraph', 'vispy', 'mayavi',
        'vtk', 'traits', 'traitsui', 'envisage', 'apptools', 'pyface', 'bqplot',
        'plotly', 'bokeh', 'holoviews', 'panel', 'param', 'pyviz', 'datashader',
        'colorcet', 'geoviews', 'cartopy', 'folium', 'geopy', 'shapely', 'fiona',
        'geopandas', 'rasterio', 'xarray', 'netcdf4', 'h5netcdf', 'zarr', 'dask',
        'distributed', 'pyarrow', 'fastparquet', 'sqlalchemy', 'pymongo', 'redis',
        'cassandra', 'elasticsearch', 'influxdb', 'prometheus', 'graphql', 'starlette',
        'fastapi', 'uvicorn', 'gunicorn', 'celery', 'rq', 'huey', 'schedule',
        'apscheduler', 'pendulum', 'arrow', 'maya', 'delorean', 'freezegun',
        'faker', 'mimesis', 'pytest', 'tox', 'nox', 'invoke', 'fabric', 'paramiko',
        'ansible', 'salt', 'puppet', 'chef', 'docker', 'kubernetes', 'openshift',
        'helm', 'terraform', 'pulumi', 'cloudformation', 'boto3', 'azure', 'google',
        'aliyun', 'tencentcloud', 'huaweicloud', 'baiducloud', 'jdcloud', 'ucloud'
    }
    
    categorized = {
        'standard_library': [],
        'third_party': [],
        'local': []
    }
    
    for module in sorted(imports.keys()):
        if module in stdlib:
            categorized['standard_library'].append(module)
        elif module in third_party or module.lower() in third_party:
            categorized['third_party'].append(module)
        else:
            # Check if it's likely a local module
            if module in ['gui', 'core', 'utils', 'aliyun_login_module', 'scripts']:
                categorized['local'].append(module)
            else:
                # Default to third-party for unknown modules
                categorized['third_party'].append(module)
    
    return categorized

def main():
    project_root = '/Users/Shared/Files From d.localized/projects/mating/genetic_improve'
    
    print("Analyzing imports in the genetic improvement system...")
    print("=" * 80)
    
    all_imports = analyze_project_imports(project_root)
    categorized = categorize_imports(all_imports)
    
    print("\n## Third-Party Dependencies (for PyInstaller)")
    print("-" * 40)
    for module in sorted(categorized['third_party']):
        print(f"- {module}")
        # Show first 3 files using this module
        files = list(all_imports[module])[:3]
        for f in files:
            print(f"  └─ {f}")
        if len(all_imports[module]) > 3:
            print(f"  └─ ... and {len(all_imports[module]) - 3} more files")
    
    print("\n## Standard Library Modules")
    print("-" * 40)
    print(", ".join(sorted(categorized['standard_library'])))
    
    print("\n## Local Modules")
    print("-" * 40)
    print(", ".join(sorted(categorized['local'])))
    
    print("\n## Summary")
    print("-" * 40)
    print(f"Total unique imports: {len(all_imports)}")
    print(f"Standard library: {len(categorized['standard_library'])}")
    print(f"Third-party: {len(categorized['third_party'])}")
    print(f"Local: {len(categorized['local'])}")
    
    # Create requirements for PyInstaller
    print("\n## PyInstaller Hidden Imports")
    print("-" * 40)
    hidden_imports = []
    
    # Add all third-party modules
    for module in categorized['third_party']:
        hidden_imports.append(module)
    
    # Add specific sub-modules that might be dynamically imported
    extra_imports = [
        'sklearn.utils._weight_vector',
        'sklearn.neighbors._typedefs',
        'sklearn.neighbors._quad_tree',
        'sklearn.tree._utils',
        'scipy._lib.messagestream',
        'scipy.spatial.transform._rotation_groups',
        'matplotlib.backends.backend_qt5agg',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'cv2',
        'PIL._tkinter_finder',
        'pptx.chart.data',
        'openpyxl.cell._writer',
        'pandas._libs.tslibs.timedeltas',
        'pandas._libs.tslibs.timestamps',
        'numpy.core._multiarray_umath',
        'networkx.algorithms',
        'seaborn.cm',
        'seaborn.palettes'
    ]
    
    hidden_imports.extend(extra_imports)
    
    print("hiddenimports = [")
    for imp in sorted(set(hidden_imports)):
        print(f"    '{imp}',")
    print("]")

if __name__ == "__main__":
    main()