"""本地账号修改密码对话框。"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from auth.auth_service import AuthService


def validate_password_change(
    current_password: str,
    new_password: str,
    confirmed_password: str,
) -> str:
    """返回校验错误；空字符串表示校验通过。"""
    if not current_password or not new_password or not confirmed_password:
        return "请完整填写当前密码、新密码和确认密码"
    if len(new_password) < 6:
        return "新密码至少需要6位"
    if len(new_password) > 128:
        return "新密码不能超过128位"
    if new_password != confirmed_password:
        return "两次输入的新密码不一致"
    if new_password == current_password:
        return "新密码不能与当前密码相同"
    return ""


def clear_saved_local_password(username: str) -> None:
    """改密后移除本机保存的旧密码，不读取或记录密码内容。"""
    try:
        import keyring

        service = "GeneticImprove_YILI"
        saved_username = keyring.get_password(service, "username")
        if saved_username == username:
            try:
                keyring.delete_password(service, f"password_{username}")
            except keyring.errors.PasswordDeleteError:
                pass
            try:
                keyring.delete_password(service, "username")
            except keyring.errors.PasswordDeleteError:
                pass
    except Exception as exc:
        logging.warning("清除本机旧密码失败: %s", type(exc).__name__)


class ChangePasswordDialog(QDialog):
    """允许已登录本地账号校验原密码后设置新密码。"""

    def __init__(self, username: str, parent=None, auth_service=None):
        super().__init__(parent)
        self.username = str(username or "").strip()
        self.auth_service = auth_service or AuthService()

        self.setWindowTitle("修改密码")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        account_label = QLabel(f"当前账号：{self.username}")
        account_label.setStyleSheet("color:#606266; font-size:13px;")
        layout.addWidget(account_label)

        form = QFormLayout()
        form.setSpacing(12)
        self.current_password_input = self._password_input("请输入当前密码")
        self.new_password_input = self._password_input("至少6位")
        self.confirm_password_input = self._password_input("再次输入新密码")
        form.addRow("当前密码", self.current_password_input)
        form.addRow("新密码", self.new_password_input)
        form.addRow("确认新密码", self.confirm_password_input)
        layout.addLayout(form)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定修改")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    @staticmethod
    def _password_input(placeholder: str) -> QLineEdit:
        line_edit = QLineEdit()
        line_edit.setEchoMode(QLineEdit.EchoMode.Password)
        line_edit.setPlaceholderText(placeholder)
        line_edit.setMaxLength(128)
        line_edit.setMinimumHeight(34)
        return line_edit

    def submit(self) -> None:
        current_password = self.current_password_input.text()
        new_password = self.new_password_input.text()
        confirmed_password = self.confirm_password_input.text()
        error = validate_password_change(
            current_password,
            new_password,
            confirmed_password,
        )
        if error:
            QMessageBox.warning(self, "无法修改", error)
            return

        ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setEnabled(False)
        try:
            success, message = self.auth_service.change_password(
                current_password,
                new_password,
            )
        finally:
            ok_button.setEnabled(True)

        if not success:
            QMessageBox.warning(self, "修改失败", message or "密码修改失败")
            self.current_password_input.clear()
            self.current_password_input.setFocus()
            return

        clear_saved_local_password(self.username)
        QMessageBox.information(
            self,
            "修改成功",
            "密码已修改。若本机曾保存旧密码，下次登录请重新输入新密码。",
        )
        self.accept()
