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
    # 设置日志记录到用户目录，避免权限问题
    import logging
    from pathlib import Path
    
    # 获取用户AppData目录（Windows）或用户主目录（Mac/Linux）
    if os.name == 'nt':  # Windows
        app_data_dir = Path(os.environ.get('APPDATA', os.path.expanduser('~'))) / 'GeneticImprove'
    else:  # Mac/Linux
        app_data_dir = Path.home() / '.genetic_improve'
    
    # 确保目录存在
    app_data_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = app_data_dir / 'app_debug.log'
    
    try:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        logging.info(f"Application starting... Log file: {log_file}")
    except Exception as e:
        # 如果仍然无法创建日志文件，只使用控制台输出
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        logging.warning(f"Could not create log file {log_file}: {e}. Using console logging only.")
    
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
        try:
            logging.info("Login successful, creating main window...")
            
            # 登录成功，停止视频播放并彻底关闭启动画面
            logging.info("Closing splash screen...")
            splash.stopVideo()
            splash.close()  # 使用close而不是hide
            splash.deleteLater()  # 确保启动画面被销毁
            
            # 处理事件确保启动画面完全关闭
            app.processEvents()
            logging.info("Splash screen closed")
            
            # 登录成功后检查版本更新（延迟到主窗口创建后）
            def check_version_after_login():
                try:
                    import sys
                    import os
                    # 确保当前目录在Python路径中
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    if current_dir not in sys.path:
                        sys.path.insert(0, current_dir)
                    
                    from core.update.version_manager import check_and_handle_updates
                    logging.info("Checking for version updates with smart update system...")
                    should_exit = check_and_handle_updates()
                    if should_exit:
                        logging.info("Force update initiated, application will exit")
                        # 强制更新时立即退出
                        QTimer.singleShot(100, lambda: sys.exit(0))
                    else:
                        logging.info("Version check completed, continuing normal operation")
                except Exception as e:
                    logging.warning(f"Smart update check failed: {e}")
                    import traceback
                    logging.error(f"Smart update traceback: {traceback.format_exc()}")
            
            # 先测试是否能创建简单窗口
            logging.info("Testing simple window creation...")
            from PyQt6.QtWidgets import QWidget
            test_window = QWidget()
            test_window.setWindowTitle("Test")
            test_window.show()
            app.processEvents()
            if test_window.isVisible():
                logging.info("Test window is visible, closing it")
                test_window.close()
            else:
                logging.warning("Test window is not visible!")
            
            # 创建主窗口
            logging.info("Creating MainWindow instance...")
            window = MainWindow(username=login_dialog.username)
            logging.info("MainWindow created successfully")
            
            # 先显示窗口，再最大化（Windows需要这个顺序）
            logging.info("Showing window...")
            window.show()
            app.processEvents()
            
            logging.info("Maximizing window...")
            window.showMaximized()
            
            # Windows特定的窗口激活
            if sys.platform == 'win32':
                logging.info("Applying Windows-specific window activation...")
                # 确保窗口不是最小化状态
                window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)
                window.setWindowState(window.windowState() | Qt.WindowState.WindowActive)
                
            # 强制窗口到前台
            logging.info("Bringing window to foreground...")
            window.raise_()
            window.activateWindow()
            
            # 多次处理事件确保窗口显示
            for i in range(3):
                app.processEvents()
                logging.debug(f"Process events iteration {i+1}")
                
            # 添加日志记录用于调试
            logging.info(f"Main window visible: {window.isVisible()}")
            logging.info(f"Main window state: {window.windowState()}")
            logging.info(f"Main window geometry: {window.geometry()}")
            logging.info(f"Main window position: ({window.x()}, {window.y()})")
            logging.info(f"Main window size: {window.width()}x{window.height()}")
            
            # 添加延迟检查确保窗口显示
            def check_window_visibility():
                try:
                    if not window.isVisible():
                        logging.warning("Main window not visible after 500ms, forcing show")
                        window.show()
                        window.raise_()
                        window.activateWindow()
                        if sys.platform == 'win32':
                            window.setWindowState(Qt.WindowState.WindowMaximized | Qt.WindowState.WindowActive)
                        
                        # 再次检查
                        app.processEvents()
                        if window.isVisible():
                            logging.info("Window is now visible after forcing show")
                        else:
                            logging.error("Window still not visible after forcing show!")
                            # 尝试创建一个简单的测试窗口
                            from PyQt6.QtWidgets import QMessageBox
                            QMessageBox.critical(None, "窗口显示错误", 
                                               "主窗口无法显示。请检查日志文件获取更多信息。\n"
                                               f"日志文件位置: {log_file}")
                    else:
                        logging.info("Main window is visible")
                        
                    # 主窗口显示正常后，先检查应用版本更新，再检查数据库版本
                    QTimer.singleShot(500, check_version_after_login)
                    
                except Exception as e:
                    logging.exception(f"Error in check_window_visibility: {e}")
                    
            QTimer.singleShot(500, check_window_visibility)
            
        except Exception as e:
            logging.exception(f"Error creating or showing main window: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "启动错误", 
                               f"创建主窗口时发生错误:\n{str(e)}\n\n"
                               f"请查看日志文件: {log_file}")
            sys.exit(1)
    else:
        # 登录取消或失败，退出程序
        splash.stopVideo()
        sys.exit()

    return app.exec()

if __name__ == "__main__":
    sys.exit(main())