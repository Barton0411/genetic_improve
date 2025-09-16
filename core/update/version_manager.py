"""
版本更新管理模块
"""

try:
    import requests
except ImportError:
    print("警告: requests模块未安装，版本检查功能不可用")
    print("请运行: pip install requests")
    requests = None
import platform
import logging
from typing import Dict, Optional, Tuple
from pathlib import Path
try:
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QRadioButton, QButtonGroup, QFrame
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
import webbrowser
import subprocess
import tempfile
import os

from version import get_version

logger = logging.getLogger(__name__)


class VersionManager:
    """版本管理器"""
    
    def __init__(self, server_url: str = "https://api.genepop.com"):
        """
        初始化版本管理器
        
        Args:
            server_url: 服务器URL
        """
        self.server_url = server_url.rstrip('/')
        # 备用服务器列表（用于海外访问）
        self.backup_servers = [
            "http://39.96.189.27:8080",  # 直接IP访问
            "https://api.genepop.com",   # 主域名
        ]
        self.current_version = get_version()
        self.platform_info = self._get_platform_info()
        
    def _get_platform_info(self) -> Dict[str, str]:
        """获取平台信息"""
        system = platform.system().lower()
        
        if system == "darwin":
            return {
                "os": "mac",
                "platform": "macOS",
                "file_extension": ".dmg"
            }
        elif system == "windows":
            return {
                "os": "win",
                "platform": "Windows", 
                "file_extension": ".exe"
            }
        else:
            return {
                "os": "linux",
                "platform": "Linux",
                "file_extension": ".tar.gz"
            }
    
    def check_for_updates(self) -> Tuple[bool, Optional[Dict]]:
        """
        检查是否有新版本（支持备用服务器重试）
        
        Returns:
            (是否有更新, 版本信息字典)
        """
        if requests is None:
            logger.error("requests模块未安装，无法检查版本更新")
            return False, None
            
        # 尝试主服务器和备用服务器
        servers_to_try = [self.server_url] + [s for s in self.backup_servers if s != self.server_url]
        
        for server_url in servers_to_try:
            try:
                logger.info(f"尝试连接服务器: {server_url}")
                # 调用服务器API检查版本
                response = requests.get(
                    f"{server_url}/api/version/latest",
                    timeout=10
                )
                
                if response.status_code == 200:
                    version_info = response.json()
                    latest_version = version_info.get('data', {}).get('version') or version_info.get('version')
                    
                    if latest_version and self._compare_versions(latest_version, self.current_version) > 0:
                        logger.info(f"发现新版本 {latest_version}，服务器: {server_url}")
                        return True, version_info
                    else:
                        logger.info(f"当前已是最新版本，服务器: {server_url}")
                        return False, None
                else:
                    logger.warning(f"服务器 {server_url} 返回错误: HTTP {response.status_code}")
                    continue
                    
            except requests.RequestException as e:
                logger.warning(f"服务器 {server_url} 连接失败: {e}")
                continue
        
        logger.error("所有服务器都无法访问")
        return False, None
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """
        比较版本号
        
        Returns:
            1: version1 > version2
            0: version1 == version2
            -1: version1 < version2
        """
        try:
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            # 补齐长度
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))
            
            for v1, v2 in zip(v1_parts, v2_parts):
                if v1 > v2:
                    return 1
                elif v1 < v2:
                    return -1
            
            return 0
        except ValueError:
            logger.error(f"版本号格式错误: {version1}, {version2}")
            return 0
    
    def show_update_dialog(self, version_info: Dict) -> tuple:
        """
        显示更新对话框
        
        Args:
            version_info: 版本信息
            
        Returns:
            (用户是否选择更新, 选择的平台)
        """
        try:
            if not QT_AVAILABLE:
                logger.error("PyQt6不可用，无法显示更新对话框")
                return False, None
                
            # 创建更新对话框
            dialog = UpdateDialog(version_info, self.platform_info)
            result = dialog.exec()
            
            if result == QDialog.DialogCode.Accepted:
                selected_platform = dialog.get_selected_platform()
                return True, selected_platform
            else:
                return False, None
        except Exception as e:
            logger.error(f"显示更新对话框失败: {e}")
            import traceback
            logger.error(f"对话框错误详情: {traceback.format_exc()}")
            return False, None
    
    def get_download_url_from_version_info(self, version_info: Dict, platform: str) -> Optional[str]:
        """
        从版本信息中获取下载链接
        
        Args:
            version_info: 版本信息字典
            platform: 平台 (mac/win)
            
        Returns:
            下载链接
        """
        try:
            data = version_info.get('data', {})
            if platform == "mac":
                return data.get('mac_download_url')
            elif platform == "win":
                return data.get('win_download_url')
            else:
                logger.error(f"不支持的平台: {platform}")
                return None
                
        except Exception as e:
            logger.error(f"解析下载链接失败: {e}")
            return None
    
    def download_and_install(self, download_url: str, version: str) -> bool:
        """
        下载并安装新版本
        
        Args:
            download_url: 下载链接
            version: 版本号
            
        Returns:
            是否成功
        """
        try:
            # 在浏览器中打开下载链接
            webbrowser.open(download_url)
            
            # 记录日志
            logger.info(f"新版本 {version} 的下载已在浏览器中开始")
            logger.info("下载完成后请关闭当前程序，然后安装新版本")
            
            return True
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            return False


class UpdateDialog(QDialog):
    """更新对话框 - 使用PyQt6"""
    
    def __init__(self, version_info: Dict, platform_info: Dict):
        super().__init__()
        self.version_info = version_info
        self.platform_info = platform_info
        self.result = False
        self.selected_platform = platform_info['os']
        self.setupUI()
        
    def setupUI(self):
        """设置UI"""
        self.setWindowTitle("软件更新")
        self.setFixedSize(500, 400)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("发现新版本！")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 版本信息
        version_frame = QFrame()
        version_frame.setFrameStyle(QFrame.Shape.Box)
        version_layout = QVBoxLayout(version_frame)
        
        current_label = QLabel(f"当前版本: {get_version()}")
        version_layout.addWidget(current_label)
        
        latest_version = self.version_info.get('data', {}).get('version') or self.version_info.get('version')
        latest_label = QLabel(f"最新版本: {latest_version}")
        latest_font = QFont()
        latest_font.setBold(True)
        latest_label.setFont(latest_font)
        version_layout.addWidget(latest_label)
        
        layout.addWidget(version_frame)
        
        # 更新内容
        changes_label = QLabel("更新内容:")
        layout.addWidget(changes_label)
        
        changes_text = QTextEdit()
        changes_text.setMaximumHeight(150)
        changes_text.setReadOnly(True)
        
        # 填充更新内容
        changes = self.version_info.get('data', {}).get('changes') or self.version_info.get('changes', [])
        if isinstance(changes, str):
            changes_text.setText(changes)
        else:
            content = "\n".join([f"{i}. {change}" for i, change in enumerate(changes, 1)])
            changes_text.setText(content)
        
        layout.addWidget(changes_text)
        
        # 平台选择
        platform_label = QLabel("选择平台:")
        layout.addWidget(platform_label)
        
        platform_layout = QVBoxLayout()
        self.button_group = QButtonGroup()
        
        self.mac_radio = QRadioButton("macOS (.dmg)")
        self.win_radio = QRadioButton("Windows (.exe)")
        
        self.button_group.addButton(self.mac_radio, 0)
        self.button_group.addButton(self.win_radio, 1)
        
        if self.selected_platform == "mac":
            self.mac_radio.setChecked(True)
        else:
            self.win_radio.setChecked(True)
            
        platform_layout.addWidget(self.mac_radio)
        platform_layout.addWidget(self.win_radio)
        layout.addLayout(platform_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        skip_btn = QPushButton("跳过")
        skip_btn.clicked.connect(self.reject)
        button_layout.addWidget(skip_btn)
        
        update_btn = QPushButton("立即更新")
        update_btn.clicked.connect(self.accept)
        update_btn.setDefault(True)
        button_layout.addWidget(update_btn)
        
        layout.addLayout(button_layout)
        
    def get_selected_platform(self):
        """获取选择的平台"""
        if self.mac_radio.isChecked():
            return "mac"
        else:
            return "win"


def check_and_handle_updates(server_url: str = "https://api.genepop.com") -> bool:
    """
    检查并处理更新
    
    Args:
        server_url: 服务器URL
        
    Returns:
        是否需要退出程序进行更新
    """
    try:
        manager = VersionManager(server_url)
        
        # 检查更新
        has_update, version_info = manager.check_for_updates()
        
        if not has_update:
            logger.info("当前已是最新版本")
            return False
        
        latest_version_for_log = version_info.get('data', {}).get('version') or version_info.get('version', '未知')
        logger.info(f"发现新版本: {latest_version_for_log}")
        
        # 显示更新对话框
        should_update, selected_platform = manager.show_update_dialog(version_info)
        
        if not should_update:
            logger.info("用户选择跳过更新")
            return False
        
        # 获取版本号（处理不同的API响应格式）
        latest_version = version_info.get('data', {}).get('version') or version_info.get('version')
        if not latest_version:
            logger.error("无法获取版本号信息")
            return False
        
        # 获取下载链接
        download_url = manager.get_download_url_from_version_info(version_info, selected_platform)
        
        if not download_url:
            logger.error("获取下载链接失败，请稍后再试")
            return False
        
        # 下载并安装
        success = manager.download_and_install(download_url, latest_version)
        
        if success:
            # 记录日志
            logger.info("下载已开始，建议现在退出程序以便安装新版本")
            # 默认不退出程序，让用户自己决定
            return False
        
        return False
        
    except Exception as e:
        logger.error(f"更新检查失败: {e}")
        return False