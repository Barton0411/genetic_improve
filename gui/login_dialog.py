from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QWidget, QCheckBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
from pathlib import Path
import logging
import requests
import keyring
from auth.auth_service import AuthService


class LoginDialog(QDialog):
    # 伊起牛API地址
    YQN_API_TEST = "https://yqnapi-sit.yqndairy.com"  # 测试环境
    YQN_API_PROD = "https://yqnapi.yqndairy.com"     # 生产环境

    # 凭据存储的服务名
    KEYRING_SERVICE_YQN = "GeneticImprove_YQN"
    KEYRING_SERVICE_YILI = "GeneticImprove_YILI"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("伊利奶牛选配 - 登录")
        self.setMinimumSize(420, 220)  # 设置最小尺寸，允许自动扩展

        # 设置窗口标志
        self.setWindowFlags(
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        # 设置窗口图标
        icon_path = Path(__file__).parent.parent / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # 初始化变量
        self.yqn_token = None
        self.login_type = None  # 'yili' 或 'yqn'
        self.username = None
        self.selected_login_type = None  # 当前选择的登录方式
        self._password_from_keyring = False  # 标记密码是否从 keyring 加载

        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(30, 20, 30, 20)

        # ===== 第一步：选择登录方式 =====
        self.selection_widget = QWidget()
        self.selection_layout = QVBoxLayout()
        self.selection_layout.setSpacing(15)

        # 标题
        self.selection_title = QLabel("请选择登录方式")
        self.selection_title.setFont(QFont("微软雅黑", 14, QFont.Weight.Bold))
        self.selection_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selection_layout.addWidget(self.selection_title)

        self.selection_layout.addSpacing(10)

        # 两个登录按钮水平排列
        self.login_type_btn_layout = QHBoxLayout()
        self.login_type_btn_layout.setSpacing(15)

        # 伊起牛登录按钮（左边，绿色）
        self.yqn_select_btn = QPushButton("伊起牛")
        self.yqn_select_btn.setMinimumHeight(50)
        self.yqn_select_btn.setFont(QFont("微软雅黑", 13))
        self.yqn_select_btn.clicked.connect(lambda: self.select_login_type("yqn"))
        self.yqn_select_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
        """)
        self.login_type_btn_layout.addWidget(self.yqn_select_btn)

        # 育种中心登录按钮（右边，蓝色）
        self.yili_select_btn = QPushButton("育种中心")
        self.yili_select_btn.setMinimumHeight(50)
        self.yili_select_btn.setFont(QFont("微软雅黑", 13))
        self.yili_select_btn.clicked.connect(lambda: self.select_login_type("yili"))
        self.yili_select_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.login_type_btn_layout.addWidget(self.yili_select_btn)

        self.selection_layout.addLayout(self.login_type_btn_layout)

        self.selection_layout.addStretch()

        # 取消按钮（灰色）
        self.selection_cancel_btn = QPushButton("取消")
        self.selection_cancel_btn.clicked.connect(self.reject)
        self.selection_cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        self.selection_layout.addWidget(self.selection_cancel_btn)

        self.selection_widget.setLayout(self.selection_layout)

        # ===== 第二步：登录表单 =====
        self.login_form_widget = QWidget()
        self.login_form_layout = QVBoxLayout()
        self.login_form_layout.setSpacing(10)

        # 返回按钮和标题行
        self.header_layout = QHBoxLayout()
        self.back_btn = QPushButton("< 返回")
        self.back_btn.setFixedWidth(60)
        self.back_btn.clicked.connect(self.show_selection)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #3498db;
                border: none;
                text-align: left;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #2980b9;
            }
        """)
        self.header_layout.addWidget(self.back_btn)

        self.login_type_label = QLabel("")
        self.login_type_label.setFont(QFont("微软雅黑", 13, QFont.Weight.Bold))
        self.login_type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_layout.addWidget(self.login_type_label)

        self.header_layout.addSpacing(60)  # 平衡返回按钮的宽度

        self.login_form_layout.addLayout(self.header_layout)

        # 分隔线
        self.separator = QFrame()
        self.separator.setFrameShape(QFrame.Shape.HLine)
        self.separator.setStyleSheet("background-color: #ddd;")
        self.login_form_layout.addWidget(self.separator)

        self.login_form_layout.addSpacing(5)

        # 账号输入
        self.username_label = QLabel("账号:")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入账号")
        self.login_form_layout.addWidget(self.username_label)
        self.login_form_layout.addWidget(self.username_input)

        # 密码输入
        self.password_label = QLabel("密码:")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_form_layout.addWidget(self.password_label)

        # 密码输入框和显示密码复选框
        self.password_row_layout = QHBoxLayout()
        self.password_row_layout.addWidget(self.password_input)

        self.show_password_checkbox = QCheckBox("显示")
        self.show_password_checkbox.stateChanged.connect(self.toggle_password_visibility)
        self.password_row_layout.addWidget(self.show_password_checkbox)

        self.login_form_layout.addLayout(self.password_row_layout)

        # 记住密码复选框
        self.remember_password_checkbox = QCheckBox("记住密码")
        self.remember_password_checkbox.setStyleSheet("font-size: 12px;")
        self.login_form_layout.addWidget(self.remember_password_checkbox)

        self.login_form_layout.addSpacing(10)

        # 按钮行
        self.button_layout = QHBoxLayout()
        self.login_button = QPushButton("登录")
        self.login_button.setMinimumHeight(40)
        self.login_button.clicked.connect(self.do_login)

        self.register_button = QPushButton("注册")
        self.register_button.setMinimumHeight(40)
        self.register_button.clicked.connect(self.show_register)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.setMinimumHeight(40)
        self.cancel_button.clicked.connect(self.reject)

        self.button_layout.addWidget(self.login_button)
        self.button_layout.addWidget(self.register_button)
        self.button_layout.addWidget(self.cancel_button)

        self.login_form_layout.addLayout(self.button_layout)
        self.login_form_layout.addStretch()

        self.login_form_widget.setLayout(self.login_form_layout)
        self.login_form_widget.hide()

        # ===== 等待提示 =====
        self.waiting_widget = QWidget()
        self.waiting_layout = QVBoxLayout()

        self.waiting_label_text = QLabel("正在连接服务器...")
        self.waiting_label_hint = QLabel("（请等待2-5秒）")

        waiting_font = QFont("微软雅黑", 15, QFont.Weight.Medium)
        self.waiting_label_text.setFont(waiting_font)
        self.waiting_label_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.waiting_label_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.waiting_layout.addStretch()
        self.waiting_layout.addWidget(self.waiting_label_text)
        self.waiting_layout.addWidget(self.waiting_label_hint)
        self.waiting_layout.addStretch()

        self.waiting_widget.setLayout(self.waiting_layout)
        self.waiting_widget.hide()

        # 添加到主布局
        self.main_layout.addWidget(self.selection_widget)
        self.main_layout.addWidget(self.login_form_widget)
        self.main_layout.addWidget(self.waiting_widget)

        self.setLayout(self.main_layout)

        # 样式设置
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLabel {
                font-size: 13px;
            }
            QLineEdit {
                padding: 8px;
                min-height: 28px;
                font-size: 14px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
            QPushButton {
                padding: 5px 15px;
                min-height: 32px;
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QCheckBox {
                font-size: 12px;
            }
        """)

    def select_login_type(self, login_type):
        """选择登录方式后显示登录表单"""
        self.selected_login_type = login_type

        # 更新标题和样式
        if login_type == "yqn":
            self.login_type_label.setText("伊起牛账号登录")
            self.login_button.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #219a52;
                }
            """)
            # 伊起牛账号不显示注册按钮
            self.register_button.hide()
        else:
            self.login_type_label.setText("育种中心账号登录")
            self.login_button.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
            """)
            # 育种中心账号显示注册按钮
            self.register_button.show()

        # 清空输入框并重置状态
        self.username_input.clear()
        self.password_input.clear()
        self.show_password_checkbox.setChecked(False)
        self.show_password_checkbox.setEnabled(True)
        self.show_password_checkbox.setToolTip("")
        self.remember_password_checkbox.setChecked(False)
        self._password_from_keyring = False

        # 切换界面
        self.selection_widget.hide()
        self.login_form_widget.show()

        # 尝试加载已保存的凭据
        self._load_saved_credentials()

        # 设置焦点
        if self.username_input.text():
            self.password_input.setFocus()
        else:
            self.username_input.setFocus()

        # 调整窗口大小以适应登录表单
        self.adjustSize()
        self.setMinimumHeight(340)  # 登录表单需要更多高度

    def show_selection(self):
        """返回选择登录方式界面"""
        self.login_form_widget.hide()
        self.waiting_widget.hide()
        self.selection_widget.show()

        # 恢复选择界面的最小高度
        self.setMinimumHeight(220)
        self.resize(420, 220)

    def show_waiting(self):
        """显示等待提示"""
        self.selection_widget.hide()
        self.login_form_widget.hide()
        self.waiting_widget.show()

    def show_login_form(self):
        """显示登录表单"""
        self.waiting_widget.hide()
        self.selection_widget.hide()
        self.login_form_widget.show()

    def toggle_password_visibility(self, state):
        """切换密码的显示/隐藏状态"""
        if self.show_password_checkbox.isChecked():
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

    def do_login(self):
        """处理登录点击事件"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "提示", "账号和密码不能为空")
            return

        self.show_waiting()

        if self.selected_login_type == "yqn":
            logging.info(f"伊起牛登录尝试 - 用户名: {username}, 密码长度: {len(password)}")
            QTimer.singleShot(100, lambda: self.process_yqn_login(username, password))
        else:
            QTimer.singleShot(100, lambda: self.process_yili_login(username, password))

    def process_yqn_login(self, username, password):
        """处理伊起牛账号登录验证"""
        try:
            api_url = f"{self.YQN_API_PROD}/auth/login"

            # 禁用代理，直接连接
            session = requests.Session()
            session.trust_env = False
            session.proxies = {'http': None, 'https': None}

            response = session.post(
                api_url,
                json={"username": username, "password": password},
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            result = response.json()
            logging.info(f"伊起牛API响应 - code: {result.get('code')}, msg: {result.get('msg')}")

            if result.get("code") == 200 and result.get("data"):
                self.yqn_token = result["data"].get("access_token")
                self.username = username
                self.login_type = "yqn"
                logging.info("伊起牛登录成功")

                # 保存或清除凭据
                if self.remember_password_checkbox.isChecked():
                    self._save_credentials(username, password)
                else:
                    self._clear_saved_credentials()

                self.accept()
            else:
                self.show_login_form()
                error_msg = result.get("msg") or "账号或密码错误，请重试。"
                logging.warning(f"伊起牛登录失败: {error_msg}")
                QMessageBox.warning(self, "登录失败", error_msg)
                self.password_input.clear()
                self.password_input.setFocus()

        except requests.exceptions.Timeout:
            self.show_login_form()
            QMessageBox.critical(
                self,
                "连接超时",
                "连接伊起牛服务器超时。\n\n"
                "可能原因：\n"
                "1. 网络连接不稳定\n"
                "2. 当前IP未加入伊起牛API白名单\n\n"
                "解决方案：\n"
                "• 检查网络连接\n"
                "• 尝试连接VPN\n"
                "• 联系伊起牛技术支持添加您的IP到白名单"
            )
        except requests.exceptions.ConnectionError:
            self.show_login_form()
            QMessageBox.critical(
                self,
                "网络错误",
                "无法连接到伊起牛服务器。\n\n"
                "可能原因：\n"
                "1. 网络连接问题\n"
                "2. 当前IP未加入伊起牛API白名单（最常见）\n\n"
                "解决方案：\n"
                "• 检查网络连接\n"
                "• 尝试连接VPN后重试\n"
                "• 联系伊起牛技术支持，提供您的公网IP申请加入白名单"
            )
        except Exception as e:
            logging.error(f"伊起牛登录错误: {str(e)}")
            self.show_login_form()
            QMessageBox.critical(self, "登录错误", f"登录过程中发生错误: {str(e)}")

    def process_yili_login(self, username, password):
        """处理育种中心账号登录验证"""
        try:
            auth_service = AuthService()
            success, message = auth_service.login(username, password)

            if success:
                self.username = username
                self.login_type = "yili"

                # 保存或清除凭据
                if self.remember_password_checkbox.isChecked():
                    self._save_credentials(username, password)
                else:
                    self._clear_saved_credentials()

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

            auth_service = AuthService()
            success, username = show_register_dialog(self, auth_service)

            if success and username:
                self.username_input.setText(username)
                self.password_input.setFocus()
                QMessageBox.information(
                    self,
                    "注册成功",
                    f"账号 {username} 注册成功！\n请输入密码登录。"
                )
        except Exception as e:
            logging.error(f"注册对话框打开失败: {e}")
            QMessageBox.critical(self, "错误", f"无法打开注册界面: {str(e)}")

    def _get_keyring_service(self) -> str:
        """获取当前登录类型对应的 keyring 服务名"""
        if self.selected_login_type == "yqn":
            return self.KEYRING_SERVICE_YQN
        return self.KEYRING_SERVICE_YILI

    def _load_saved_credentials(self):
        """加载已保存的凭据"""
        self._password_from_keyring = False
        try:
            service = self._get_keyring_service()
            username = keyring.get_password(service, "username")
            if username:
                password = keyring.get_password(service, f"password_{username}")
                if password:
                    self.username_input.setText(username)
                    self.password_input.setText(password)
                    self.remember_password_checkbox.setChecked(True)
                    self._password_from_keyring = True
                    self._protect_saved_password()
                    logging.info(f"已加载保存的凭据: {username}")
        except Exception as e:
            logging.warning(f"加载凭据失败: {e}")

    def _protect_saved_password(self):
        """保护已保存的密码：禁用显示、禁止复制"""
        # 禁用显示密码复选框
        self.show_password_checkbox.setEnabled(False)
        self.show_password_checkbox.setChecked(False)
        self.show_password_checkbox.setToolTip("已保存的密码不允许显示")

        # 确保密码框处于密码模式
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        # 连接文本变化信号，当用户修改密码时解除保护
        self.password_input.textChanged.connect(self._on_password_changed)

    def _on_password_changed(self, text):
        """密码框内容变化时的处理"""
        if self._password_from_keyring:
            # 用户开始修改密码，解除保护
            self._password_from_keyring = False
            self.show_password_checkbox.setEnabled(True)
            self.show_password_checkbox.setToolTip("")
            # 断开信号避免重复触发
            try:
                self.password_input.textChanged.disconnect(self._on_password_changed)
            except:
                pass

    def _save_credentials(self, username: str, password: str):
        """保存凭据到系统密钥环"""
        try:
            service = self._get_keyring_service()
            keyring.set_password(service, "username", username)
            keyring.set_password(service, f"password_{username}", password)
            logging.info(f"凭据已保存: {username}")
        except Exception as e:
            logging.warning(f"保存凭据失败: {e}")

    def _clear_saved_credentials(self):
        """清除已保存的凭据"""
        try:
            service = self._get_keyring_service()
            username = keyring.get_password(service, "username")
            if username:
                keyring.delete_password(service, "username")
                keyring.delete_password(service, f"password_{username}")
                logging.info("已清除保存的凭据")
        except Exception as e:
            logging.warning(f"清除凭据失败: {e}")
