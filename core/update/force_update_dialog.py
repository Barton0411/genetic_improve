#!/usr/bin/env python3
"""
强制更新对话框 - 不可关闭，必须更新
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
            
            response = requests.get(self.url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            mb_downloaded = downloaded_size / 1024 / 1024
                            mb_total = total_size / 1024 / 1024
                            status = f"已下载 {mb_downloaded:.1f}MB / {mb_total:.1f}MB"
                            self.progress.emit(progress, status)
            
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
        self.setFixedSize(600, 500)
        self.setModal(True)
        
        # 禁用关闭按钮
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | 
                           Qt.WindowType.WindowTitleHint)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 20, 30, 20)
        
        # 警告图标和标题
        header_layout = QHBoxLayout()
        
        # 警告图标 (使用系统警告图标)
        icon_label = QLabel()
        icon_label.setPixmap(self.style().standardPixmap(self.style().StandardPixmap.SP_MessageBoxWarning))
        header_layout.addWidget(icon_label)
        
        # 标题
        title_label = QLabel("检测到重要更新")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #d32f2f;")  # 红色警告
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # 重要提示
        warning_frame = QFrame()
        warning_frame.setStyleSheet("""
            QFrame {
                background-color: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 8px;
                padding: 15px;
            }
        """)\n        warning_layout = QVBoxLayout(warning_frame)\n        \n        warning_text = QLabel(\n            \"⚠️ 为了确保系统安全和功能正常，必须立即更新到最新版本。\\n\"\n            \"本次更新包含重要的安全修复和功能改进，无法跳过。\"\n        )\n        warning_text.setWordWrap(True)\n        warning_text.setStyleSheet(\"color: #856404; font-weight: bold;\")\n        warning_layout.addWidget(warning_text)\n        \n        layout.addWidget(warning_frame)\n        \n        # 版本信息\n        version_frame = QFrame()\n        version_frame.setFrameStyle(QFrame.Shape.Box)\n        version_frame.setStyleSheet(\"QFrame { border: 1px solid #ddd; border-radius: 6px; padding: 10px; }\")\n        version_layout = QVBoxLayout(version_frame)\n        \n        from version import get_version\n        current_label = QLabel(f\"当前版本: {get_version()}\")\n        version_layout.addWidget(current_label)\n        \n        latest_version = self.version_info.get('data', {}).get('version') or self.version_info.get('version')\n        latest_label = QLabel(f\"最新版本: {latest_version}\")\n        latest_font = QFont()\n        latest_font.setBold(True)\n        latest_label.setFont(latest_font)\n        latest_label.setStyleSheet(\"color: #2e7d32;\")\n        version_layout.addWidget(latest_label)\n        \n        layout.addWidget(version_frame)\n        \n        # 更新内容\n        changes_label = QLabel(\"更新内容:\")\n        changes_label.setFont(QFont(\"Arial\", 10, QFont.Weight.Bold))\n        layout.addWidget(changes_label)\n        \n        changes_text = QTextEdit()\n        changes_text.setMaximumHeight(120)\n        changes_text.setReadOnly(True)\n        \n        # 填充更新内容\n        changes = self.version_info.get('data', {}).get('changes') or self.version_info.get('changes', [])\n        if isinstance(changes, str):\n            changes_text.setText(changes)\n        elif isinstance(changes, list):\n            content = \"\\n\".join([f\"• {change}\" for change in changes])\n            changes_text.setText(content)\n        else:\n            changes_text.setText(\"重要系统更新和安全修复\")\n        \n        layout.addWidget(changes_text)\n        \n        # 进度区域\n        progress_frame = QFrame()\n        progress_frame.setStyleSheet(\"QFrame { border: 1px solid #ddd; border-radius: 6px; padding: 15px; }\")\n        progress_layout = QVBoxLayout(progress_frame)\n        \n        self.status_label = QLabel(\"点击下方按钮开始更新\")\n        progress_layout.addWidget(self.status_label)\n        \n        self.progress_bar = QProgressBar()\n        self.progress_bar.setVisible(False)\n        progress_layout.addWidget(self.progress_bar)\n        \n        layout.addWidget(progress_frame)\n        \n        # 按钮区域\n        button_layout = QHBoxLayout()\n        button_layout.addStretch()\n        \n        self.update_btn = QPushButton(\"立即更新\")\n        self.update_btn.clicked.connect(self.start_update)\n        self.update_btn.setStyleSheet(\"\"\"\n            QPushButton {\n                background-color: #2196F3;\n                color: white;\n                border: none;\n                padding: 12px 24px;\n                border-radius: 6px;\n                font-weight: bold;\n                font-size: 14px;\n            }\n            QPushButton:hover {\n                background-color: #1976D2;\n            }\n            QPushButton:pressed {\n                background-color: #1565C0;\n            }\n            QPushButton:disabled {\n                background-color: #ccc;\n            }\n        \"\"\")\n        self.update_btn.setDefault(True)\n        button_layout.addWidget(self.update_btn)\n        \n        layout.addLayout(button_layout)\n        \n        # 添加说明文字\n        note_label = QLabel(\n            \"注意: 更新过程中请勿关闭程序，您的项目数据和设置将会保留。\"\n        )\n        note_label.setStyleSheet(\"color: #666; font-size: 11px;\")\n        note_label.setWordWrap(True)\n        layout.addWidget(note_label)\n        \n        # 安装位置信息\n        location_label = QLabel(f\"安装位置: {self.app_info['app_root']}\")\n        location_label.setStyleSheet(\"color: #888; font-size: 10px;\")\n        layout.addWidget(location_label)\n        \n    def start_update(self):\n        \"\"\"开始更新过程\"\"\"\n        \n        try:\n            self.update_btn.setEnabled(False)\n            self.progress_bar.setVisible(True)\n            self.status_label.setText(\"正在准备更新...\")\n            \n            # 导入智能更新器\n            from .smart_updater import SmartUpdater\n            \n            # 创建更新器实例\n            self.updater = SmartUpdater()\n            \n            # 准备更新信息\n            update_info = {\n                'version': self.version_info.get('data', {}).get('version') or self.version_info.get('version'),\n                'package_url': self._get_package_url(),\n                'package_size': self.version_info.get('data', {}).get('package_size', 0),\n                'md5': self.version_info.get('data', {}).get('md5', ''),\n                'force_update': True\n            }\n            \n            # 开始下载\n            self._start_download(update_info)\n            \n        except Exception as e:\n            logger.error(f\"启动更新失败: {e}\", exc_info=True)\n            self._show_error(f\"启动更新失败: {e}\")\n    \n    def _get_package_url(self) -> str:\n        \"\"\"获取适合当前平台的下载URL\"\"\"\n        \n        data = self.version_info.get('data', {})\n        \n        if self.app_info['platform'] == 'windows':\n            return data.get('win_download_url', '')\n        elif self.app_info['platform'] == 'darwin':\n            return data.get('mac_download_url', '')\n        else:\n            return data.get('linux_download_url', '')\n    \n    def _start_download(self, update_info: Dict):\n        \"\"\"开始下载更新包\"\"\"\n        \n        package_url = update_info['package_url']\n        if not package_url:\n            self._show_error(\"无法获取更新包下载地址\")\n            return\n        \n        # 设置保存路径\n        temp_dir = Path(self.app_info['user_data_dir']) / 'temp'\n        temp_dir.mkdir(parents=True, exist_ok=True)\n        save_path = temp_dir / f\"update_package_{update_info['version']}.zip\"\n        \n        # 创建下载线程\n        self.download_thread = DownloadThread(package_url, str(save_path))\n        self.download_thread.progress.connect(self._on_download_progress)\n        self.download_thread.finished.connect(self._on_download_finished)\n        \n        # 开始下载\n        self.download_thread.start()\n    \n    def _on_download_progress(self, percent: int, status: str):\n        \"\"\"下载进度更新\"\"\"\n        self.progress_bar.setValue(percent)\n        self.status_label.setText(status)\n    \n    def _on_download_finished(self, success: bool, message: str):\n        \"\"\"下载完成处理\"\"\"\n        \n        if success:\n            self.status_label.setText(\"下载完成，正在准备更新...\")\n            \n            # 延迟一秒然后开始实际更新\n            QTimer.singleShot(1000, self._execute_update)\n            \n        else:\n            self._show_error(f\"下载失败: {message}\")\n    \n    def _execute_update(self):\n        \"\"\"执行实际更新\"\"\"\n        \n        try:\n            self.status_label.setText(\"正在启动更新程序，即将重启应用...\")\n            \n            # 这里调用智能更新器的强制更新功能\n            update_info = {\n                'version': self.version_info.get('data', {}).get('version'),\n                'package_url': self._get_package_url(),\n                'package_size': self.version_info.get('data', {}).get('package_size', 0),\n                'md5': self.version_info.get('data', {}).get('md5', ''),\n                'force_update': True\n            }\n            \n            success = self.updater.prepare_forced_update(update_info)\n            \n            if success:\n                # 更新准备成功，程序即将退出\n                self.status_label.setText(\"更新程序已启动，应用即将重启...\")\n                \n                # 延迟2秒后退出\n                QTimer.singleShot(2000, self._exit_for_update)\n            else:\n                self._show_error(\"无法启动更新程序\")\n                \n        except Exception as e:\n            logger.error(f\"执行更新失败: {e}\", exc_info=True)\n            self._show_error(f\"执行更新失败: {e}\")\n    \n    def _exit_for_update(self):\n        \"\"\"为更新而退出程序\"\"\"\n        logger.info(\"为更新退出应用程序\")\n        sys.exit(0)\n    \n    def _show_error(self, message: str):\n        \"\"\"显示错误信息\"\"\"\n        self.update_btn.setEnabled(True)\n        self.progress_bar.setVisible(False)\n        self.status_label.setText(f\"❌ {message}\")\n        \n        QMessageBox.critical(self, \"更新错误\", \n                           f\"{message}\\n\\n请检查网络连接后重试，或联系技术支持。\")\n    \n    def closeEvent(self, event):\n        \"\"\"阻止用户关闭对话框\"\"\"\n        event.ignore()\n        \n        QMessageBox.warning(self, \"无法关闭\", \n                           \"为确保系统安全，必须完成更新后才能使用程序。\\n\"\n                           \"请点击'立即更新'按钮完成更新。\")\n    \n    def keyPressEvent(self, event):\n        \"\"\"阻止ESC键关闭对话框\"\"\"\n        if event.key() == Qt.Key.Key_Escape:\n            event.ignore()\n        else:\n            super().keyPressEvent(event)\n\ndef test_force_update_dialog():\n    \"\"\"测试强制更新对话框\"\"\"\n    \n    app = QApplication.instance()\n    if app is None:\n        app = QApplication(sys.argv)\n    \n    # 模拟版本信息\n    version_info = {\n        'data': {\n            'version': '1.0.6',\n            'changes': [\n                '重要安全修复',\n                '修复关键数据丢失问题',\n                '优化系统性能',\n                '新增数据备份功能'\n            ],\n            'package_size': 52428800,  # 50MB\n            'win_download_url': 'https://example.com/update.zip',\n            'mac_download_url': 'https://example.com/update.dmg'\n        }\n    }\n    \n    # 模拟应用信息\n    from .smart_updater import detect_current_installation\n    app_info = detect_current_installation()\n    \n    # 创建对话框\n    dialog = ForceUpdateDialog(version_info, app_info)\n    \n    return dialog.exec()\n\nif __name__ == '__main__':\n    result = test_force_update_dialog()\n    print(f\"对话框结果: {result}\")