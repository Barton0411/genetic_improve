"""
PyInstaller hook to exclude torch and related packages
"""
from PyInstaller.utils.hooks import collect_submodules

# 强制排除torch相关模块
excludedimports = [
    'torch',
    'torch.nn',
    'torch.optim',
    'torch.utils',
    'torchvision',
    'torchaudio',
]

# 不收集任何torch相关数据
datas = []
binaries = []
hiddenimports = []
