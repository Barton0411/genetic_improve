# gui/login_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
from pathlib import Path  # 添加这行
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
        self.setFixedSize(300, 150)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        # 设置窗口图标
        icon_path = Path(__file__).parent.parent / "icon.ico"  # 直接从项目根目录获取
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
            # 使用与 update_manager.py 相同的数据库连接信息
            cloud_engine = create_engine(
                f"mysql+pymysql://{CLOUD_DB_USER}:{CLOUD_DB_PASSWORD}"
                f"@{CLOUD_DB_HOST}:{CLOUD_DB_PORT}/{CLOUD_DB_NAME}?charset=utf8mb4"
            )

            with cloud_engine.connect() as connection:
                # 检查用户名和密码
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
            QMessageBox.critical(self, "数据库连接错误", f"连接数据库时发生错误，请联系管理员。")
            self.username_input.clear()
            self.password_input.clear()
            self.username_input.setFocus()