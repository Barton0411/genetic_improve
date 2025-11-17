"""
PyInstaller hook to exclude pyarrow (not needed in production)
"""
excludedimports = ['pyarrow']
datas = []
binaries = []
hiddenimports = []
