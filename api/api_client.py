"""
HTTP API客户端
用于与认证API服务通信，替换直接数据库连接
"""

import requests
import json
import logging
from typing import Tuple, Optional, Dict, Any
from pathlib import Path
import os
import platform

logger = logging.getLogger(__name__)

class APIClient:
    """API客户端类"""

    def __init__(self, config_file: Optional[str] = None):
        """
        初始化API客户端

        Args:
            config_file: 配置文件路径，如果为None则使用默认配置
        """
        self.token = None
        self.user_info = None  # 缓存用户信息（登录时保存）
        self._load_config(config_file)

        # 尝试从token manager恢复令牌
        self._restore_token_from_manager()

        # 设置请求会话（Mac平台特殊处理）
        import platform
        if platform.system() == 'Darwin':
            # Mac平台使用特殊的session配置
            try:
                from auth.mac_security_fix import get_mac_safe_session, fix_mac_network_issues
                fix_mac_network_issues()  # 应用Mac网络修复
                self.session = get_mac_safe_session()
                logger.info("使用Mac安全会话配置")
            except Exception as e:
                logger.warning(f"无法加载Mac安全配置: {e}，使用默认配置")
                self.session = requests.Session()
        else:
            self.session = requests.Session()

        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'GeneticImprove-Client/2.0'
        })

        # 禁用代理，确保直接连接服务器
        if platform.system() != 'Darwin':  # 非Mac平台
            self.session.trust_env = False  # 不使用系统代理设置
            self.session.proxies = {
                'http': None,
                'https': None
            }

    def _load_config(self, config_file: Optional[str] = None):
        """加载配置文件"""
        if config_file is None:
            # 尝试多个位置查找配置文件
            import sys
            possible_paths = []

            # 1. 项目根目录（开发环境）
            project_root = Path(__file__).parent.parent
            possible_paths.append(project_root / "config" / "api_config.json")

            # 2. 打包应用的资源目录（Mac .app）
            if getattr(sys, 'frozen', False):
                # 打包应用
                if platform.system() == 'Darwin':
                    # Mac应用包
                    app_path = Path(sys.executable).parent.parent / "Resources"
                    possible_paths.append(app_path / "config" / "api_config.json")
                    # 也尝试MacOS目录
                    app_path2 = Path(sys.executable).parent
                    possible_paths.append(app_path2 / "config" / "api_config.json")
                else:
                    # Windows应用
                    app_path = Path(sys.executable).parent
                    possible_paths.append(app_path / "config" / "api_config.json")

            # 查找第一个存在的配置文件
            config_file = None
            for path in possible_paths:
                if path.exists():
                    config_file = path
                    logger.info(f"找到配置文件: {config_file}")
                    break

            if config_file is None:
                logger.warning(f"在以下位置都未找到配置文件: {possible_paths}")

        try:
            if config_file and Path(config_file).exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                current_env = config.get('current_environment', 'production')
                env_config = config.get('environments', {}).get(current_env, {})

                self.base_url = env_config.get('api_base_url', 'https://api.genepop.com').rstrip('/')
                self.timeout = env_config.get('timeout', 15)
                self.retry_attempts = env_config.get('retry_attempts', 3)

                # 加载安全配置
                security_config = config.get('security', {})
                self.verify_ssl = security_config.get('verify_ssl', False)

                logger.info(f"已加载API配置 - 环境: {current_env}, URL: {self.base_url}, SSL验证: {self.verify_ssl}")
            else:
                # 默认配置 - 使用可靠的HTTP连接
                self.base_url = "https://api.genepop.com"
                self.timeout = 15
                self.retry_attempts = 3
                self.verify_ssl = False
                logger.warning("未找到配置文件，使用默认配置（HTTP）")

        except Exception as e:
            logger.error(f"加载配置文件失败: {e}，使用默认配置")
            # 使用可靠的HTTP连接作为默认
            self.base_url = "http://39.96.189.27"
            self.timeout = 15
            self.retry_attempts = 3
            self.verify_ssl = False

    def _restore_token_from_manager(self):
        """从token manager恢复令牌"""
        try:
            from auth.token_manager import get_token_manager
            token_manager = get_token_manager()
            token = token_manager.get_token()
            if token:
                self.token = token
                logger.info("已从本地恢复API令牌")
        except Exception as e:
            logger.debug(f"无法恢复令牌: {e}")

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None,
                     headers: Optional[Dict] = None) -> Tuple[bool, Dict]:
        """
        发送HTTP请求的通用方法

        Args:
            method: HTTP方法 (GET, POST等)
            endpoint: API端点
            data: 请求数据
            headers: 额外的请求头

        Returns:
            (成功标志, 响应数据)
        """
        url = f"{self.base_url}{endpoint}"

        # 详细日志记录
        logger.info(f"Making {method} request to: {url}")
        logger.debug(f"SSL verification: {self.verify_ssl}")
        logger.debug(f"Timeout: {self.timeout}s")
        if data:
            # 不记录密码等敏感信息
            safe_data = {k: '***' if 'password' in k.lower() else v for k, v in data.items()}
            logger.debug(f"Request data: {safe_data}")

        try:
            # 合并请求头
            req_headers = self.session.headers.copy()
            if headers:
                req_headers.update(headers)
            logger.debug(f"Request headers: {req_headers}")

            # 发送请求（使用SSL验证配置）
            logger.info(f"Sending {method} request...")
            if method.upper() == 'GET':
                response = self.session.get(url, timeout=self.timeout, headers=req_headers, verify=self.verify_ssl)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, timeout=self.timeout, headers=req_headers, verify=self.verify_ssl)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")

            logger.info(f"Response status code: {response.status_code}")
            logger.debug(f"Response headers: {response.headers}")

            # 检查HTTP状态码
            response.raise_for_status()

            # 解析JSON响应
            result = response.json()
            logger.debug(f"Response data: {result}")

            return True, result

        except requests.exceptions.ConnectionError as e:
            logger.error(f"网络连接失败: {url}")
            logger.error(f"ConnectionError details: {str(e)}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return False, {"success": False, "message": "网络连接失败，请检查网络后重试"}

        except requests.exceptions.Timeout as e:
            logger.error(f"请求超时: {url}")
            logger.error(f"Timeout details: {str(e)}")
            return False, {"success": False, "message": "请求超时，请稍后重试"}

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP错误: {e}")
            return False, {"success": False, "message": f"服务器错误: {e.response.status_code}"}

        except requests.exceptions.RequestException as e:
            logger.error(f"请求异常: {e}")
            return False, {"success": False, "message": f"请求失败: {str(e)}"}

        except json.JSONDecodeError:
            logger.error("服务器响应格式错误")
            return False, {"success": False, "message": "服务器响应格式错误"}

        except Exception as e:
            logger.error(f"未知错误: {e}")
            return False, {"success": False, "message": f"未知错误: {str(e)}"}

    def health_check(self) -> Tuple[bool, str]:
        """
        检查API服务健康状态

        Returns:
            (成功标志, 状态信息)
        """
        success, response = self._make_request('GET', '/auth/health')

        if success and response.get('success'):
            return True, response.get('message', 'API服务正常')
        else:
            return False, response.get('message', 'API服务不可用')

    def login(self, username: str, password: str) -> Tuple[bool, Optional[str], str]:
        """
        用户登录

        Args:
            username: 用户名
            password: 密码

        Returns:
            (成功标志, JWT令牌, 消息)
        """
        data = {
            "username": username,
            "password": password
        }

        success, response = self._make_request('POST', '/api/auth/login', data)

        if success and response.get('success'):
            response_data = response.get('data', {})
            token = response_data.get('token')
            self.token = token  # 保存令牌

            # 保存用户信息（登录时API就返回了name）
            self.user_info = {
                'user_id': response_data.get('user_id'),
                'name': response_data.get('name')
            }
            logger.info(f"登录成功，用户信息: {self.user_info}")

            return True, token, response.get('message', '登录成功')
        else:
            return False, None, response.get('message', '登录失败')

    def register(self, employee_id: str, password: str, invite_code: str, name: str) -> Tuple[bool, str]:
        """
        用户注册

        Args:
            employee_id: 工号
            password: 密码
            invite_code: 邀请码
            name: 姓名

        Returns:
            (成功标志, 消息)
        """
        data = {
            "employee_id": employee_id,
            "password": password,
            "invite_code": invite_code,
            "name": name
        }

        success, response = self._make_request('POST', '/api/auth/register', data)

        if success and response.get('success'):
            return True, response.get('message', '注册成功')
        else:
            return False, response.get('message', '注册失败')

    def get_profile(self) -> Tuple[bool, Optional[Dict], str]:
        """
        获取当前用户信息

        Returns:
            (成功标志, 用户信息, 消息)
        """
        if not self.token:
            return False, None, "未登录，请先登录"

        # 优先返回缓存的用户信息（登录时已获取）
        if self.user_info:
            logger.debug(f"使用缓存的用户信息: {self.user_info}")
            return True, self.user_info, "获取用户信息成功"

        # 如果没有缓存，则从API获取
        headers = {
            'Authorization': f'Bearer {self.token}'
        }

        success, response = self._make_request('GET', '/api/auth/profile', headers=headers)

        if success and response.get('success'):
            self.user_info = response.get('data')  # 缓存用户信息
            return True, self.user_info, response.get('message', '获取用户信息成功')
        else:
            return False, None, response.get('message', '获取用户信息失败')

    def verify_token(self) -> Tuple[bool, str]:
        """
        验证当前令牌是否有效

        Returns:
            (成功标志, 消息)
        """
        if not self.token:
            return False, "未登录，请先登录"

        headers = {
            'Authorization': f'Bearer {self.token}'
        }

        success, response = self._make_request('POST', '/api/auth/verify', headers=headers)

        if success and response.get('success'):
            return True, response.get('message', '令牌有效')
        else:
            # 令牌无效，清除本地令牌和用户信息
            self.token = None
            self.user_info = None
            return False, response.get('message', '令牌无效')

    def set_token(self, token: str):
        """
        设置令牌（用于从本地存储恢复会话）

        Args:
            token: JWT令牌
        """
        self.token = token

    def clear_token(self):
        """清除令牌和用户信息"""
        self.token = None
        self.user_info = None

    def upload_missing_bulls(self, bulls_data: list) -> bool:
        """
        上传缺失公牛记录到云端数据库
        注意：此API无需认证

        Args:
            bulls_data: 缺失公牛数据列表

        Returns:
            bool: 是否上传成功
        """
        data = {
            'bulls': bulls_data
        }

        # 此API无需认证，直接请求即可
        success, response = self._make_request('POST', '/api/data/missing_bulls', data)

        if success and response.get('success'):
            uploaded_count = response.get('data', {}).get('uploaded_count', len(bulls_data))
            logger.info(f"成功通过API上传 {uploaded_count} 条缺失公牛记录")
            print(f"成功上传 {uploaded_count} 条缺失公牛记录到云端")
            return True
        else:
            error_msg = response.get('message', '未知错误')
            logger.error(f"API上传缺失公牛失败: {error_msg}")
            print(f"上传缺失公牛记录失败: {error_msg}")
            return False


# 全局API客户端实例
_global_api_client = None

def get_api_client() -> APIClient:
    """获取全局API客户端实例"""
    global _global_api_client
    if _global_api_client is None:
        _global_api_client = APIClient()

    # 确保令牌是最新的
    if not _global_api_client.token:
        _global_api_client._restore_token_from_manager()

    return _global_api_client


# 便捷函数
def api_login(username: str, password: str) -> Tuple[bool, Optional[str], str]:
    """登录的便捷函数"""
    return get_api_client().login(username, password)

def api_register(employee_id: str, password: str, invite_code: str, name: str) -> Tuple[bool, str]:
    """注册的便捷函数"""
    return get_api_client().register(employee_id, password, invite_code, name)

def api_get_profile() -> Tuple[bool, Optional[Dict], str]:
    """获取用户信息的便捷函数"""
    return get_api_client().get_profile()

def api_health_check() -> Tuple[bool, str]:
    """健康检查的便捷函数"""
    return get_api_client().health_check()


if __name__ == "__main__":
    # 测试代码
    client = APIClient()

    # 测试健康检查
    print("测试健康检查:")
    success, message = client.health_check()
    print(f"  结果: {success}, 消息: {message}")

    # 测试登录（需要有效的用户名密码）
    print("\n测试登录:")
    success, token, message = client.login("test_user", "test_password")
    print(f"  结果: {success}, 令牌: {token[:20] if token else None}..., 消息: {message}")