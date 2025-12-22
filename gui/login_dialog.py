from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QWidget, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
from pathlib import Path
import logging
import requests
from auth.auth_service import AuthService

class LoginDialog(QDialog):
    # 伊起牛API地址
    YQN_API_TEST = "https://yqnapi-sit.yqndairy.com"  # 测试环境
    YQN_API_PROD = "https://yqnapi.yqndairy.com"     # 生产环境

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("伊利奶牛选配 - 登录")
        self.setFixedSize(420, 280)

        # 设置窗口标志，移除WindowStaysOnTopHint避免Windows上的层级问题
        self.setWindowFlags(
            Qt.WindowType.CustomizeWindowHint |   # 自定义窗口外观
            Qt.WindowType.WindowTitleHint |      # 显示标题栏
            Qt.WindowType.WindowCloseButtonHint  # 显示关闭按钮
        )

        # 设置窗口图标
        icon_path = Path(__file__).parent.parent / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.main_layout = QVBoxLayout()

        # 创建Tab控件
        self.tab_widget = QTabWidget()

        # ===== 伊利账号登录Tab =====
        self.yili_tab = QWidget()
        self.yili_layout = QVBoxLayout()

        self.username_label = QLabel("账号:")
        self.username_input = QLineEdit()
        self.yili_layout.addWidget(self.username_label)
        self.yili_layout.addWidget(self.username_input)

        self.password_label = QLabel("密码:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.yili_layout.addWidget(self.password_label)
        self.yili_layout.addWidget(self.password_input)

        self.yili_button_layout = QHBoxLayout()
        self.login_button = QPushButton("登录")
        self.login_button.clicked.connect(self.login)
        self.register_button = QPushButton("注册")
        self.register_button.clicked.connect(self.show_register)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        self.yili_button_layout.addWidget(self.login_button)
        self.yili_button_layout.addWidget(self.register_button)
        self.yili_button_layout.addWidget(self.cancel_button)
        self.yili_layout.addLayout(self.yili_button_layout)

        self.yili_tab.setLayout(self.yili_layout)

        # ===== 伊起牛账号登录Tab =====
        self.yqn_tab = QWidget()
        self.yqn_layout = QVBoxLayout()

        self.yqn_username_label = QLabel("账号:")
        self.yqn_username_input = QLineEdit()
        self.yqn_layout.addWidget(self.yqn_username_label)
        self.yqn_layout.addWidget(self.yqn_username_input)

        self.yqn_password_label = QLabel("密码:")
        self.yqn_password_input = QLineEdit()
        self.yqn_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.yqn_layout.addWidget(self.yqn_password_label)
        self.yqn_layout.addWidget(self.yqn_password_input)

        self.yqn_button_layout = QHBoxLayout()
        self.yqn_login_button = QPushButton("登录")
        self.yqn_login_button.clicked.connect(self.yqn_login)
        self.yqn_cancel_button = QPushButton("取消")
        self.yqn_cancel_button.clicked.connect(self.reject)
        self.yqn_button_layout.addWidget(self.yqn_login_button)
        self.yqn_button_layout.addWidget(self.yqn_cancel_button)
        self.yqn_layout.addLayout(self.yqn_button_layout)

        self.yqn_tab.setLayout(self.yqn_layout)

        # 添加Tab到TabWidget
        self.tab_widget.addTab(self.yili_tab, "选配软件账号")
        self.tab_widget.addTab(self.yqn_tab, "伊起牛账号")

        self.main_layout.addWidget(self.tab_widget)

        # 等待提示
        self.waiting_label_text = QLabel("  正在连接服务器......", self)
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

        self.main_layout.addWidget(self.waiting_widget)
        self.setLayout(self.main_layout)

        # 保存伊起牛登录token
        self.yqn_token = None
        self.login_type = None  # 'yili' 或 'yqn'

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
        self.tab_widget.hide()
        self.waiting_widget.show()

    def show_login_form(self):
        """显示登录界面，隐藏等待提示"""
        self.waiting_widget.hide()
        self.tab_widget.show()

    def login(self):
        """处理伊利账号登录点击事件"""
        username = self.username_input.text()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "提示", "账号和密码不能为空")
            return

        self.show_waiting()
        QTimer.singleShot(100, lambda: self.process_login(username, password))

    def yqn_login(self):
        """处理伊起牛账号登录点击事件"""
        username = self.yqn_username_input.text()
        password = self.yqn_password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "提示", "账号和密码不能为空")
            return

        self.show_waiting()
        QTimer.singleShot(100, lambda: self.process_yqn_login(username, password))

    def process_yqn_login(self, username, password):
        """处理伊起牛账号登录验证"""
        try:
            # 使用生产环境API
            api_url = f"{self.YQN_API_PROD}/auth/login"

            response = requests.post(
                api_url,
                json={"username": username, "password": password},
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            result = response.json()

            if result.get("code") == 200 and result.get("data"):
                # 登录成功
                self.yqn_token = result["data"].get("access_token")
                self.username = username
                self.login_type = "yqn"
                self.accept()
            else:
                self.show_login_form()
                error_msg = result.get("msg") or "账号或密码错误，请重试。"
                QMessageBox.warning(self, "登录失败", error_msg)
                self.yqn_password_input.clear()
                self.yqn_password_input.setFocus()

        except requests.exceptions.Timeout:
            self.show_login_form()
            QMessageBox.critical(self, "连接超时", "连接伊起牛服务器超时，请检查网络后重试。")
        except requests.exceptions.ConnectionError:
            self.show_login_form()
            QMessageBox.critical(self, "网络错误", "无法连接到伊起牛服务器，请检查网络连接。")
        except Exception as e:
            logging.error(f"伊起牛登录错误: {str(e)}")
            self.show_login_form()
            QMessageBox.critical(
                self,
                "登录错误",
                f"登录过程中发生错误: {str(e)}"
            )

    def process_login(self, username, password):
        """处理登录验证（使用API认证服务）"""
        try:
            # 使用API认证服务进行登录验证
            auth_service = AuthService()
            success, message = auth_service.login(username, password)

            if success:
                self.username = username
                self.login_type = "yili"
                self.accept()
            else:
                self.show_login_form()
                QMessageBox.warning(self, "登录失败", message or "账号或密码错误，请重试。")
                self.username_input.clear()
                self.password_input.clear()
                self.username_input.setFocus()

        except Exception as e:
            logging.error(f"登录错误: {str(e)}")
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

    def show_register(self):
        """显示注册对话框"""
        try:
            from gui.register_dialog import show_register_dialog

            # 创建认证服务实例
            auth_service = AuthService()

            # 显示注册对话框
            success, username = show_register_dialog(self, auth_service)

            if success and username:
                # 注册成功，自动填入用户名
                self.username_input.setText(username)
                self.password_input.setFocus()
                QMessageBox.information(
                    self,
                    "注册成功",
                    f"账号 {username} 注册成功！\n请输入密码登录。"
                )
        except Exception as e:
            logging.error(f"注册对话框打开失败: {e}")
            QMessageBox.critical(
                self,
                "错误",
                f"无法打开注册界面: {str(e)}"
            )