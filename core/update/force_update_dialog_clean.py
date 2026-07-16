#!/usr/bin/env python3
"""
强制更新对话框 - 不可关闭，必须更新（清理版本）
"""

import sys
import logging
from typing import Dict, Optional
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QProgressBar, QFrame,
                             QApplication, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPixmap, QIcon
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

class DownloadThread(QThread):
    """下载线程 - 避免阻塞UI"""
    
    progress = pyqtSignal(int, str)  # 进度百分比, 状态信息
    finished = pyqtSignal(bool, str)  # 是否成功, 结果信息
    
    def __init__(self, url: str, save_path: str):
        super().__init__()
        self.url = url
        self.save_path = save_path
        
    def run(self):
        """执行下载"""
        try:
            self.progress.emit(0, "开始下载更新包...")
            
            import requests
            import os
            
            # 检查URL是否有效
            if not self.url:
                self.finished.emit(False, "下载地址无效")
                return
            
            # 发送HTTP请求开始下载（禁用代理直连，避免系统代理未启动时连接被拒）
            session = requests.Session()
            session.trust_env = False
            session.proxies = {'http': None, 'https': None}
            response = session.get(self.url, stream=True, timeout=30)
            response.raise_for_status()
            
            # 获取文件总大小
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            # 确保目录存在
            os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
            
            # 开始下载
            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 计算下载进度
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            size_mb = downloaded_size / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024)
                            self.progress.emit(progress, f"正在下载... {progress}% ({size_mb:.1f}/{total_mb:.1f} MB)")
                        else:
                            size_mb = downloaded_size / (1024 * 1024)
                            self.progress.emit(50, f"正在下载... {size_mb:.1f} MB")
            
            # 验证下载的文件
            if os.path.exists(self.save_path) and os.path.getsize(self.save_path) > 0:
                self.progress.emit(100, "下载完成，准备更新...")
                self.finished.emit(True, "下载成功")
            else:
                self.finished.emit(False, "下载文件验证失败")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"网络错误: {e}")
            self.finished.emit(False, f"网络错误: {str(e)}")
        except OSError as e:
            logger.error(f"文件操作错误: {e}")
            self.finished.emit(False, f"文件操作错误: {str(e)}")
        except Exception as e:
            logger.error(f"下载失败: {e}")
            self.finished.emit(False, f"下载失败: {str(e)}")

class ForceUpdateDialog(QDialog):
    """强制更新对话框"""
    
    def __init__(self, version_info: Dict, app_info: Dict, parent=None):
        super().__init__(parent)
        self.version_info = version_info
        self.app_info = app_info
        self.download_thread = None
        self.user_chose_exit = False  # 用户是否选择退出程序
        self.setupUI()
        
    def setupUI(self):
        """设置用户界面"""
        self.setWindowTitle("重要更新 - 伊利奶牛选配")
        self.setFixedSize(800, 620)
        self.setModal(True)
        
        # 允许显示关闭按钮
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint | 
                           Qt.WindowType.WindowTitleHint)
        
        # 主体容器
        main_widget = QFrame(self)
        main_widget.setObjectName("mainWidget")
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(25)
        main_layout.setContentsMargins(35, 25, 35, 25)
        
        # 设置深色模式兼容样式
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QDialog[darkMode="true"] {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            #mainWidget {
                background-color: white;
            }
            #mainWidget[darkMode="true"] {
                background-color: #2b2b2b;
            }
        """)
        
        # 检测深色模式
        self._is_dark_mode = self._detect_dark_mode()
        if self._is_dark_mode:
            self.setProperty("darkMode", True)
            main_widget.setProperty("darkMode", True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(main_widget)
        
        # 创建精美的标题卡片
        self._create_header_card(main_layout)
        
        # 版本对比卡片
        self._create_version_card(main_layout)
        
        # 更新内容卡片
        self._create_changes_card(main_layout)
        
        # 进度区域
        self._create_progress_card(main_layout)
        
        # 按钮区域
        self._create_action_area(main_layout)
        
        # 底部说明
        self._create_footer(main_layout)
        
    def _detect_dark_mode(self) -> bool:
        """检测系统是否为深色模式"""
        try:
            import platform
            from PyQt6.QtGui import QPalette
            
            # macOS系统检测
            if platform.system() == 'Darwin':
                import subprocess
                result = subprocess.run(['defaults', 'read', '-g', 'AppleInterfaceStyle'], 
                                      capture_output=True, text=True)
                return result.stdout.strip() == 'Dark'
            
            # Windows系统检测
            elif platform.system() == 'Windows':
                try:
                    import winreg
                    registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                    reg_keypath = r'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize'
                    reg_key = winreg.OpenKey(registry, reg_keypath)
                    value, _ = winreg.QueryValueEx(reg_key, 'AppsUseLightTheme')
                    return value == 0
                except:
                    pass
            
            # 备用方法：使用QPalette检测
            palette = self.palette()
            window_color = palette.color(QPalette.ColorRole.Window)
            return window_color.lightness() < 128
            
        except:
            return False
    
    def _create_header_card(self, layout):
        """创建简洁的标题区域"""
        # 标题
        title_label = QLabel("系统安全更新")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setWeight(QFont.Weight.Light)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {'#ffffff' if self._is_dark_mode else '#212529'}; margin: 20px 0;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 简洁的分割线
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"color: {'#444' if self._is_dark_mode else '#dee2e6'}; margin: 10px 0;")
        layout.addWidget(divider)
    
    def _create_version_card(self, layout):
        """创建版本信息显示"""
        # 获取版本信息
        try:
            from version import get_version
            current_version = get_version()
        except:
            current_version = "1.0.5"
            
        latest_version = self.version_info.get('data', {}).get('version') or self.version_info.get('version', '1.0.6')
        
        # 版本对比容器 - 使用水平布局
        version_container = QHBoxLayout()
        version_container.setSpacing(40)
        version_container.setContentsMargins(50, 30, 50, 30)
        
        # 左边：当前版本 - 使用固定的输入框样式
        left_widget = QFrame()
        left_widget.setFixedSize(180, 100)
        left_widget.setStyleSheet(f"""
            QFrame {{
                background-color: {'#2a2a2a' if self._is_dark_mode else '#f8f9fa'};
                border: none;
                border-radius: 12px;
            }}
        """)
        
        left_layout = QVBoxLayout(left_widget)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.setContentsMargins(10, 10, 10, 10)
        
        current_title = QLabel("当前版本")
        current_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        current_title.setStyleSheet(f"color: {'#999' if self._is_dark_mode else '#666'}; font-size: 12px; margin-bottom: 5px;")
        left_layout.addWidget(current_title)
        
        # 使用LineEdit样式但设为只读
        from PyQt6.QtWidgets import QLineEdit
        current_version_display = QLineEdit(f"v{current_version}")
        current_version_display.setReadOnly(True)
        current_version_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        current_version_display.setStyleSheet(f"""
            QLineEdit {{
                color: {'#ffffff' if self._is_dark_mode else '#212529'};
                font-size: 18px;
                font-weight: bold;
                border: none;
                background: transparent;
                text-align: center;
            }}
        """)
        left_layout.addWidget(current_version_display)
        
        version_container.addWidget(left_widget)
        
        # 中间：完整箭头 - 使用单一Unicode长箭头字符
        arrow_widget = QFrame()
        arrow_widget.setFixedSize(80, 100)
        arrow_layout = QVBoxLayout(arrow_widget)
        arrow_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        
        # 使用简单但可靠的箭头符号
        arrow_label = QLabel("➜")  # 使用右箭头Unicode字符 U+279C
        arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow_label.setStyleSheet("""
            QLabel {
                color: #007bff;
                font-size: 32px;
                font-weight: normal;
                background: transparent;
                border: none;
                font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
            }
        """)
        arrow_layout.addWidget(arrow_label)
        
        version_container.addWidget(arrow_widget)
        
        # 右边：最新版本 - 使用固定的输入框样式
        right_widget = QFrame()
        right_widget.setFixedSize(180, 100)
        right_widget.setStyleSheet("""
            QFrame {
                background-color: #007bff;
                border: none;
                border-radius: 12px;
            }
        """)
        
        right_layout = QVBoxLayout(right_widget)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.setContentsMargins(10, 10, 10, 10)
        
        latest_title = QLabel("最新版本")
        latest_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        latest_title.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 12px; margin-bottom: 5px;")
        right_layout.addWidget(latest_title)
        
        # 使用LineEdit样式但设为只读
        latest_version_display = QLineEdit(f"v{latest_version}")
        latest_version_display.setReadOnly(True)
        latest_version_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        latest_version_display.setStyleSheet("""
            QLineEdit {
                color: white;
                font-size: 18px;
                font-weight: bold;
                border: none;
                background: transparent;
                text-align: center;
            }
        """)
        right_layout.addWidget(latest_version_display)
        
        version_container.addWidget(right_widget)
        
        layout.addLayout(version_container)
    
    def _create_version_box(self, title: str, version: str, color: str, is_current: bool):
        """创建版本信息框"""
        container = QFrame()
        container.setObjectName("versionBox")
        
        if is_current:
            bg_color = "#444" if self._is_dark_mode else "#f1f3f4"
            border_style = "2px dashed"
        else:
            bg_color = "#1a472a" if self._is_dark_mode else "#e8f5e8"
            border_style = "3px solid"
            
        container.setStyleSheet(f"""
            #versionBox {{
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 {bg_color}, stop: 1 {'#2a2a2a' if self._is_dark_mode and is_current else '#ffffff' if not self._is_dark_mode and is_current else bg_color});
                border: {border_style} {color};
                border-radius: 12px;
                padding: 18px;
                min-width: 140px;
            }}
        """)
        
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        
        # 状态图标
        status_icon = "📦" if is_current else "🚀"
        icon_label = QLabel(status_icon)
        icon_label.setStyleSheet("font-size: 20px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color: {color};
            font-size: 13px;
            font-weight: bold;
            text-transform: uppercase;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        version_label = QLabel(f"v{version}")
        version_label.setStyleSheet(f"""
            color: {'#ffffff' if self._is_dark_mode else '#212529'};
            font-size: 20px;
            font-weight: bold;
            margin: 5px 0;
        """)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)
        
        return container
    
    def _create_changes_card(self, layout):
        """创建简洁的更新说明"""
        # 更新说明
        changes_label = QLabel("此更新包含重要安全修复，必须立即安装")
        changes_label.setStyleSheet(f"""
            color: {'#cccccc' if self._is_dark_mode else '#495057'};
            font-size: 16px;
            font-weight: 400;
            text-align: center;
            margin: 30px 0 20px 0;
            padding: 20px;
        """)
        changes_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        changes_label.setWordWrap(True)
        layout.addWidget(changes_label)
        
        # 查看更新内容按钮
        details_btn_layout = QHBoxLayout()
        details_btn_layout.addStretch()
        
        self.details_btn = QPushButton("查看更新内容")
        self.details_btn.clicked.connect(self.show_update_details)
        self.details_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: #007bff;
                border: 1px solid #007bff;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: 400;
            }}
            QPushButton:hover {{
                background-color: #007bff;
                color: white;
            }}
        """)
        details_btn_layout.addWidget(self.details_btn)
        details_btn_layout.addStretch()
        
        layout.addLayout(details_btn_layout)
    
    def _create_progress_card(self, layout):
        """创建简洁的进度区域"""
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"""
            color: {'#999' if self._is_dark_mode else '#666'};
            font-size: 14px;
            text-align: center;
            margin: 20px 0;
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {'#555' if self._is_dark_mode else '#dee2e6'};
                border-radius: 10px;
                background-color: {'#333' if self._is_dark_mode else '#e9ecef'};
                text-align: center;
                font-size: 12px;
                font-weight: bold;
                color: {'#ffffff' if self._is_dark_mode else '#495057'};
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                                          stop: 0 #007bff, stop: 1 #0056b3);
                border-radius: 9px;
            }}
        """)
        layout.addWidget(self.progress_bar)
    
    def _create_action_area(self, layout):
        """创建简洁的按钮区域"""
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.update_btn = QPushButton("立即更新")
        self.update_btn.clicked.connect(self.start_update)
        self.update_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #007bff;
                color: white;
                border: none;
                padding: 16px 48px;
                border-radius: 6px;
                font-size: 16px;
                font-weight: 500;
                min-width: 140px;
            }}
            QPushButton:hover {{
                background-color: #0056b3;
            }}
            QPushButton:pressed {{
                background-color: #004085;
            }}
            QPushButton:disabled {{
                background-color: {'#555' if self._is_dark_mode else '#6c757d'};
            }}
        """)
        self.update_btn.setDefault(True)
        button_layout.addWidget(self.update_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
    
    def _create_footer(self, layout):
        """创建简洁的底部说明"""
        # 简洁的说明文字
        note_label = QLabel("更新过程中请勿关闭程序")
        note_label.setStyleSheet(f"""
            color: {'#777' if self._is_dark_mode else '#999'};
            font-size: 12px;
            text-align: center;
            margin-top: 30px;
        """)
        note_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note_label)
    
    def show_update_details(self):
        """显示更新内容详情"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle("更新内容详情")
        dialog.setFixedSize(500, 400)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # 更新内容文本
        changes_text = QTextEdit()
        changes_text.setReadOnly(True)
        changes_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)  # 启用自动换行

        text_bg = "#1e1e1e" if self._is_dark_mode else "#f8f9fa"
        text_color = "#ffffff" if self._is_dark_mode else "#212529"
        border_color = "#555" if self._is_dark_mode else "#dee2e6"

        changes_text.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 15px;
                background-color: {text_bg};
                color: {text_color};
                font-size: 14px;
                line-height: 1.6;
            }}
        """)

        # 填充更新内容
        changes = self.version_info.get('data', {}).get('changes') or self.version_info.get('changes', [])
        if isinstance(changes, str):
            changes_text.setPlainText(changes)
        elif isinstance(changes, list):
            # 使用HTML格式，支持<b>标签和正确的换行
            # 每个条目用<p>标签包裹，确保有足够的行间距
            content = "".join([f"<p style='margin-bottom: 10px;'>• {change}</p>" for change in changes])
            changes_text.setHtml(content)
        else:
            changes_text.setHtml("<p>• 重要系统更新和安全修复</p><p>• 修复已知问题</p><p>• 提升系统稳定性</p>")
        
        layout.addWidget(changes_text)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: 4px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #5a6268;
            }}
        """)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        dialog.exec()
        
    def start_update(self):
        """开始更新过程"""
        
        try:
            self.update_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.status_label.setText("正在准备更新...")
            
            # 获取下载URL
            package_url = self._get_package_url()
            if not package_url:
                self._show_error("无法获取更新包下载地址")
                return
            
            # 开始下载
            self._start_download(package_url)
            
        except Exception as e:
            logger.error(f"启动更新失败: {e}", exc_info=True)
            self._show_error(f"启动更新失败: {e}")
    
    def _get_package_url(self) -> str:
        """获取适合当前平台的下载URL"""
        
        # 优先从顶层获取，如果没有则从data字段获取（兼容两种格式）
        if self.app_info['platform'] == 'windows':
            url = self.version_info.get('win_download_url', '')
            if not url:
                url = self.version_info.get('data', {}).get('win_download_url', '')
            return url
        elif self.app_info['platform'] == 'darwin':
            url = self.version_info.get('mac_download_url', '')
            if not url:
                url = self.version_info.get('data', {}).get('mac_download_url', '')
            return url
        else:
            url = self.version_info.get('linux_download_url', '')
            if not url:
                url = self.version_info.get('data', {}).get('linux_download_url', '')
            return url
    
    def _start_download(self, package_url: str):
        """开始下载更新包"""
        
        # 设置保存路径 - 使用用户下载文件夹，更容易找到
        import os
        downloads_dir = Path(os.path.expanduser("~/Downloads"))
        version = self.version_info.get('version') or self.version_info.get('data', {}).get('version', 'unknown')
        
        # 根据平台设置正确的文件扩展名
        if self.app_info['platform'] == 'windows':
            save_path = downloads_dir / f"伊利奶牛选配_v{version}_win.exe"
        elif self.app_info['platform'] == 'darwin':
            save_path = downloads_dir / f"伊利奶牛选配_v{version}_mac.dmg"
        else:
            save_path = downloads_dir / f"伊利奶牛选配_v{version}.tar.gz"
        
        # 如果文件已存在，添加时间戳以避免覆盖
        if save_path.exists():
            import time
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            stem = save_path.stem
            suffix = save_path.suffix
            save_path = save_path.parent / f"{stem}_{timestamp}{suffix}"
        
        # 存储下载路径供后续使用
        self.downloaded_file_path = save_path
        logger.info(f"文件将保存到: {save_path}")
        
        # 创建下载线程
        self.download_thread = DownloadThread(package_url, str(save_path))
        self.download_thread.progress.connect(self._on_download_progress)
        self.download_thread.finished.connect(self._on_download_finished)
        
        # 开始下载
        self.download_thread.start()
    
    def _on_download_progress(self, percent: int, status: str):
        """下载进度更新"""
        self.progress_bar.setValue(percent)
        self.status_label.setText(status)
    
    def _on_download_finished(self, success: bool, message: str):
        """下载完成处理"""
        
        if success:
            self.status_label.setText("下载完成！文件已保存到Downloads文件夹")
            
            # 显示重要提示
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox(self)
            msg.setWindowTitle("⚠️ 重要提示")
            msg.setText(f"""新版本已下载完成！

文件位置：Downloads文件夹
文件名：{self.downloaded_file_path.name if hasattr(self, 'downloaded_file_path') else '伊利奶牛选配.dmg'}

如果自动安装失败，请：
1. 打开Downloads文件夹找到下载的DMG文件
2. 双击DMG文件打开
3. 将应用拖拽到Applications文件夹替换旧版本

⚠️ 必须安装新版本才能继续使用应用！""")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            
            # 延迟一秒然后开始实际更新
            QTimer.singleShot(1000, self._execute_update)
            
        else:
            self._show_error(f"下载失败: {message}")
    
    def _execute_update(self):
        """执行实际更新"""
        
        try:
            if not hasattr(self, 'downloaded_file_path') or not self.downloaded_file_path.exists():
                self._show_error("下载文件不存在")
                return
                
            platform = self.app_info['platform']
            
            if platform == 'darwin':  # macOS
                self._install_macos_dmg()
            elif platform == 'windows':  # Windows
                self._install_windows_exe()
            else:
                self._show_error("不支持的操作系统")
                
        except Exception as e:
            logger.error(f"执行更新失败: {e}", exc_info=True)
            self._show_error(f"执行更新失败: {e}")
    
    def _install_macos_dmg(self):
        """安装macOS DMG包"""
        import subprocess
        import os
        
        try:
            self.status_label.setText("正在挂载DMG文件...")
            
            # 记录挂载前的volumes
            volumes_before = set(os.listdir('/Volumes/')) if os.path.exists('/Volumes/') else set()
            
            # 挂载DMG
            mount_cmd = ['hdiutil', 'attach', str(self.downloaded_file_path), '-nobrowse']
            mount_result = subprocess.run(mount_cmd, capture_output=True, text=True)
            
            if mount_result.returncode != 0:
                raise Exception(f"无法挂载DMG: {mount_result.stderr}")
            
            # 查找挂载点 - 改进解析逻辑
            mount_point = None
            logger.info(f"hdiutil输出:\n{mount_result.stdout}")
            
            # 等待挂载完成
            import time
            time.sleep(2)
            
            # 通用方法：扫描所有挂载点，找到包含.app的那个
            app_source = None
            app_name = None
            
            # 检查所有当前的挂载点
            volumes_after = set(os.listdir('/Volumes/')) if os.path.exists('/Volumes/') else set()
            logger.info(f"当前所有挂载点: {volumes_after}")
            
            # 安全地查找新挂载的包含目标应用的挂载点
            new_volumes = volumes_after - volumes_before
            logger.info(f"新挂载的卷: {new_volumes}")
            
            # 只检查新挂载的卷，避免误操作已有的应用
            for volume in new_volumes:
                volume_path = f"/Volumes/{volume}"
                try:
                    if os.path.isdir(volume_path):
                        contents = os.listdir(volume_path)
                        logger.info(f"检查新挂载点 {volume}: {contents}")
                        
                        # 查找.app文件
                        app_files = [f for f in contents if f.endswith('.app')]
                        if app_files:
                            # 验证是否是我们期望的应用
                            candidate_app = app_files[0]
                            if self._is_valid_target_app(candidate_app, volume_path):
                                app_source = os.path.join(volume_path, candidate_app)
                                app_name = candidate_app
                                mount_point = volume_path
                                logger.info(f"确认目标应用: {app_name} 在 {mount_point}")
                                break
                            else:
                                logger.warning(f"跳过非目标应用: {candidate_app}")
                except Exception as e:
                    logger.debug(f"跳过挂载点 {volume}: {e}")
                    continue
            
            # 如果在新挂载点中没找到，回退到检查已知的DMG挂载点名称
            if not app_source:
                logger.info("在新挂载点中未找到，检查已知的DMG挂载点...")
                # 已知的可能挂载点名称
                known_mount_names = [
                    "伊利奶牛选配",
                    "伊利奶牛选配 1", 
                    "伊利奶牛选配 2",
                    "伊利奶牛选配 3",
                    "Genetic Improve",
                    "GeneticImprove",
                    "伊利选配",
                    "奶牛育种智选报告专家"
                ]
                
                for mount_name in known_mount_names:
                    if mount_name in volumes_after:
                        volume_path = f"/Volumes/{mount_name}"
                        try:
                            if os.path.isdir(volume_path):
                                contents = os.listdir(volume_path)
                                app_files = [f for f in contents if f.endswith('.app')]
                                if app_files:
                                    candidate_app = app_files[0]
                                    if self._is_valid_target_app(candidate_app, volume_path):
                                        app_source = os.path.join(volume_path, candidate_app)
                                        app_name = candidate_app
                                        mount_point = volume_path
                                        logger.info(f"在已知挂载点找到目标应用: {app_name} 在 {mount_name}")
                                        break
                        except Exception as e:
                            logger.debug(f"检查挂载点 {mount_name} 失败: {e}")
                            continue
            
            if not app_source or not app_name:
                raise Exception(f"在所有挂载点中未找到.app文件。可用挂载点: {list(volumes_after)}")
            
            self.status_label.setText(f"正在复制应用程序 {app_name}...")
            
            # 目标路径
            target_app = f"/Applications/{app_name}"
            
            # macOS最佳实践：直接显示手动安装指导，不进行自动安装
            logger.info("macOS平台采用手动安装方式，避免权限和应用包问题")
            self._show_manual_install_guide(app_source, target_app)
            return
            
            # 用户手动安装后，DMG保持挂载状态以便用户操作
            # 不自动卸载DMG，让用户完成安装后自行处理
            self.status_label.setText("请按照指导完成手动安装")
            
            # 显示安全验证指导（如果用户需要）
            self._show_security_guide()
            
        except subprocess.CalledProcessError as e:
            self._show_error(f"安装失败: {e}")
        except Exception as e:
            self._show_error(f"安装出错: {e}")
    
    def _install_windows_exe(self):
        """安装Windows EXE包"""
        import subprocess
        
        try:
            self.status_label.setText("正在启动安装程序...")
            
            # 启动安装程序（静默模式）
            install_cmd = [str(self.downloaded_file_path), '/S']  # /S 为静默安装参数
            
            subprocess.Popen(install_cmd)
            
            self.status_label.setText("安装程序已启动，应用即将退出...")
            
            # 延迟3秒后退出，让安装程序接管
            QTimer.singleShot(3000, self._exit_for_update)
            
        except Exception as e:
            self._show_error(f"启动安装程序失败: {e}")
    
    def _restart_application(self, app_path: str):
        """重启应用程序"""
        import subprocess
        import sys
        
        try:
            # 启动新版本应用
            subprocess.Popen(['open', app_path])
            
            # 退出当前应用
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"重启应用失败: {e}")
            sys.exit(0)
    
    def _handle_macos_security(self, app_path: str):
        """处理macOS安全验证问题"""
        import subprocess
        import os
        from pathlib import Path
        
        try:
            # 只尝试简单的隔离属性移除，不使用任何可能需要权限的命令
            subprocess.run(['xattr', '-r', '-d', 'com.apple.quarantine', app_path], 
                         check=False, capture_output=True, timeout=5)
            logger.info(f"已尝试移除应用隔离属性: {app_path}")
            
        except Exception as e:
            logger.info(f"无法自动处理安全验证，用户需要手动允许应用运行: {e}")
            # 完全不执行任何其他操作
    
    def _is_valid_target_app(self, app_name: str, volume_path: str) -> bool:
        """验证是否是我们要更新的目标应用"""
        import os
        
        try:
            # 1. 检查应用名称是否包含关键词
            app_keywords = ['genetic', 'improve', '遗传', '改良', '选配', '奶牛', '伊利']
            app_name_lower = app_name.lower()
            name_match = any(keyword in app_name_lower for keyword in app_keywords)
            
            # 2. 检查应用包内的Info.plist
            app_path = os.path.join(volume_path, app_name)
            info_plist_path = os.path.join(app_path, 'Contents', 'Info.plist')
            
            bundle_match = False
            if os.path.exists(info_plist_path):
                try:
                    with open(info_plist_path, 'r', encoding='utf-8', errors='ignore') as f:
                        plist_content = f.read()
                        # 检查Bundle ID或应用名称
                        bundle_keywords = ['genetic', 'improve', 'cattle', 'breeding', '遗传改良']
                        bundle_match = any(keyword in plist_content.lower() for keyword in bundle_keywords)
                except:
                    pass
            
            # 3. 检查应用大小（应该是一个合理的大小）
            size_match = False
            try:
                # 计算应用包大小
                import subprocess
                result = subprocess.run(['du', '-s', app_path], capture_output=True, text=True)
                if result.returncode == 0:
                    size_kb = int(result.stdout.split()[0])
                    # 期望应用大小在10MB-1GB之间
                    size_match = 10000 < size_kb < 1000000
            except:
                pass
            
            logger.info(f"应用验证 {app_name}: 名称匹配={name_match}, Bundle匹配={bundle_match}, 大小合理={size_match}")
            
            # 至少要满足两个条件
            return sum([name_match, bundle_match, size_match]) >= 2
            
        except Exception as e:
            logger.error(f"验证应用时出错: {e}")
            return False
    
    def _remove_app_with_permission(self, app_path: str) -> bool:
        """使用GUI方式安全删除应用"""
        import subprocess
        import shutil
        import os
        from PyQt6.QtCore import QTimer
        
        # 首先尝试使用Python shutil直接删除（不阻塞GUI）
        try:
            if os.path.exists(app_path):
                shutil.rmtree(app_path)
                logger.info("通过Python shutil成功删除应用")
                return True
        except PermissionError:
            logger.info("Python删除权限不足，需要使用系统权限")
        except Exception as e:
            logger.warning(f"Python删除失败: {e}")
        
        # 完全跳过管理员权限要求，直接返回False让系统尝试其他安装方式
        logger.info("跳过管理员权限删除，将使用智能安装策略")
        return False
    
    def _show_manual_install_guide(self, app_source: str, target_app: str):
        """显示手动安装指导"""
        from PyQt6.QtWidgets import QMessageBox, QPushButton
        import subprocess
        import os
        
        app_name = os.path.basename(target_app)
        mount_point = os.path.dirname(app_source)
        
        # 获取下载的DMG文件路径
        dmg_file_path = str(self.downloaded_file_path) if hasattr(self, 'downloaded_file_path') else "未知"
        
        guide_message = f"""📦 手动安装新版本

新版本已下载完成，请手动安装：

1️⃣ 将 "{app_name}" 拖拽到 "Applications" 文件夹
2️⃣ 如提示替换现有应用，点击"替换"
3️⃣ macOS会自动处理版本替换
4️⃣ 安装完成后可删除此DMG文件

下载文件位置：
{dmg_file_path}

完成后从Applications文件夹启动新版本"""
        
        # 创建自定义消息框，确保在暗色模式下可见
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("手动安装指导")
        msg_box.setText(guide_message)
        msg_box.setIcon(QMessageBox.Icon.Information)
        
        # 设置样式确保在暗色模式下可见
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: palette(window);
                color: palette(window-text);
            }
            QMessageBox QLabel {
                color: palette(window-text);
                font-size: 14px;
                padding: 10px;
            }
            QMessageBox QPushButton {
                background-color: palette(button);
                color: palette(button-text);
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
        """)
        
        # 添加自定义按钮
        open_downloads_btn = msg_box.addButton("打开下载文件夹", QMessageBox.ButtonRole.ActionRole)
        msg_box.addButton(QMessageBox.StandardButton.Ok)
        
        msg_box.exec()
        
        # 如果用户点击了"打开下载文件夹"按钮
        if msg_box.clickedButton() == open_downloads_btn:
            # 打开下载文件所在的文件夹并选中文件
            if hasattr(self, 'downloaded_file_path') and self.downloaded_file_path.exists():
                try:
                    # macOS: 使用open命令并选中文件
                    subprocess.run(['open', '-R', str(self.downloaded_file_path)], check=False)
                    logger.info(f"已打开并选中下载文件: {self.downloaded_file_path}")
                except:
                    # 备选：只打开文件夹
                    try:
                        subprocess.run(['open', str(self.downloaded_file_path.parent)], check=False)
                        logger.info(f"已打开下载文件夹: {self.downloaded_file_path.parent}")
                    except:
                        pass
        
        # 打开Finder到挂载点
        try:
            subprocess.run(['open', mount_point], check=False)
            logger.info(f"已在Finder中打开: {mount_point}")
        except:
            pass
        
        # 打开Applications文件夹
        try:
            subprocess.run(['open', '/Applications'], check=False)
            logger.info("已打开Applications文件夹")
        except:
            pass
        
        # 不自动重启，让用户手动启动新版本
        logger.info("用户需要手动安装完成后启动新版本")
    
    def _copy_app_with_permission(self, source_path: str, target_path: str) -> bool:
        """简单复制应用，失败就返回False"""
        import shutil
        import os
        
        try:
            # 确保目标目录存在
            target_dir = os.path.dirname(target_path)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            
            # 如果目标已存在，先删除
            if os.path.exists(target_path):
                shutil.rmtree(target_path)
            
            # 复制应用
            shutil.copytree(source_path, target_path)
            logger.info("成功复制应用")
            return True
                
        except Exception as e:
            logger.warning(f"复制应用失败: {e}")
            return False
    
    def _show_security_guide(self):
        """显示安全验证指导"""
        from PyQt6.QtWidgets import QMessageBox
        
        guide_message = """🔒 安全提示

如果系统提示"无法验证开发者"：

1️⃣ 右键点击应用 → 选择"打开"
2️⃣ 或在"系统偏好设置" → "安全性与隐私" → "通用"中点击"仍要打开"

这是正常的macOS安全机制，应用本身是安全的。"""
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("安装完成")
        msg_box.setText(guide_message)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.exec()
    
    def _exit_for_update(self):
        """为更新而退出程序"""
        import sys
        logger.info("为更新退出应用程序")
        sys.exit(0)
    
    
    def _show_error(self, message: str):
        """显示错误信息"""
        self.update_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"❌ {message}")
        
        QMessageBox.critical(self, "更新错误", 
                           f"{message}\n\n请检查网络连接后重试，或联系技术支持。")
    
    def closeEvent(self, event):
        """处理用户关闭对话框的操作"""
        # 弹出确认对话框
        reply = QMessageBox.question(
            self, 
            "确认退出程序", 
            "关闭更新窗口将退出整个程序。\n\n"
            "注意：本次更新涉及重要逻辑，跳过更新将无法使用程序。\n"
            "请完成更新！\n\n"
            "确定要退出程序吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 用户确认退出，停止下载线程（如果正在运行）
            if self.download_thread and self.download_thread.isRunning():
                self.download_thread.quit()
                self.download_thread.wait()
            
            logger.info("用户选择退出程序而不是进行强制更新")
            
            # 设置退出标志并关闭对话框
            self.user_chose_exit = True
            event.accept()  # 允许关闭对话框
            self.reject()  # 返回QDialog.Rejected状态
        else:
            event.ignore()  # 取消关闭
    
    def keyPressEvent(self, event):
        """处理键盘按键事件"""
        if event.key() == Qt.Key.Key_Escape:
            # ESC键触发关闭事件，会通过closeEvent处理确认
            self.close()
        else:
            super().keyPressEvent(event)

def test_force_update_dialog():
    """测试强制更新对话框"""
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 模拟版本信息
    version_info = {
        'data': {
            'version': '1.0.6',
            'changes': [
                '🔒 重要安全修复：修复数据泄露漏洞',
                '🚨 紧急修复：修复程序崩溃问题',
                '⚡ 性能优化：提升系统运行速度30%',
                '💾 新增功能：增强数据备份机制',
                '🛡️ 系统加固：增强防护能力'
            ],
            'package_size': 52428800,  # 50MB
            'win_download_url': 'https://example.com/update.zip',
            'mac_download_url': 'https://example.com/update.dmg'
        }
    }
    
    # 模拟应用信息
    from .smart_updater import detect_current_installation
    app_info = detect_current_installation()
    
    # 创建对话框
    dialog = ForceUpdateDialog(version_info, app_info)
    
    return dialog.exec()

if __name__ == '__main__':
    result = test_force_update_dialog()
    print(f"对话框结果: {result}")