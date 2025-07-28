# example_usage.py
# 阿里云登录模块使用示例

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from login_dialog import LoginDialog, show_login_dialog

class MainWindow(QMainWindow):
    """主窗口示例"""
    
    def __init__(self, username):
        super().__init__()
        self.username = username
        self.setWindowTitle(f"欢迎用户: {username}")
        self.setGeometry(100, 100, 600, 400)
        
        # 创建中央widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout()
        
        # 添加欢迎标签
        welcome_label = QLabel(f"欢迎您，{username}！")
        welcome_label.setStyleSheet("font-size: 16px; padding: 20px;")
        layout.addWidget(welcome_label)
        
        central_widget.setLayout(layout)

def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 方法1：直接使用show_login_dialog函数
    success, username = show_login_dialog(title="系统登录", use_encryption=True)
    
    if success:
        # 登录成功，显示主窗口
        main_window = MainWindow(username)
        main_window.show()
        return app.exec()
    else:
        # 登录失败或取消，退出程序
        return 0

def example_with_dialog_object():
    """使用LoginDialog对象的示例"""
    app = QApplication(sys.argv)
    
    # 方法2：创建LoginDialog对象
    login_dialog = LoginDialog(title="自定义登录", use_encryption=True)
    
    if login_dialog.exec() == LoginDialog.DialogCode.Accepted:
        username = login_dialog.get_username()
        main_window = MainWindow(username)
        main_window.show()
        return app.exec()
    else:
        return 0

def example_without_encryption():
    """不使用加密配置的示例"""
    app = QApplication(sys.argv)
    
    # 使用明文配置（不推荐用于生产环境）
    success, username = show_login_dialog(
        title="测试登录", 
        use_encryption=False
    )
    
    if success:
        main_window = MainWindow(username)
        main_window.show()
        return app.exec()
    else:
        return 0

if __name__ == "__main__":
    # 运行主示例
    sys.exit(main())
    
    # 要运行其他示例，请注释上面的行并取消注释下面的行：
    # sys.exit(example_with_dialog_object())
    # sys.exit(example_without_encryption()) 