"""
注册对话框 - 支持邀请码验证
移植自protein_screening项目
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
from pathlib import Path
from auth.auth_service import AuthService

class RegisterDialog(QDialog):
    """用户注册对话框"""

    def __init__(self, parent=None, auth_service=None):
        """
        初始化注册对话框

        Args:
            parent: 父窗口
            auth_service: 认证服务实例
        """
        super().__init__(parent)
        self.auth_service = auth_service or AuthService()
        self.username = None

        self.setWindowTitle("用户注册 - 伊利奶牛选配")
        self.setFixedSize(400, 530)

        # 设置窗口标志
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        # 设置窗口图标
        icon_path = Path(__file__).parent.parent / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._setup_ui()
        self._setup_styles()

    def _setup_ui(self):
        """设置用户界面"""
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(35, 30, 35, 25)

        # 标题
        title = QLabel("创建新账号")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # 添加一些间距
        layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        # 邀请码输入
        self.invite_code_label = QLabel("邀请码:")
        self.invite_code_input = QLineEdit()
        self.invite_code_input.setPlaceholderText("必填")
        layout.addWidget(self.invite_code_label)
        layout.addWidget(self.invite_code_input)

        # 工号输入（作为登录账号）
        self.employee_id_label = QLabel("工号(登录账号):")
        self.employee_id_input = QLineEdit()
        self.employee_id_input.setPlaceholderText("登录时使用")
        layout.addWidget(self.employee_id_label)
        layout.addWidget(self.employee_id_input)

        # 姓名输入
        self.name_label = QLabel("姓名:")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("真实姓名")
        layout.addWidget(self.name_label)
        layout.addWidget(self.name_input)

        # 密码输入
        self.password_label = QLabel("密码:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("至少6个字符")
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_input)

        # 确认密码
        self.confirm_password_label = QLabel("确认密码:")
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input.setPlaceholderText("确认密码")
        layout.addWidget(self.confirm_password_label)
        layout.addWidget(self.confirm_password_input)

        # 添加弹性间距
        layout.addStretch()

        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)  # 设置按钮间距

        self.register_button = QPushButton("注册")
        self.register_button.clicked.connect(self.register)
        self.register_button.setDefault(True)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.setObjectName("cancelBtn")
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.register_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        # 等待提示
        self.waiting_label = QLabel("正在处理...")
        self.waiting_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.waiting_label.hide()
        layout.addWidget(self.waiting_label)

        self.setLayout(layout)

    def _setup_styles(self):
        """设置样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border-radius: 8px;
            }
            QLabel {
                color: #333;
                font-size: 14px;
                margin-bottom: 2px;
                margin-top: 3px;
            }
            QLineEdit {
                padding: 10px 12px;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                font-size: 14px;
                background-color: #f8f9fa;
                color: #333;
                min-height: 20px;
            }
            QLineEdit:focus {
                border: 1px solid #007AFF;
                background-color: white;
                outline: none;
            }
            QLineEdit::placeholder {
                color: #999;
            }
            QPushButton {
                padding: 8px 20px;
                background-color: #007AFF;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 15px;
                font-weight: 500;
                min-width: 100px;
                min-height: 32px;
            }
            QPushButton:hover {
                background-color: #0051D5;
            }
            QPushButton:pressed {
                background-color: #0041AB;
            }
            QPushButton#cancelBtn {
                background-color: #f0f0f0;
                color: #333;
            }
            QPushButton#cancelBtn:hover {
                background-color: #e0e0e0;
            }
            QPushButton#cancelBtn:pressed {
                background-color: #d0d0d0;
            }
            QPushButton:disabled {
                background-color: #c0c0c0;
                color: #888;
            }
        """)

    def show_waiting(self, message: str = "正在处理..."):
        """显示等待提示"""
        self.waiting_label.setText(message)
        self.waiting_label.show()
        self.register_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

        # 禁用所有输入框
        for widget in [self.invite_code_input, self.employee_id_input,
                      self.name_input, self.password_input,
                      self.confirm_password_input]:
            widget.setEnabled(False)

    def hide_waiting(self):
        """隐藏等待提示"""
        self.waiting_label.hide()
        self.register_button.setEnabled(True)
        self.cancel_button.setEnabled(True)

        # 启用所有输入框
        for widget in [self.invite_code_input, self.employee_id_input,
                      self.name_input, self.password_input,
                      self.confirm_password_input]:
            widget.setEnabled(True)

    def validate_inputs(self) -> tuple[bool, str]:
        """
        验证输入

        Returns:
            (是否有效, 错误信息)
        """
        invite_code = self.invite_code_input.text().strip()
        employee_id = self.employee_id_input.text().strip()
        name = self.name_input.text().strip()
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()

        # 验证邀请码
        if not invite_code:
            return False, "请输入邀请码"

        # 验证工号
        if not employee_id:
            return False, "请输入工号"

        # 验证姓名
        if not name:
            return False, "请输入姓名"

        # 验证密码
        if not password:
            return False, "请输入密码"
        if len(password) < 6:
            return False, "密码长度至少6个字符"
        if password != confirm_password:
            return False, "两次输入的密码不一致"

        return True, ""

    def register(self):
        """处理注册"""
        # 验证输入
        valid, error_msg = self.validate_inputs()
        if not valid:
            QMessageBox.warning(self, "输入错误", error_msg)
            return

        # 获取输入值
        invite_code = self.invite_code_input.text().strip()
        employee_id = self.employee_id_input.text().strip()
        name = self.name_input.text().strip()
        password = self.password_input.text()

        self.show_waiting("正在注册...")

        # 使用定时器异步处理注册
        QTimer.singleShot(100, lambda: self._process_register(
            employee_id, password, invite_code, name
        ))

    def _process_register(self, employee_id: str, password: str, invite_code: str, name: str):
        """处理注册逻辑"""
        # 调用认证服务注册
        success, message = self.auth_service.register(employee_id, password, invite_code, name)

        self.hide_waiting()

        if success:
            self.username = employee_id
            QMessageBox.information(self, "注册成功", message)
            self.accept()
        else:
            QMessageBox.warning(self, "注册失败", message)

            # 根据错误信息定位焦点
            if "邀请码" in message:
                self.invite_code_input.setFocus()
                self.invite_code_input.selectAll()
            elif "工号" in message:
                self.employee_id_input.setFocus()
                self.employee_id_input.selectAll()
            elif "姓名" in message:
                self.name_input.setFocus()
                self.name_input.selectAll()

    def get_username(self) -> str:
        """获取注册成功的用户名"""
        return self.username


# 便捷函数
def show_register_dialog(parent=None, auth_service=None) -> tuple[bool, str]:
    """
    显示注册对话框

    Args:
        parent: 父窗口
        auth_service: 认证服务实例

    Returns:
        (是否注册成功, 用户名)
    """
    dialog = RegisterDialog(parent, auth_service)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return True, dialog.get_username()
    return False, None