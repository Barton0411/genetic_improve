"""
跨平台适配模块
解决macOS开发的应用在Linux服务器上的兼容性问题
"""

import platform
import os
import sys
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class PlatformAdapter:
    """平台适配器"""
    
    def __init__(self):
        self.current_platform = platform.system().lower()
        self.is_macos = self.current_platform == 'darwin'
        self.is_linux = self.current_platform == 'linux'
        self.is_windows = self.current_platform == 'windows'
        
    def get_font_paths(self):
        """获取系统字体路径"""
        if self.is_macos:
            return [
                '/System/Library/Fonts/',
                '/Library/Fonts/',
                '~/Library/Fonts/'
            ]
        elif self.is_linux:
            return [
                '/usr/share/fonts/',
                '/usr/local/share/fonts/',
                '~/.fonts/',
                '~/.local/share/fonts/'
            ]
        elif self.is_windows:
            return [
                'C:/Windows/Fonts/',
                '~/AppData/Local/Microsoft/Windows/Fonts/'
            ]
        return []
    
    def get_chinese_fonts(self):
        """获取中文字体列表"""
        if self.is_macos:
            return [
                'PingFang SC',
                'STHeiti',
                'Hiragino Sans GB',
                'STSong'
            ]
        elif self.is_linux:
            return [
                'Noto Sans CJK SC',
                'Source Han Sans CN',
                'WenQuanYi Micro Hei',
                'DejaVu Sans',
                'Liberation Sans'
            ]
        elif self.is_windows:
            return [
                'Microsoft YaHei',
                'SimHei',
                'SimSun',
                'Microsoft JhengHei'
            ]
        return ['DejaVu Sans']  # 默认字体
    
    def get_app_data_dir(self, app_name="genetic_improve"):
        """获取应用数据目录"""
        if self.is_macos:
            base_dir = Path.home() / "Library" / "Application Support"
        elif self.is_linux:
            base_dir = Path.home() / ".local" / "share"
        elif self.is_windows:
            base_dir = Path.home() / "AppData" / "Local"
        else:
            base_dir = Path.home()
            
        app_dir = base_dir / app_name
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir
    
    def setup_display_env(self):
        """设置显示环境变量（Linux服务器需要）"""
        if self.is_linux and 'DISPLAY' not in os.environ:
            os.environ['DISPLAY'] = ':99'
            os.environ['QT_QPA_PLATFORM'] = 'xcb'
            os.environ['XDG_RUNTIME_DIR'] = '/tmp/runtime-root'
            
            # 创建运行时目录
            Path('/tmp/runtime-root').mkdir(exist_ok=True)
    
    def get_matplotlib_backend(self):
        """获取适合的matplotlib后端"""
        if self.is_linux and not os.environ.get('DISPLAY'):
            return 'Agg'  # 无头模式
        return 'Qt5Agg'  # 默认Qt后端
    
    def setup_qt_platform(self):
        """设置Qt平台"""
        if self.is_linux:
            os.environ['QT_QPA_PLATFORM'] = 'xcb'
            # 禁用Qt的警告信息
            os.environ['QT_LOGGING_RULES'] = 'qt.qpa.xcb.warning=false'
    
    def install_system_dependencies(self):
        """返回需要安装的系统依赖命令"""
        if self.is_linux:
            return """
# Ubuntu/Debian 系统依赖安装命令：
sudo apt update
sudo apt install -y \\
    python3-pyqt6 \\
    python3-pyqt6.qtmultimedia \\
    qt6-base-dev \\
    xvfb \\
    x11vnc \\
    fonts-noto-cjk \\
    fonts-wqy-microhei \\
    libxcb-xinerama0 \\
    libgl1-mesa-glx \\
    libegl1-mesa \\
    libxrandr2 \\
    libxss1 \\
    libxcursor1 \\
    libxcomposite1 \\
    libasound2 \\
    libxi6 \\
    libxtst6

# CentOS/RHEL 系统依赖安装命令：
sudo yum install -y \\
    python3-qt6 \\
    qt6-qtbase-devel \\
    xorg-x11-server-Xvfb \\
    x11vnc \\
    google-noto-sans-cjk-fonts \\
    liberation-fonts
"""
        elif self.is_macos:
            return """
# macOS 系统依赖安装命令：
brew install qt@6
brew install --cask font-noto-sans-cjk-sc
"""
        return "# 当前平台无需额外系统依赖"

# 全局适配器实例
adapter = PlatformAdapter()

def initialize_platform():
    """初始化平台环境"""
    logger.info(f"检测到平台: {adapter.current_platform}")
    
    # 设置显示环境
    adapter.setup_display_env()
    
    # 设置Qt平台
    adapter.setup_qt_platform()
    
    # 设置matplotlib后端
    import matplotlib
    matplotlib.use(adapter.get_matplotlib_backend())
    
    logger.info("平台环境初始化完成")

def get_system_info():
    """获取系统信息"""
    import psutil
    
    info = {
        'platform': platform.system(),
        'platform_version': platform.version(),
        'architecture': platform.machine(),
        'python_version': sys.version,
        'cpu_count': os.cpu_count(),
        'memory_total': f"{psutil.virtual_memory().total / (1024**3):.1f}GB",
        'display': os.environ.get('DISPLAY', 'Not set'),
        'qt_platform': os.environ.get('QT_QPA_PLATFORM', 'Not set')
    }
    
    return info

if __name__ == "__main__":
    # 测试平台适配
    initialize_platform()
    
    print("=== 平台信息 ===")
    info = get_system_info()
    for key, value in info.items():
        print(f"{key}: {value}")
    
    print("\n=== 字体支持 ===")
    fonts = adapter.get_chinese_fonts()
    print(f"支持的中文字体: {fonts}")
    
    print(f"\n=== 系统依赖安装命令 ===")
    print(adapter.install_system_dependencies())