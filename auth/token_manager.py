"""
令牌管理模块
负责JWT令牌的本地安全存储、获取和验证
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
import base64
from cryptography.fernet import Fernet
import keyring
from datetime import datetime
import jwt

logger = logging.getLogger(__name__)

class TokenManager:
    """令牌管理器"""

    def __init__(self):
        """初始化令牌管理器"""
        self.app_name = "GeneticImprove"
        self.token_key = "jwt_token"

        # 获取用户数据目录
        if os.name == 'nt':  # Windows
            self.data_dir = Path(os.environ.get('APPDATA', os.path.expanduser('~'))) / 'GeneticImprove'
        else:  # Mac/Linux
            self.data_dir = Path.home() / '.genetic_improve'

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.token_file = self.data_dir / 'token_cache.json'

    def _get_encryption_key(self) -> bytes:
        """
        获取加密密钥，优先使用系统密钥环，降级到本地文件

        Returns:
            加密密钥
        """
        # 检查是否是Mac打包应用，如果是则跳过keyring
        import sys
        import platform

        skip_keyring = False
        if platform.system() == 'Darwin' and getattr(sys, 'frozen', False):
            skip_keyring = True
            logger.info("Mac打包应用，跳过Keychain访问")

        if not skip_keyring:
            try:
                # 尝试从系统密钥环获取
                key_str = keyring.get_password(self.app_name, "encryption_key")
                if key_str:
                    return base64.b64decode(key_str.encode())
            except Exception as e:
                logger.warning(f"无法从系统密钥环获取密钥: {e}")

        # 降级到本地文件存储
        key_file = self.data_dir / '.token_key'

        if key_file.exists():
            try:
                with open(key_file, 'rb') as f:
                    return base64.b64decode(f.read())
            except Exception as e:
                logger.warning(f"读取本地密钥文件失败: {e}")

        # 生成新密钥
        key = Fernet.generate_key()

        # 尝试保存到系统密钥环（Mac打包应用跳过）
        if not skip_keyring:
            try:
                key_str = base64.b64encode(key).decode()
                keyring.set_password(self.app_name, "encryption_key", key_str)
                logger.info("密钥已保存到系统密钥环")
            except Exception as e:
                logger.warning(f"无法保存密钥到系统密钥环: {e}")

            # 降级到本地文件
            try:
                with open(key_file, 'wb') as f:
                    f.write(base64.b64encode(key))
                # 设置文件权限（仅所有者可读写）
                os.chmod(key_file, 0o600)
                logger.info("密钥已保存到本地文件")
            except Exception as e:
                logger.error(f"无法保存密钥到本地文件: {e}")

        return key

    def _encrypt_data(self, data: str) -> str:
        """
        加密数据

        Args:
            data: 要加密的字符串

        Returns:
            加密后的字符串
        """
        try:
            key = self._get_encryption_key()
            f = Fernet(key)
            encrypted_data = f.encrypt(data.encode())
            return base64.b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"数据加密失败: {e}")
            raise

    def _decrypt_data(self, encrypted_data: str) -> str:
        """
        解密数据

        Args:
            encrypted_data: 加密的字符串

        Returns:
            解密后的字符串
        """
        try:
            key = self._get_encryption_key()
            f = Fernet(key)
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted_data = f.decrypt(encrypted_bytes)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"数据解密失败: {e}")
            raise

    def save_token(self, token: str, username: str = None) -> bool:
        """
        安全保存令牌到本地

        Args:
            token: JWT令牌
            username: 用户名（可选）

        Returns:
            保存是否成功
        """
        try:
            # 解析令牌以获取过期时间
            try:
                payload = jwt.decode(token, options={"verify_signature": False})
                exp_timestamp = payload.get('exp', 0)
            except Exception:
                exp_timestamp = 0

            token_data = {
                'token': token,
                'username': username,
                'saved_at': datetime.utcnow().isoformat(),
                'expires_at': exp_timestamp
            }

            # 加密令牌数据
            encrypted_data = self._encrypt_data(json.dumps(token_data))

            # 保存到文件
            cache_data = {
                'encrypted_token': encrypted_data,
                'saved_at': datetime.utcnow().isoformat()
            }

            with open(self.token_file, 'w') as f:
                json.dump(cache_data, f)

            # 设置文件权限
            os.chmod(self.token_file, 0o600)

            logger.info("令牌已安全保存")
            return True

        except Exception as e:
            logger.error(f"保存令牌失败: {e}")
            return False

    def get_token(self) -> Optional[str]:
        """
        从本地获取令牌

        Returns:
            JWT令牌，如果不存在或无效则返回None
        """
        try:
            if not self.token_file.exists():
                return None

            with open(self.token_file, 'r') as f:
                cache_data = json.load(f)

            encrypted_token = cache_data.get('encrypted_token')
            if not encrypted_token:
                return None

            # 解密令牌数据
            token_data_str = self._decrypt_data(encrypted_token)
            token_data = json.loads(token_data_str)

            token = token_data.get('token')
            expires_at = token_data.get('expires_at', 0)

            # 检查令牌是否过期
            if expires_at > 0:
                current_timestamp = datetime.utcnow().timestamp()
                if current_timestamp >= expires_at:
                    logger.info("令牌已过期")
                    self.clear_token()
                    return None

            return token

        except Exception as e:
            logger.error(f"获取令牌失败: {e}")
            return None

    def get_token_info(self) -> Optional[dict]:
        """
        获取令牌信息（不包含实际令牌）

        Returns:
            令牌信息字典，如果不存在则返回None
        """
        try:
            if not self.token_file.exists():
                return None

            with open(self.token_file, 'r') as f:
                cache_data = json.load(f)

            encrypted_token = cache_data.get('encrypted_token')
            if not encrypted_token:
                return None

            # 解密令牌数据
            token_data_str = self._decrypt_data(encrypted_token)
            token_data = json.loads(token_data_str)

            # 返回不包含实际令牌的信息
            return {
                'username': token_data.get('username'),
                'saved_at': token_data.get('saved_at'),
                'expires_at': token_data.get('expires_at'),
                'is_valid': self.is_token_valid()
            }

        except Exception as e:
            logger.error(f"获取令牌信息失败: {e}")
            return None

    def is_token_valid(self) -> bool:
        """
        检查令牌是否有效（存在且未过期）

        Returns:
            令牌是否有效
        """
        token = self.get_token()
        return token is not None

    def clear_token(self) -> bool:
        """
        清除本地保存的令牌

        Returns:
            清除是否成功
        """
        try:
            if self.token_file.exists():
                self.token_file.unlink()
                logger.info("令牌已清除")
            return True

        except Exception as e:
            logger.error(f"清除令牌失败: {e}")
            return False

    def refresh_token_if_needed(self, api_client) -> bool:
        """
        如果需要，刷新令牌（预留接口）

        Args:
            api_client: API客户端实例

        Returns:
            刷新是否成功
        """
        # 当前版本不支持令牌刷新，需要重新登录
        if not self.is_token_valid():
            self.clear_token()
            return False
        return True


# 全局令牌管理器实例
_global_token_manager = None

def get_token_manager() -> TokenManager:
    """获取全局令牌管理器实例"""
    global _global_token_manager
    if _global_token_manager is None:
        _global_token_manager = TokenManager()
    return _global_token_manager


# 便捷函数
def save_token(token: str, username: str = None) -> bool:
    """保存令牌的便捷函数"""
    return get_token_manager().save_token(token, username)

def get_token() -> Optional[str]:
    """获取令牌的便捷函数"""
    return get_token_manager().get_token()

def is_token_valid() -> bool:
    """检查令牌有效性的便捷函数"""
    return get_token_manager().is_token_valid()

def clear_token() -> bool:
    """清除令牌的便捷函数"""
    return get_token_manager().clear_token()


if __name__ == "__main__":
    # 测试代码
    manager = TokenManager()

    # 测试保存和获取令牌
    test_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.token"
    print("测试令牌管理:")

    print(f"保存令牌: {manager.save_token(test_token, 'test_user')}")
    print(f"获取令牌: {manager.get_token()}")
    print(f"令牌有效: {manager.is_token_valid()}")
    print(f"令牌信息: {manager.get_token_info()}")
    print(f"清除令牌: {manager.clear_token()}")
    print(f"再次获取令牌: {manager.get_token()}")