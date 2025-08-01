import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import Qt

# 延迟导入重量级模块
def lazy_import():
    global MainWindow, LoginDialog, VideoSplashScreen
    from gui.main_window import MainWindow
    from gui.login_dialog import LoginDialog
    from gui.splash_screen import VideoSplashScreen

def main():
    # 设置项目根目录环境变量
    root_dir = Path(__file__).parent
    os.environ['GENETIC_IMPROVE_ROOT'] = str(root_dir)
    
    app = QApplication(sys.argv)
    
    # 延迟导入模块
    lazy_import()
    
    # 创建并显示启动画面
    splash = VideoSplashScreen()
    splash.show()
    splash.startVideo()
    
    # 显示登录对话框
    login_dialog = LoginDialog()
    
    # 将登录对话框移动到屏幕中下位置
    screen = app.primaryScreen().geometry()
    dialog_geometry = login_dialog.geometry()
    x = (screen.width() - dialog_geometry.width()) // 2  # 水平居中
    y = int(screen.height() * 0.55)  # 距离顶部55%的位置
    login_dialog.move(x, y)
    if login_dialog.exec() == QDialog.DialogCode.Accepted:
        # 登录成功，停止视频播放并隐藏启动画面
        splash.stopVideo()
        splash.hide()
        # 创建主窗口并最大化显示
        window = MainWindow(username=login_dialog.username)
        window.showMaximized()
    else:
        # 登录取消或失败，退出程序
        splash.stopVideo()
        sys.exit()

    return app.exec()

if __name__ == "__main__":
    sys.exit(main())