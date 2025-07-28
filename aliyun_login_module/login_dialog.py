# login_dialog.py
# 登录对话框组件

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
from pathlib import Path  
import logging
from auth_service import AuthService

class LoginDialog(QDialog):
    """用户登录对话框"""
    
    def __init__(self, parent=None, title="用户登录", use_encryption=True):
        """
        初始化登录对话框
        
        Args:
            parent: 父窗口
            title (str): 窗口标题
            use_encryption (bool): 是否使用加密的数据库配置
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(350, 200)
        self.username = None  # 存储登录成功的用户名
        
        # 初始化认证服务
        self.auth_service = AuthService(use_encryption=use_encryption)
        
        # 设置窗口标志，确保总是在最前面
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |  # 窗口保持在最前
            Qt.WindowType.CustomizeWindowHint |   # 自定义窗口外观
            Qt.WindowType.WindowTitleHint |      # 显示标题栏
            Qt.WindowType.WindowCloseButtonHint  # 显示关闭按钮
        )

        # 设置窗口图标
        icon_path = Path(__file__).parent / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._setup_ui()
        self._setup_styles()

    def _setup_ui(self):
        """设置用户界面"""
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

        # 等待提示组件
        self._setup_waiting_widget()
        
        self.setLayout(self.layout)

        # 设置回车键登录
        self.password_input.returnPressed.connect(self.login)

    def _setup_waiting_widget(self):
        """设置等待提示组件"""
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

    def _setup_styles(self):
        """设置样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLineEdit {
                padding: 5px;
                min-height: 25px;
                border: 1px solid #ccc;
                border-radius: 3px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
            QPushButton {
                padding: 8px 15px;
                min-height: 30px;
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 3px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QLabel {
                font-size: 14px;
                color: #333;
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
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "提示", "账号和密码不能为空")
            return

        # 禁用登录按钮防止重复点击
        self.login_button.setEnabled(False)
        self.show_waiting()
        
        # 使用定时器异步处理登录，避免界面卡顿
        QTimer.singleShot(100, lambda: self.process_login(username, password))

    def process_login(self, username, password):
        """处理登录验证"""
        try:
            # 调用认证服务进行验证
            if self.auth_service.authenticate_user(username, password):
                self.username = username
                self.accept()  # 登录成功，关闭对话框
            else:
                self._handle_login_failure("账号或密码错误，请重试")
                
        except Exception as e:
            logging.error(f"登录过程中发生错误: {str(e)}")
            self._handle_login_failure(f"连接数据库时发生错误，请联系管理员。\n{str(e)}")

    def _handle_login_failure(self, message):
        """处理登录失败"""
        self.show_login_form()
        self.login_button.setEnabled(True)
        QMessageBox.warning(self, "登录失败", message)
        self.username_input.clear()
        self.password_input.clear()
        self.username_input.setFocus()

    def get_username(self):
        """获取登录成功的用户名"""
        return self.username

    def reset_form(self):
        """重置表单"""
        self.username_input.clear()
        self.password_input.clear()
        self.username_input.setFocus()
        self.login_button.setEnabled(True)
        self.show_login_form()

# 静态方法，方便直接调用
def show_login_dialog(parent=None, title="用户登录", use_encryption=True):
    """
    显示登录对话框
    
    Args:
        parent: 父窗口
        title (str): 窗口标题
        use_encryption (bool): 是否使用加密配置
        
    Returns:
        tuple: (是否登录成功, 用户名)
    """
    dialog = LoginDialog(parent, title, use_encryption)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return True, dialog.get_username()
    return False, None 