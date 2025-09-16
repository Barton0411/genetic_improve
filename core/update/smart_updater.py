#!/usr/bin/env python3
"""
智能更新器 - 支持任意安装位置的程序更新
"""

import os
import sys
import json
import shutil
import logging
import platform
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib
import time
import psutil

logger = logging.getLogger(__name__)

class PathDetector:
    """路径检测器 - 智能识别程序安装位置和用户数据目录"""
    
    def __init__(self):
        self.platform = platform.system().lower()
        
    def get_current_app_info(self) -> Dict:
        """获取当前应用的完整路径信息"""
        
        # 获取当前程序的绝对路径
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后的程序
            if self.platform == 'darwin' and sys.executable.endswith('.app/Contents/MacOS/GeneticImprove'):
                # macOS app bundle
                app_root = Path(sys.executable).parents[2]  # 到 .app 目录
                executable_path = Path(sys.executable)
            else:
                # Windows exe 或 Linux
                executable_path = Path(sys.executable)
                app_root = executable_path.parent
        else:
            # 开发环境
            executable_path = Path(sys.argv[0]).resolve()
            app_root = Path(__file__).parent.parent.parent  # 项目根目录
        
        # 获取用户数据目录
        user_data_dir = self._get_user_data_directory()
        
        # 分析安装类型
        install_info = self._analyze_installation_type(app_root)
        
        app_info = {
            'executable_path': str(executable_path.resolve()),
            'app_root': str(app_root.resolve()),
            'user_data_dir': str(user_data_dir),
            'platform': self.platform,
            'install_type': install_info['type'],
            'install_location': install_info['location'],
            'drive_letter': install_info.get('drive_letter', ''),
            'requires_admin': install_info['requires_admin'],
            'is_writable': self._check_write_permission(app_root),
            'pid': os.getpid(),
            'process_name': Path(executable_path).name
        }
        
        return app_info
    
    def _get_user_data_directory(self) -> Path:
        """获取用户数据目录"""
        if self.platform == 'windows':
            # Windows: %APPDATA%\GeneticImprove
            appdata = os.environ.get('APPDATA')
            if appdata:
                return Path(appdata) / 'GeneticImprove'
            else:
                return Path.home() / 'AppData' / 'Roaming' / 'GeneticImprove'
        elif self.platform == 'darwin':
            # macOS: ~/Library/Application Support/GeneticImprove
            return Path.home() / 'Library' / 'Application Support' / 'GeneticImprove'
        else:
            # Linux: ~/.genetic_improve
            return Path.home() / '.genetic_improve'
    
    def _analyze_installation_type(self, app_root: Path) -> Dict:
        """分析安装类型和位置"""
        
        app_root_str = str(app_root).lower()
        
        if self.platform == 'windows':
            return self._analyze_windows_installation(app_root, app_root_str)
        elif self.platform == 'darwin':
            return self._analyze_macos_installation(app_root, app_root_str)
        else:
            return self._analyze_linux_installation(app_root, app_root_str)
    
    def _analyze_windows_installation(self, app_root: Path, app_root_str: str) -> Dict:
        """分析Windows安装类型"""
        
        # 获取驱动器盘符
        drive_letter = str(app_root).split(':')[0].upper() if ':' in str(app_root) else 'C'
        
        # 判断安装位置类型
        if 'program files' in app_root_str:
            if 'program files (x86)' in app_root_str:
                install_type = 'system_x86'
                location = f'{drive_letter}:\\Program Files (x86)'
            else:
                install_type = 'system_x64'
                location = f'{drive_letter}:\\Program Files'
            requires_admin = True
            
        elif 'appdata' in app_root_str:
            if 'local' in app_root_str:
                install_type = 'user_local'
                location = 'AppData\\Local'
            else:
                install_type = 'user_roaming'
                location = 'AppData\\Roaming'
            requires_admin = False
            
        elif app_root.is_relative_to(Path.home()):
            install_type = 'user_home'
            location = '用户目录'
            requires_admin = False
            
        else:
            # 其他位置，可能是便携版或自定义位置
            install_type = 'portable'
            location = str(app_root.parent)
            requires_admin = False
        
        return {
            'type': install_type,
            'location': location,
            'drive_letter': drive_letter,
            'requires_admin': requires_admin
        }
    
    def _analyze_macos_installation(self, app_root: Path, app_root_str: str) -> Dict:
        """分析macOS安装类型"""
        
        if '/applications' in app_root_str:
            return {
                'type': 'system_applications',
                'location': '/Applications',
                'requires_admin': True
            }
        elif str(app_root).startswith(str(Path.home())):
            return {
                'type': 'user_applications', 
                'location': f'{Path.home()}/Applications',
                'requires_admin': False
            }
        else:
            return {
                'type': 'portable',
                'location': str(app_root.parent),
                'requires_admin': False
            }
    
    def _analyze_linux_installation(self, app_root: Path, app_root_str: str) -> Dict:
        """分析Linux安装类型"""
        
        if app_root_str.startswith('/usr/'):
            return {
                'type': 'system_usr',
                'location': '/usr',
                'requires_admin': True
            }
        elif app_root_str.startswith('/opt/'):
            return {
                'type': 'system_opt',
                'location': '/opt',
                'requires_admin': True
            }
        elif str(app_root).startswith(str(Path.home())):
            return {
                'type': 'user_home',
                'location': str(Path.home()),
                'requires_admin': False
            }
        else:
            return {
                'type': 'portable',
                'location': str(app_root.parent),
                'requires_admin': False
            }
    
    def _check_write_permission(self, path: Path) -> bool:
        """检查指定路径的写入权限"""
        try:
            # 尝试创建临时文件
            test_file = path / f'.write_test_{os.getpid()}'
            test_file.write_text('test')
            test_file.unlink()
            return True
        except (PermissionError, OSError):
            return False

class SmartUpdater:
    """智能更新器主类"""
    
    def __init__(self):
        self.detector = PathDetector()
        self.app_info = self.detector.get_current_app_info()
        self.user_data_dir = Path(self.app_info['user_data_dir'])
        
        # 确保用户数据目录存在
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置日志
        self._setup_logging()
        
        logger.info(f"应用信息检测完成: {json.dumps(self.app_info, indent=2, ensure_ascii=False)}")
    
    def _setup_logging(self):
        """设置日志记录"""
        log_file = self.user_data_dir / 'logs' / 'updater.log'
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 配置文件日志
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
    
    def prepare_forced_update(self, update_info: Dict) -> bool:
        """准备强制更新"""
        
        logger.info(f"开始准备强制更新到版本 {update_info.get('version')}")
        
        try:
            # 1. 检查更新条件
            if not self._validate_update_conditions(update_info):
                return False
            
            # 2. 创建更新配置
            update_config = self._create_update_config(update_info)
            
            # 3. 下载更新包
            package_path = self._download_update_package(update_info)
            
            # 4. 验证更新包
            if not self._verify_update_package(package_path, update_info):
                logger.error("更新包验证失败")
                return False
            
            # 5. 创建独立更新器
            updater_path = self._create_updater_executable()
            
            # 6. 保存更新配置
            config_path = self._save_update_config(update_config, package_path)
            
            # 7. 启动独立更新器
            self._launch_updater(updater_path, config_path)
            
            return True
            
        except Exception as e:
            logger.error(f"准备更新失败: {e}", exc_info=True)
            return False
    
    def _validate_update_conditions(self, update_info: Dict) -> bool:
        """验证更新条件"""
        
        # 检查网络连接
        # 检查磁盘空间
        required_space = update_info.get('package_size', 0) * 2  # 需要双倍空间用于备份
        available_space = shutil.disk_usage(self.user_data_dir).free
        
        if required_space > available_space:
            logger.error(f"磁盘空间不足: 需要 {required_space}, 可用 {available_space}")
            return False
        
        # 检查权限
        if self.app_info['requires_admin'] and not self.app_info['is_writable']:
            logger.warning("需要管理员权限进行更新")
            # TODO: 请求管理员权限
        
        return True
    
    def _create_update_config(self, update_info: Dict) -> Dict:
        """创建更新配置"""
        
        config = {
            'app_info': self.app_info,
            'update_info': update_info,
            'paths': {
                'backup_root': str(self.user_data_dir / 'backup'),
                'temp_root': str(self.user_data_dir / 'temp'),
                'logs_dir': str(self.user_data_dir / 'logs')
            },
            'preserve_patterns': [
                # 用户数据保护模式
                '**/projects/**',           # 项目文件
                '**/cache/**',             # 缓存数据
                '**/logs/**',              # 日志文件
                '**/config/**',            # 配置文件
                '**/.genetic_improve/**',  # 用户数据目录
                '**/*.db',                 # 数据库文件
                '**/*.log',                # 日志文件
                '**/settings.json',        # 设置文件
                '**/user_preferences.json' # 用户偏好
            ],
            'timestamp': int(time.time())
        }
        
        return config
    
    def _download_update_package(self, update_info: Dict) -> Path:
        """下载更新包"""
        
        package_url = update_info['package_url']
        temp_dir = self.user_data_dir / 'temp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        package_path = temp_dir / f"update_package_{update_info['version']}.zip"
        
        logger.info(f"开始下载更新包: {package_url}")
        
        # TODO: 实现带进度的下载
        import urllib.request
        urllib.request.urlretrieve(package_url, package_path)
        
        logger.info(f"更新包下载完成: {package_path}")
        return package_path
    
    def _verify_update_package(self, package_path: Path, update_info: Dict) -> bool:
        """验证更新包完整性"""
        
        if not package_path.exists():
            return False
        
        # 验证文件大小
        expected_size = update_info.get('package_size')
        if expected_size and package_path.stat().st_size != expected_size:
            logger.error(f"文件大小不匹配: 期望 {expected_size}, 实际 {package_path.stat().st_size}")
            return False
        
        # 验证MD5哈希
        expected_md5 = update_info.get('md5')
        if expected_md5:
            actual_md5 = self._calculate_md5(package_path)
            if actual_md5.lower() != expected_md5.lower():
                logger.error(f"MD5校验失败: 期望 {expected_md5}, 实际 {actual_md5}")
                return False
        
        # 验证ZIP文件完整性
        try:
            with zipfile.ZipFile(package_path, 'r') as zf:
                zf.testzip()
        except Exception as e:
            logger.error(f"ZIP文件损坏: {e}")
            return False
        
        logger.info("更新包验证通过")
        return True
    
    def _calculate_md5(self, file_path: Path) -> str:
        """计算文件MD5哈希"""
        md5_hash = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    
    def _create_updater_executable(self) -> Path:
        """创建独立的更新器可执行文件"""
        
        updater_dir = self.user_data_dir / 'updater'
        updater_dir.mkdir(parents=True, exist_ok=True)
        
        if self.app_info['platform'] == 'windows':
            updater_path = updater_dir / 'updater.exe'
        else:
            updater_path = updater_dir / 'updater'
        
        # 这里应该是预编译的独立更新器程序
        # 目前先创建一个Python脚本作为演示
        updater_script = updater_dir / 'updater.py'
        updater_script.write_text(self._get_updater_script_content())
        
        return updater_script
    
    def _get_updater_script_content(self) -> str:
        """获取更新器脚本内容"""
        return '''#!/usr/bin/env python3
"""
独立更新器 - 负责实际的文件替换操作
"""

import sys
import json
import time
import logging
from pathlib import Path

def main():
    if len(sys.argv) != 2:
        print("用法: updater.py <config_file>")
        return
    
    config_file = sys.argv[1]
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 设置日志
    log_file = Path(config['paths']['logs_dir']) / 'updater_execution.log'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("独立更新器启动")
    
    try:
        # 等待主程序退出
        main_pid = config['app_info']['pid']
        logger.info(f"等待主程序退出 (PID: {main_pid})")
        wait_for_process_exit(main_pid)
        
        # 执行更新
        execute_update(config)
        
        logger.info("更新完成，启动新版本")
        # 启动新版本程序
        # subprocess.Popen([config['app_info']['executable_path']])
        
    except Exception as e:
        logger.error(f"更新失败: {e}", exc_info=True)

def wait_for_process_exit(pid):
    """等待指定进程退出"""
    import psutil
    try:
        process = psutil.Process(pid)
        process.wait(timeout=30)
    except (psutil.NoSuchProcess, psutil.TimeoutExpired):
        pass

def execute_update(config):
    """执行实际的更新操作"""
    # TODO: 实现文件备份、替换、验证等操作
    pass

if __name__ == '__main__':
    main()
'''
    
    def _save_update_config(self, config: Dict, package_path: Path) -> Path:
        """保存更新配置到文件"""
        
        config_dir = self.user_data_dir / 'temp'
        config_path = config_dir / 'update_config.json'
        
        config['package_path'] = str(package_path)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"更新配置已保存: {config_path}")
        return config_path
    
    def _launch_updater(self, updater_path: Path, config_path: Path):
        """启动独立更新器"""
        
        logger.info(f"启动独立更新器: {updater_path}")
        
        if updater_path.suffix == '.py':
            # Python脚本
            subprocess.Popen([sys.executable, str(updater_path), str(config_path)])
        else:
            # 可执行文件
            subprocess.Popen([str(updater_path), str(config_path)])
        
        logger.info("独立更新器已启动，主程序即将退出")

def detect_current_installation():
    """检测当前安装信息的便捷函数"""
    detector = PathDetector()
    return detector.get_current_app_info()

def test_path_detection():
    """测试路径检测功能"""
    print("=== 智能路径检测测试 ===")
    
    try:
        app_info = detect_current_installation()
        
        print(f"🔍 检测结果:")
        print(f"   可执行文件: {app_info['executable_path']}")
        print(f"   程序根目录: {app_info['app_root']}")
        print(f"   用户数据目录: {app_info['user_data_dir']}")
        print(f"   操作系统: {app_info['platform']}")
        print(f"   安装类型: {app_info['install_type']}")
        print(f"   安装位置: {app_info['install_location']}")
        if app_info['drive_letter']:
            print(f"   驱动器: {app_info['drive_letter']}:")
        print(f"   需要管理员权限: {'是' if app_info['requires_admin'] else '否'}")
        print(f"   目录可写: {'是' if app_info['is_writable'] else '否'}")
        print(f"   进程ID: {app_info['pid']}")
        print(f"   进程名: {app_info['process_name']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 检测失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    test_path_detection()