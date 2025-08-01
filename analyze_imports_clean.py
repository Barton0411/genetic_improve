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
    exclude_dirs = {'test', 'tests', 'other_py', '__pycache__', '.git', 'build', 'dist', '.venv', 'venv', 'env'}
    
    for py_file in root_path.rglob('*.py'):
        # Skip excluded directories
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue
        
        # Skip files in .venv
        if '.venv' in str(py_file):
            continue
            
        imports = extract_imports_from_file(py_file)
        for imp in imports:
            all_imports[imp].add(str(py_file.relative_to(root_path)))
    
    return all_imports

def get_third_party_libraries():
    """Get a comprehensive list of third-party libraries commonly used."""
    return {
        # GUI Libraries
        'PyQt6', 'PyQt5', 'PySide2', 'PySide6', 'tkinter',
        
        # Data Science & ML
        'pandas', 'numpy', 'sklearn', 'scikit-learn', 'scipy', 'seaborn', 
        'matplotlib', 'statsmodels', 'xgboost', 'lightgbm', 'catboost',
        
        # Deep Learning
        'tensorflow', 'keras', 'torch', 'torchvision', 'transformers',
        
        # Image Processing
        'cv2', 'opencv-python', 'PIL', 'Pillow', 'pillow', 'skimage', 'scikit-image',
        
        # Data Visualization
        'plotly', 'bokeh', 'altair', 'holoviews', 'networkx',
        
        # File Handling
        'openpyxl', 'xlsxwriter', 'xlrd', 'xlwt', 'python-pptx', 'pptx',
        'python-docx', 'docx', 'PyPDF2', 'pdfplumber', 'reportlab',
        
        # Database
        'pymysql', 'psycopg2', 'sqlalchemy', 'pymongo', 'redis',
        
        # Web & API
        'requests', 'urllib3', 'httpx', 'aiohttp', 'flask', 'fastapi',
        'django', 'tornado', 'bottle',
        
        # Cryptography & Security
        'cryptography', 'bcrypt', 'passlib', 'pycryptodome', 'paramiko',
        
        # Utilities
        'tqdm', 'click', 'colorama', 'python-dateutil', 'dateutil',
        'pytz', 'arrow', 'pendulum', 'humanize', 'python-dotenv',
        
        # Testing
        'pytest', 'unittest2', 'nose', 'mock', 'faker', 'hypothesis',
        
        # Serialization
        'msgpack', 'protobuf', 'avro', 'ujson', 'orjson',
        
        # System & Process
        'psutil', 'py-cpuinfo', 'GPUtil', 'pynvml',
        
        # Parallel Processing
        'joblib', 'multiprocess', 'dask', 'ray', 'celery',
        
        # Other Common Libraries
        'setuptools', 'pip', 'wheel', 'six', 'certifi', 'chardet',
        'idna', 'packaging', 'pyparsing', 'attrs', 'more-itertools',
        'zipp', 'importlib-metadata', 'importlib-resources',
        'typing-extensions', 'backports', 'future', 'configparser',
        
        # Additional libraries found in this project
        'cffi', 'pycparser', 'greenlet', 'et_xmlfile', 'jdcal',
        'kiwisolver', 'cycler', 'fonttools', 'contourpy',
        'threadpoolctl', 'pyasn1', 'rsa', 'oauthlib',
        'google', 'proto', 'grpc', 'h5py', 'tables', 'numexpr',
        'bottleneck', 'patsy', 'beautifulsoup4', 'lxml', 'html5lib',
        'nbformat', 'nbconvert', 'jupyter', 'ipython', 'notebook',
        'ipykernel', 'ipywidgets', 'qtpy', 'qdarkstyle', 'qtawesome',
        'AppKit', 'Foundation', 'Quartz', 'Carbon',
        
        # Common lowercase variants
        'pillow', 'scikit-learn', 'scikit-image', 'opencv-python',
        'python-dateutil', 'beautifulsoup4', 'google-auth',
        'google-api-python-client', 'protobuf', 'grpcio',
        'importlib-metadata', 'importlib-resources', 'typing-extensions'
    }

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
    
    third_party_libs = get_third_party_libraries()
    
    categorized = {
        'standard_library': [],
        'third_party': [],
        'local': []
    }
    
    for module in sorted(imports.keys()):
        if module in stdlib:
            categorized['standard_library'].append(module)
        elif module in third_party_libs or module.lower() in third_party_libs:
            categorized['third_party'].append(module)
        else:
            # Check if it's likely a local module
            if module in ['gui', 'core', 'utils', 'aliyun_login_module', 'scripts']:
                categorized['local'].append(module)
            else:
                # Unknown modules - likely third-party
                categorized['third_party'].append(module)
    
    return categorized

def main():
    project_root = '/Users/Shared/Files From d.localized/projects/mating/genetic_improve'
    
    print("Analyzing imports in the genetic improvement system...")
    print("=" * 80)
    
    all_imports = analyze_project_imports(project_root)
    categorized = categorize_imports(all_imports)
    
    print("\n## CRITICAL Third-Party Dependencies for PyInstaller")
    print("-" * 40)
    
    # Key dependencies that must be included
    critical_deps = [
        'PyQt6', 'pandas', 'numpy', 'sklearn', 'scipy', 'seaborn', 
        'matplotlib', 'networkx', 'cv2', 'openpyxl', 'xlsxwriter', 
        'pptx', 'PIL', 'pymysql', 'cryptography', 'joblib', 'cffi'
    ]
    
    found_critical = []
    for dep in critical_deps:
        if dep in categorized['third_party']:
            found_critical.append(dep)
            print(f"✓ {dep}")
        else:
            # Check if imported differently
            for module in categorized['third_party']:
                if module.lower() == dep.lower():
                    found_critical.append(module)
                    print(f"✓ {module} (as {dep})")
                    break
    
    print("\n## All Third-Party Dependencies")
    print("-" * 40)
    for module in sorted(set(categorized['third_party'])):
        if module not in found_critical:
            print(f"- {module}")
    
    print("\n## PyInstaller Configuration")
    print("-" * 40)
    print("# Add to your .spec file:")
    print("\nhiddenimports = [")
    
    # Core imports
    core_imports = [
        # PyQt6 modules
        'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 
        'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets',
        
        # Scientific computing
        'numpy', 'pandas', 'scipy', 'sklearn',
        'scipy.special._ufuncs_cxx',
        'scipy._lib.messagestream',
        'scipy.spatial.transform._rotation_groups',
        
        # sklearn submodules
        'sklearn.utils._weight_vector',
        'sklearn.neighbors._typedefs',
        'sklearn.neighbors._quad_tree',
        'sklearn.tree._utils',
        'sklearn.metrics.cluster',
        'sklearn.preprocessing',
        
        # Visualization
        'matplotlib', 'matplotlib.backends.backend_qt5agg',
        'seaborn', 'seaborn.cm', 'seaborn.palettes',
        'networkx', 'networkx.algorithms',
        
        # Image processing
        'cv2', 'PIL', 'PIL._tkinter_finder',
        
        # File handling
        'openpyxl', 'openpyxl.cell._writer',
        'xlsxwriter', 'pptx', 'pptx.chart.data',
        
        # Database
        'pymysql', 'cryptography',
        
        # Other
        'joblib', 'cffi', 'cffi._pycparser',
        'pandas._libs.tslibs.timedeltas',
        'pandas._libs.tslibs.timestamps',
        'numpy.core._multiarray_umath',
    ]
    
    # Add all found third-party modules
    all_hidden = core_imports + categorized['third_party']
    
    for imp in sorted(set(all_hidden)):
        print(f"    '{imp}',")
    print("]")
    
    print("\n# Add to datas:")
    print("datas = [")
    print("    # Add data files if needed")
    print("    # ('path/to/datafile', 'destination'),")
    print("]")
    
    print("\n## Summary")
    print("-" * 40)
    print(f"Total unique imports: {len(all_imports)}")
    print(f"Standard library: {len(categorized['standard_library'])}")
    print(f"Third-party: {len(set(categorized['third_party']))}")
    print(f"Local: {len(categorized['local'])}")

if __name__ == "__main__":
    main()