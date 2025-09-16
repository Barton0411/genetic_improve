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
            
            # 模拟下载过程（实际项目中会进行真实下载）
            for i in range(0, 101, 10):
                self.progress.emit(i, f"正在下载... {i}%")
                self.msleep(200)  # 模拟下载时间
            
            self.progress.emit(100, "下载完成，准备更新...")
            self.finished.emit(True, "下载成功")
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            self.finished.emit(False, str(e))

class ForceUpdateDialog(QDialog):
    """强制更新对话框"""
    
    def __init__(self, version_info: Dict, app_info: Dict, parent=None):
        super().__init__(parent)
        self.version_info = version_info
        self.app_info = app_info
        self.download_thread = None
        self.setupUI()
        
    def setupUI(self):
        """设置用户界面"""
        self.setWindowTitle("重要更新 - 伊利奶牛选配")
        self.setFixedSize(800, 620)
        self.setModal(True)
        
        # 禁用关闭按钮
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | 
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
            changes_text.setText(changes)
        elif isinstance(changes, list):
            content = "\n".join([f"• {change}" for change in changes])
            changes_text.setText(content)
        else:
            changes_text.setText("• 重要系统更新和安全修复\n• 修复已知问题\n• 提升系统稳定性")
        
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
        
        data = self.version_info.get('data', {})
        
        if self.app_info['platform'] == 'windows':
            return data.get('win_download_url', '')
        elif self.app_info['platform'] == 'darwin':
            return data.get('mac_download_url', '')
        else:
            return data.get('linux_download_url', '')
    
    def _start_download(self, package_url: str):
        """开始下载更新包"""
        
        # 设置保存路径
        temp_dir = Path(self.app_info['user_data_dir']) / 'temp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        version = self.version_info.get('data', {}).get('version', 'unknown')
        save_path = temp_dir / f"update_package_{version}.zip"
        
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
            self.status_label.setText("下载完成，正在准备更新...")
            
            # 延迟一秒然后开始实际更新
            QTimer.singleShot(1000, self._execute_update)
            
        else:
            self._show_error(f"下载失败: {message}")
    
    def _execute_update(self):
        """执行实际更新"""
        
        try:
            self.status_label.setText("正在启动更新程序，即将重启应用...")
            
            print("🔄 模拟更新流程:")
            print("   1. 启动独立更新器")
            print("   2. 备份当前版本")
            print("   3. 替换程序文件")
            print("   4. 重启新版本")
            print("✅ 强制更新测试成功！")
            
            # 在实际环境中，这里会调用智能更新器
            # 延迟2秒后退出（模拟）
            QTimer.singleShot(2000, self._finish_test)
                
        except Exception as e:
            logger.error(f"执行更新失败: {e}", exc_info=True)
            self._show_error(f"执行更新失败: {e}")
    
    def _finish_test(self):
        """完成测试"""
        self.status_label.setText("✅ 测试成功！更新流程完整")
        self.accept()  # 关闭对话框
    
    def _show_error(self, message: str):
        """显示错误信息"""
        self.update_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"❌ {message}")
        
        QMessageBox.critical(self, "更新错误", 
                           f"{message}\n\n请检查网络连接后重试，或联系技术支持。")
    
    def closeEvent(self, event):
        """阻止用户关闭对话框"""
        event.ignore()
        
        QMessageBox.warning(self, "无法关闭", 
                           "为确保系统安全，必须完成更新后才能使用程序。\n"
                           "请点击'立即更新'按钮完成更新。")
    
    def keyPressEvent(self, event):
        """阻止ESC键关闭对话框"""
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
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