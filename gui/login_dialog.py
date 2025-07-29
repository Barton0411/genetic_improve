from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
from pathlib import Path  
import logging
from sqlalchemy import create_engine, text
from core.data.update_manager import (
    CLOUD_DB_HOST, CLOUD_DB_PORT, CLOUD_DB_USER, 
    CLOUD_DB_PASSWORD, CLOUD_DB_NAME
)

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("奶牛育种智选报告专家 - 登录")
        self.setFixedSize(350, 200)
        
        # 设置窗口标志，确保总是在最前面
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |  # 窗口保持在最前
            Qt.WindowType.CustomizeWindowHint |   # 自定义窗口外观
            Qt.WindowType.WindowTitleHint |      # 显示标题栏
            Qt.WindowType.WindowCloseButtonHint  # 显示关闭按钮
        )

        # 设置窗口图标
        icon_path = Path(__file__).parent.parent / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.layout = QVBoxLayout()

        # 账号输入
        self.username_label = QLabel("账号:")
        self.username_input = QLineEdit()
        self.layout.addWidget(self.username_label)
        self.layout.addWidget(self.username_input)

        # 密码输入
        self.password_label = QLabel("密码:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.layout.addWidget(self.password_label)
        self.layout.addWidget(self.password_input)

        # 按钮布局
        self.button_layout = QHBoxLayout()
        self.login_button = QPushButton("登录")
        self.login_button.clicked.connect(self.login)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        self.button_layout.addWidget(self.login_button)
        self.button_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.button_layout)

        # 等待提示
        self.waiting_label_text = QLabel("  正在连接数据库......", self)
        self.waiting_label_hint = QLabel("（请等待2-5秒）", self)
        
        waiting_font = QFont("微软雅黑", 15, QFont.Weight.Medium)
        self.waiting_label_text.setFont(waiting_font)
        self.waiting_label_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.waiting_label_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.waiting_layout = QVBoxLayout()
        self.waiting_layout.addWidget(self.waiting_label_text)
        self.waiting_layout.addWidget(self.waiting_label_hint)
        
        self.waiting_widget = QWidget()
        self.waiting_widget.setLayout(self.waiting_layout)
        self.waiting_widget.hide()
        
        self.layout.addWidget(self.waiting_widget)
        self.setLayout(self.layout)

        # 样式设置
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLineEdit {
                padding: 5px;
                min-height: 25px;
                font-size: 14px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QPushButton {
                padding: 5px 15px;
                min-height: 30px;
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)

    def show_waiting(self):
        """显示等待提示，隐藏登录界面"""
        for widget in [
            self.username_label, self.username_input, 
            self.password_label, self.password_input, 
            self.login_button, self.cancel_button
        ]:
            widget.hide()
        self.waiting_widget.show()

    def show_login_form(self):
        """显示登录界面，隐藏等待提示"""
        self.waiting_widget.hide()
        for widget in [
            self.username_label, self.username_input, 
            self.password_label, self.password_input, 
            self.login_button, self.cancel_button
        ]:
            widget.show()

    def login(self):
        """处理登录点击事件"""
        username = self.username_input.text()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "提示", "账号和密码不能为空")
            return

        self.show_waiting()
        QTimer.singleShot(100, lambda: self.process_login(username, password))

    def process_login(self, username, password):
        """处理登录验证"""
        try:
            cloud_engine = create_engine(
                f"mysql+pymysql://{CLOUD_DB_USER}:{CLOUD_DB_PASSWORD}"
                f"@{CLOUD_DB_HOST}:{CLOUD_DB_PORT}/{CLOUD_DB_NAME}?charset=utf8mb4"
            )

            with cloud_engine.connect() as connection:
                result = connection.execute(
                    text("SELECT * FROM `id-pw` WHERE ID=:username AND PW=:password"),
                    {"username": username, "password": password}
                ).fetchone()

                if result:
                    self.username = username
                    self.accept()
                else:
                    self.show_login_form()
                    QMessageBox.warning(self, "登录失败", "账号或密码错误，请重试。")
                    self.username_input.clear()
                    self.password_input.clear()
                    self.username_input.setFocus()

        except Exception as e:
            logging.error(f"数据库连接错误: {str(e)}")
            self.show_login_form()
            
            # 判断错误类型并给出友好提示
            error_message = "无法连接到服务器，请检查网络连接。"
            
            if "Can't connect to MySQL server" in str(e):
                error_message = "无法连接到数据库服务器，请检查您的网络连接是否正常。"
            elif "Access denied" in str(e):
                error_message = "数据库访问被拒绝，请联系管理员。"
            elif "timed out" in str(e).lower():
                error_message = "连接超时，请检查网络连接后重试。"
            elif "nodename nor servname provided" in str(e):
                error_message = "网络连接异常，无法解析服务器地址。\n请检查您的网络设置。"
            
            QMessageBox.critical(
                self, 
                "网络连接错误", 
                error_message + "\n\n如果问题持续存在，请联系技术支持。"
            )
            
            self.username_input.clear()
            self.password_input.clear()
            self.username_input.setFocus()