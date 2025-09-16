"""
版本更新管理模块
"""

import requests
import platform
import logging
from typing import Dict, Optional, Tuple
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser
import subprocess
import tempfile
import os

from ..version import get_version

logger = logging.getLogger(__name__)


class VersionManager:
    """版本管理器"""
    
    def __init__(self, server_url: str = "https://your-server-domain.com"):
        """
        初始化版本管理器
        
        Args:
            server_url: 服务器URL
        """
        self.server_url = server_url.rstrip('/')
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
        检查是否有新版本
        
        Returns:
            (是否有更新, 版本信息字典)
        """
        try:
            # 调用服务器API检查版本
            response = requests.get(
                f"{self.server_url}/api/version/latest",
                timeout=10
            )
            
            if response.status_code == 200:
                version_info = response.json()
                latest_version = version_info.get('version')
                
                if latest_version and self._compare_versions(latest_version, self.current_version) > 0:
                    return True, version_info
                else:
                    return False, None
            else:
                logger.error(f"版本检查失败: HTTP {response.status_code}")
                return False, None
                
        except requests.RequestException as e:
            logger.error(f"版本检查失败: {e}")
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
    
    def show_update_dialog(self, version_info: Dict) -> bool:
        """
        显示更新对话框
        
        Args:
            version_info: 版本信息
            
        Returns:
            用户是否选择更新
        """
        try:
            # 创建更新对话框
            dialog = UpdateDialog(version_info, self.platform_info)
            return dialog.show()
        except Exception as e:
            logger.error(f"显示更新对话框失败: {e}")
            return False
    
    def get_download_url(self, version: str, platform: str) -> Optional[str]:
        """
        获取下载链接
        
        Args:
            version: 版本号
            platform: 平台 (mac/win)
            
        Returns:
            下载链接
        """
        try:
            response = requests.get(
                f"{self.server_url}/api/version/{version}/download/{platform}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('download_url')
            else:
                logger.error(f"获取下载链接失败: HTTP {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"获取下载链接失败: {e}")
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
            
            # 显示安装提示
            messagebox.showinfo(
                "下载开始",
                f"新版本 {version} 的下载已在浏览器中开始。\n\n"
                "下载完成后请关闭当前程序，然后安装新版本。"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            messagebox.showerror("下载失败", f"下载失败: {e}")
            return False


class UpdateDialog:
    """更新对话框"""
    
    def __init__(self, version_info: Dict, platform_info: Dict):
        self.version_info = version_info
        self.platform_info = platform_info
        self.result = False
        self.selected_platform = platform_info['os']
        
    def show(self) -> bool:
        """显示对话框并返回用户选择"""
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        
        # 创建对话框窗口
        dialog = tk.Toplevel(root)
        dialog.title("软件更新")
        dialog.geometry("500x400")
        dialog.resizable(False, False)
        
        # 居中显示
        dialog.transient(root)
        dialog.grab_set()
        
        # 主框架
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(
            main_frame, 
            text="发现新版本！", 
            font=('Arial', 16, 'bold')
        )
        title_label.pack(pady=(0, 10))
        
        # 版本信息
        version_frame = ttk.LabelFrame(main_frame, text="版本信息", padding="10")
        version_frame.pack(fill=tk.X, pady=(0, 15))
        
        current_label = ttk.Label(version_frame, text=f"当前版本: {get_version()}")
        current_label.pack(anchor=tk.W)
        
        latest_label = ttk.Label(
            version_frame, 
            text=f"最新版本: {self.version_info.get('version', '未知')}",
            font=('Arial', 10, 'bold')
        )
        latest_label.pack(anchor=tk.W)
        
        # 更新内容
        changes_frame = ttk.LabelFrame(main_frame, text="更新内容", padding="10")
        changes_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # 创建滚动文本框
        text_frame = ttk.Frame(changes_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        changes_text = tk.Text(
            text_frame, 
            wrap=tk.WORD, 
            yscrollcommand=scrollbar.set,
            height=8,
            font=('Arial', 9)
        )
        changes_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=changes_text.yview)
        
        # 填充更新内容
        changes = self.version_info.get('changes', [])
        for i, change in enumerate(changes, 1):
            changes_text.insert(tk.END, f"{i}. {change}\n")
        
        changes_text.config(state=tk.DISABLED)
        
        # 平台选择
        platform_frame = ttk.LabelFrame(main_frame, text="选择平台", padding="10")
        platform_frame.pack(fill=tk.X, pady=(0, 15))
        
        platform_var = tk.StringVar(value=self.selected_platform)
        
        mac_radio = ttk.Radiobutton(
            platform_frame, 
            text="macOS (.dmg)", 
            variable=platform_var, 
            value="mac"
        )
        mac_radio.pack(anchor=tk.W)
        
        win_radio = ttk.Radiobutton(
            platform_frame, 
            text="Windows (.exe)", 
            variable=platform_var, 
            value="win"
        )
        win_radio.pack(anchor=tk.W)
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        def on_update():
            self.selected_platform = platform_var.get()
            self.result = True
            dialog.destroy()
            root.quit()
        
        def on_skip():
            self.result = False
            dialog.destroy()
            root.quit()
        
        # 按钮
        update_btn = ttk.Button(
            button_frame, 
            text="立即更新", 
            command=on_update,
            style="Accent.TButton"
        )
        update_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        skip_btn = ttk.Button(
            button_frame, 
            text="跳过", 
            command=on_skip
        )
        skip_btn.pack(side=tk.RIGHT)
        
        # 处理窗口关闭
        dialog.protocol("WM_DELETE_WINDOW", on_skip)
        
        # 运行对话框
        root.mainloop()
        root.destroy()
        
        return self.result, self.selected_platform if self.result else None


def check_and_handle_updates(server_url: str = "https://your-server-domain.com") -> bool:
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
        
        logger.info(f"发现新版本: {version_info.get('version')}")
        
        # 显示更新对话框
        should_update, selected_platform = manager.show_update_dialog(version_info)
        
        if not should_update:
            logger.info("用户选择跳过更新")
            return False
        
        # 获取下载链接
        download_url = manager.get_download_url(
            version_info['version'], 
            selected_platform
        )
        
        if not download_url:
            messagebox.showerror("错误", "获取下载链接失败，请稍后再试。")
            return False
        
        # 下载并安装
        success = manager.download_and_install(
            download_url, 
            version_info['version']
        )
        
        if success:
            # 提示用户退出程序
            result = messagebox.askyesno(
                "更新提示",
                "下载已开始，建议现在退出程序以便安装新版本。\n\n是否立即退出？"
            )
            return result
        
        return False
        
    except Exception as e:
        logger.error(f"更新检查失败: {e}")
        return False