#!/usr/bin/env python3
"""
Build script for Genetic Improvement System with all dependencies
This script ensures all imports are properly included in the PyInstaller build.
"""

import os
import sys
import subprocess
from pathlib import Path

# Import the dependencies configuration
from pyinstaller_dependencies import HIDDEN_IMPORTS, DATA_FILES, BINARIES, EXCLUDES

def create_spec_file():
    """Create a comprehensive spec file with all dependencies."""
    
    spec_content = """# -*- mode: python ; coding: utf-8 -*-
# Auto-generated spec file for Genetic Improvement System

block_cipher = None

# All hidden imports discovered from the project
hiddenimports = {}

# Exclude unnecessary modules to reduce size
excludes = {}

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove duplicate entries
a.datas = list(set(a.datas))
a.binaries = list(set(a.binaries))

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GeneticImprove',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='GeneticImprove',
)

app = BUNDLE(
    coll,
    name='GeneticImprove.app',
    icon=None,
    bundle_identifier='com.genetic.improve',
    info_plist={{
        'CFBundleName': 'Genetic Improve',
        'CFBundleDisplayName': 'Genetic Improvement System',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
    }},
)
""".format(HIDDEN_IMPORTS, EXCLUDES)
    
    with open('genetic_improve_full.spec', 'w') as f:
        f.write(spec_content)
    
    print("✓ Created genetic_improve_full.spec")

def install_dependencies():
    """Install all required dependencies."""
    print("\n📦 Installing dependencies...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
    print("✓ Dependencies installed")

def build_application():
    """Build the application using PyInstaller."""
    print("\n🔨 Building application...")
    
    # Clean previous builds
    for path in ['build', 'dist']:
        if os.path.exists(path):
            import shutil
            shutil.rmtree(path)
    
    # Run PyInstaller
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        '--noconfirm',
        'genetic_improve_full.spec'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✓ Build completed successfully!")
        print(f"  Application bundle: dist/GeneticImprove.app")
    else:
        print("❌ Build failed!")
        print(result.stdout)
        print(result.stderr)
        return False
    
    return True

def verify_imports():
    """Verify that all imports are available."""
    print("\n🔍 Verifying imports...")
    
    missing = []
    for module in ['PyQt6', 'pandas', 'numpy', 'sklearn', 'scipy', 'matplotlib', 
                   'seaborn', 'networkx', 'cv2', 'openpyxl', 'xlsxwriter', 
                   'pptx', 'PIL', 'pymysql', 'cryptography', 'joblib']:
        try:
            __import__(module)
            print(f"  ✓ {module}")
        except ImportError:
            print(f"  ❌ {module} - MISSING!")
            missing.append(module)
    
    if missing:
        print(f"\n⚠️  Missing modules: {', '.join(missing)}")
        print("Please install missing dependencies before building.")
        return False
    
    return True

def create_build_instructions():
    """Create detailed build instructions."""
    instructions = """
# Build Instructions for Genetic Improvement System

## Prerequisites
1. Python 3.9 or later
2. All dependencies from requirements.txt
3. PyInstaller

## Quick Build
```bash
python3 build_with_deps.py
```

## Manual Build Steps

1. Install dependencies:
```bash
pip install -r requirements.txt
pip install pyinstaller
```

2. Create spec file:
```bash
python3 pyinstaller_dependencies.py
```

3. Build the application:
```bash
pyinstaller --clean --noconfirm genetic_improve_full.spec
```

## Troubleshooting

### Missing imports
If you get import errors, add the missing module to HIDDEN_IMPORTS in pyinstaller_dependencies.py

### Large file size
Add unnecessary modules to EXCLUDES in pyinstaller_dependencies.py

### Runtime errors
Check that all data files and resources are included in DATA_FILES

## Testing the Build
```bash
./dist/GeneticImprove.app/Contents/MacOS/GeneticImprove
```

## Creating DMG (macOS)
```bash
hdiutil create -volname "Genetic Improve" -srcfolder dist/GeneticImprove.app -ov -format UDZO GeneticImprove.dmg
```
"""
    
    with open('BUILD_INSTRUCTIONS.md', 'w') as f:
        f.write(instructions)
    
    print("✓ Created BUILD_INSTRUCTIONS.md")

def main():
    """Main build process."""
    print("🧬 Genetic Improvement System - Build Script")
    print("=" * 50)
    
    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    # Step 1: Verify imports
    if not verify_imports():
        print("\n⚠️  Please install missing dependencies first:")
        print("  pip install -r requirements.txt")
        return 1
    
    # Step 2: Create spec file
    create_spec_file()
    
    # Step 3: Create build instructions
    create_build_instructions()
    
    # Step 4: Build application
    if build_application():
        print("\n✅ Build completed successfully!")
        print(f"   Application: {project_dir}/dist/GeneticImprove.app")
        print("\n📖 See BUILD_INSTRUCTIONS.md for more details")
        return 0
    else:
        print("\n❌ Build failed! Check the error messages above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())