"""
离线认证模式 - 用于本地测试和演示
当无法连接API服务器时使用
"""

import logging
from typing import Tuple, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class OfflineAuthService:
    """离线认证服务"""

    # 内置测试账号
    TEST_USERS = {
        "test_user": {
            "password": "test123",
            "name": "测试用户",
            "role": "user"
        },
        "admin": {
            "password": "admin123",
            "name": "管理员",
            "role": "admin"
        },
        "00108828": {
            "password": "123456",
            "name": "韩吉雨",
            "role": "user"
        }
    }

    def __init__(self):
        self.username = None
        self.is_offline = True
        logger.warning("⚠️ 使用离线认证模式 - 仅供测试使用")

    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """离线登录验证"""
        user = self.TEST_USERS.get(username)

        if user and user["password"] == password:
            self.username = username
            logger.info(f"离线登录成功: {username}")
            return True, f"离线模式 - 欢迎 {user['name']}"
        else:
            return False, "用户名或密码错误"

    def get_user_name(self) -> Optional[str]:
        """获取用户名称"""
        if self.username and self.username in self.TEST_USERS:
            return self.TEST_USERS[self.username]["name"]
        return None

    def logout(self) -> bool:
        """登出"""
        self.username = None
        return True

    def register(self, employee_id: str, password: str,
                invitation_code: str, name: str) -> Tuple[bool, str]:
        """离线注册（添加到测试用户）"""
        if employee_id in self.TEST_USERS:
            return False, "用户已存在"

        self.TEST_USERS[employee_id] = {
            "password": password,
            "name": name,
            "role": "user"
        }

        logger.info(f"离线注册成功: {employee_id} - {name}")
        return True, "注册成功（离线模式）"