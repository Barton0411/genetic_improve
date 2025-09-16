#!/usr/bin/env python3
"""
测试权限处理是否会阻塞GUI
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QTextEdit
from PyQt6.QtCore import QTimer, QThread, pyqtSignal
import logging

logging.basicConfig(level=logging.INFO)

class PermissionTestWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("权限处理测试")
        self.setGeometry(100, 100, 500, 400)
        
        layout = QVBoxLayout()
        
        self.status_label = QLabel("GUI状态：正常")
        layout.addWidget(self.status_label)
        
        self.test_button = QPushButton("测试权限处理（不应阻塞GUI）")
        self.test_button.clicked.connect(self.test_permission)
        layout.addWidget(self.test_button)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        layout.addWidget(self.log_text)
        
        # 添加一个测试GUI响应性的计时器
        self.gui_timer = QTimer()
        self.gui_timer.timeout.connect(self.update_gui_status)
        self.gui_timer.start(500)  # 每500ms更新一次
        
        self.counter = 0
        
        self.setLayout(layout)
    
    def update_gui_status(self):
        """更新GUI状态，用于测试响应性"""
        self.counter += 1
        self.status_label.setText(f"GUI状态：正常运行 - 计数器: {self.counter}")
    
    def log_message(self, message):
        """添加日志消息"""
        self.log_text.append(message)
        print(message)
    
    def test_permission(self):
        """测试权限处理"""
        self.log_message("🧪 开始测试权限处理...")
        self.test_button.setEnabled(False)
        
        # 导入权限处理方法
        from core.update.force_update_dialog_clean import ForceUpdateDialog
        
        # 创建一个临时测试文件
        test_file = "/tmp/test_permission_file.txt"
        try:
            with open(test_file, 'w') as f:
                f.write("这是一个测试文件")
            self.log_message(f"✅ 创建测试文件: {test_file}")
        except Exception as e:
            self.log_message(f"❌ 创建测试文件失败: {e}")
            self.test_button.setEnabled(True)
            return
        
        # 创建ForceUpdateDialog实例来测试权限方法
        dialog = ForceUpdateDialog(
            version_info={'data': {'version': '1.0.0', 'changes': []}},
            app_info={'platform': 'darwin', 'app_root': '/tmp', 'user_data_dir': '/tmp'}
        )
        
        # 测试删除权限处理
        self.log_message("🔄 测试权限删除方法...")
        
        # 这个调用不应该阻塞GUI
        try:
            result = dialog._remove_app_with_permission(test_file)
            if result:
                self.log_message("✅ 权限删除测试成功")
            else:
                self.log_message("⚠️ 权限删除失败，但GUI没有阻塞")
        except Exception as e:
            self.log_message(f"❌ 权限删除出错: {e}")
        
        # 清理
        try:
            if os.path.exists(test_file):
                os.remove(test_file)
                self.log_message("🧹 清理测试文件")
        except:
            pass
        
        self.log_message("✅ 权限处理测试完成")
        self.test_button.setEnabled(True)

def main():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    widget = PermissionTestWidget()
    widget.show()
    
    print("🧪 权限处理GUI测试启动")
    print("   点击按钮测试权限处理")
    print("   观察计数器是否持续更新（表示GUI没有阻塞）")
    
    return app.exec()

if __name__ == '__main__':
    result = main()
    sys.exit(result)