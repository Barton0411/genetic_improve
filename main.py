import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import Qt, QTimer

# 延迟导入重量级模块
def lazy_import():
    global MainWindow, LoginDialog, VideoSplashScreen
    from gui.main_window import MainWindow
    from gui.login_dialog import LoginDialog
    from gui.splash_screen import VideoSplashScreen

def main():
    # 设置日志记录
    import logging
    log_file = Path(__file__).parent / 'app_debug.log'
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.info("Application starting...")
    
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
        # 登录成功，停止视频播放并彻底关闭启动画面
        splash.stopVideo()
        splash.close()  # 使用close而不是hide
        splash.deleteLater()  # 确保启动画面被销毁
        
        # 处理事件确保启动画面完全关闭
        app.processEvents()
        
        # 创建主窗口
        window = MainWindow(username=login_dialog.username)
        
        # 先显示窗口，再最大化（Windows需要这个顺序）
        window.show()
        app.processEvents()
        window.showMaximized()
        
        # Windows特定的窗口激活
        if sys.platform == 'win32':
            # 确保窗口不是最小化状态
            window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)
            window.setWindowState(window.windowState() | Qt.WindowState.WindowActive)
            
        # 强制窗口到前台
        window.raise_()
        window.activateWindow()
        
        # 多次处理事件确保窗口显示
        for _ in range(3):
            app.processEvents()
            
        # 添加日志记录用于调试
        import logging
        logging.info(f"Main window visible: {window.isVisible()}")
        logging.info(f"Main window state: {window.windowState()}")
        
        # 添加延迟检查确保窗口显示
        def check_window_visibility():
            if not window.isVisible():
                logging.warning("Main window not visible after 500ms, forcing show")
                window.show()
                window.raise_()
                window.activateWindow()
                if sys.platform == 'win32':
                    window.setWindowState(Qt.WindowState.WindowMaximized | Qt.WindowState.WindowActive)
            else:
                logging.info("Main window is visible")
                
        QTimer.singleShot(500, check_window_visibility)
    else:
        # 登录取消或失败，退出程序
        splash.stopVideo()
        sys.exit()

    return app.exec()

if __name__ == "__main__":
    sys.exit(main())