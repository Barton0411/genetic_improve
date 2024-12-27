# main.py
import sys
from PyQt6.QtWidgets import QApplication, QDialog  # 添加 QDialog
from gui.main_window import MainWindow
from gui.login_dialog import LoginDialog

def main():
    app = QApplication(sys.argv)
    
    # 显示登录对话框
    login_dialog = LoginDialog()
    if login_dialog.exec() == QDialog.DialogCode.Accepted:
        # 登录成功，显示主窗口
        window = MainWindow(username=login_dialog.username)
        window.show()
        sys.exit(app.exec())
    else:
        # 登录取消或失败，退出程序
        sys.exit()

if __name__ == "__main__":
    main()