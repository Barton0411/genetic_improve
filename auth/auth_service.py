"""
认证服务 - 适配伊利奶牛选配系统
已升级为API化版本，不再使用硬编码数据库连接
"""

import logging
from pathlib import Path
from typing import Optional, Tuple, Dict
from api.api_client import get_api_client
from auth.token_manager import get_token_manager
from auth.offline_auth import OfflineAuthService

class AuthService:
    """认证服务 - API版本"""

    def __init__(self):
        """初始化认证服务"""
        self.username = None
        self.api_client = get_api_client()
        self.token_manager = get_token_manager()
        self.offline_service = None  # 离线服务备用

        # 尝试从本地恢复登录状态
        self._restore_session()

    def _restore_session(self):
        """从本地存储恢复登录会话"""
        try:
            token = self.token_manager.get_token()
            if token:
                self.api_client.set_token(token)
                # 验证令牌是否仍然有效
                success, message = self.api_client.verify_token()
                if success:
                    # 获取用户信息
                    success, user_info, _ = self.api_client.get_profile()
                    if success and user_info:
                        self.username = user_info.get('user_id')
                        logging.info(f"已恢复用户会话: {self.username}")
                else:
                    # 令牌无效，清除本地存储
                    self.token_manager.clear_token()
                    self.api_client.clear_token()
        except Exception as e:
            logging.warning(f"恢复会话失败: {e}")

    def register(self, employee_id: str, password: str, invite_code: str, name: str) -> Tuple[bool, str]:
        """注册新用户"""
        try:
            # 使用API进行注册
            success, message = self.api_client.register(employee_id, password, invite_code, name)
            return success, message

        except Exception as e:
            logging.error(f"注册失败: {e}")
            return False, f"注册失败: {str(e)}"

    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """用户登录"""
        try:
            # 使用API进行登录
            success, token, message = self.api_client.login(username, password)

            if success and token:
                # 登录成功，保存令牌和用户信息
                self.username = username
                self.token_manager.save_token(token, username)
                logging.info(f"用户 {username} 登录成功")
                return True, message
            else:
                return False, message

        except Exception as e:
            logging.error(f"API登录失败，尝试离线模式: {e}")

            # 如果API连接失败，切换到离线模式
            if "SSL" in str(e) or "Connection" in str(e) or "网络" in str(e):
                logging.warning("检测到网络问题，切换到离线认证模式")
                if not self.offline_service:
                    self.offline_service = OfflineAuthService()
                return self.offline_service.login(username, password)

            return False, f"登录失败: {str(e)}"

    def check_server_health(self) -> bool:
        """检查API服务连接"""
        try:
            success, message = self.api_client.health_check()
            return success
        except:
            return False

    def get_user_name(self) -> Optional[str]:
        """获取当前用户的姓名"""
        try:
            # 优先从API客户端缓存获取（登录时已保存）
            if self.api_client.user_info:
                name = self.api_client.user_info.get('name')
                if name:
                    return name

            # 回退：调用API获取
            if self.username or self.api_client.token:
                success, user_info, message = self.api_client.get_profile()
                if success and user_info:
                    return user_info.get('name')
            return None

        except Exception as e:
            logging.error(f"获取用户姓名失败: {e}")
            return None

    def logout(self) -> bool:
        """用户登出"""
        try:
            # 清除本地令牌和会话信息
            self.token_manager.clear_token()
            self.api_client.clear_token()
            self.username = None
            logging.info("用户已登出")
            return True
        except Exception as e:
            logging.error(f"登出失败: {e}")
            return False

    def is_logged_in(self) -> bool:
        """检查用户是否已登录"""
        return self.username is not None and self.token_manager.is_token_valid()