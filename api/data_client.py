"""
数据API客户端 - 替代直接数据库连接
完全API化，不需要数据库密码
"""

import os
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

class DataAPIClient:
    """数据API客户端"""

    def __init__(self, api_base_url: str = None):
        """初始化数据API客户端"""
        # 加载配置
        config_path = Path(__file__).parent.parent / 'config' / 'api_config.json'
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                env = config.get('current_environment', 'production')
                self.base_url = api_base_url or config['environments'][env]['api_base_url']
                self.timeout = config['environments'][env].get('timeout', 30)
        else:
            self.base_url = api_base_url or 'https://api.genepop.com'
            self.timeout = 30

        self.session = requests.Session()
        self._token = None

        # 禁用代理，确保直接连接服务器
        self.session.trust_env = False  # 不使用系统代理设置
        self.session.proxies = {
            'http': None,
            'https': None
        }

        # 使用HTTP时不需要SSL验证
        # 备案完成后会切换回HTTPS+域名

    def set_token(self, token: str):
        """设置认证令牌"""
        self._token = token
        self.session.headers.update({'Authorization': f'Bearer {token}'})

    def get_database_version(self) -> Tuple[bool, Optional[str], str]:
        """
        获取数据库版本

        Returns:
            Tuple[bool, Optional[str], str]: (成功标志, 版本号, 消息)
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/data/version",
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            if data.get('success'):
                version = data['data'].get('version')
                return True, version, f"数据库版本: {version}"
            else:
                return False, None, data.get('message', '获取版本失败')

        except requests.exceptions.RequestException as e:
            logger.error(f"获取数据库版本失败: {e}")
            return False, None, str(e)

    def get_bull_library(self) -> Tuple[bool, Optional[List[Dict]], str]:
        """
        获取公牛库数据

        Returns:
            Tuple[bool, Optional[List[Dict]], str]: (成功标志, 公牛记录列表, 消息)
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/data/bull_library",
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            if data.get('success'):
                records = data['data'].get('records', [])
                total = data['data'].get('total', 0)
                return True, records, f"成功获取{total}条公牛记录"
            else:
                return False, None, data.get('message', '获取公牛库失败')

        except requests.exceptions.RequestException as e:
            logger.error(f"获取公牛库数据失败: {e}")
            return False, None, str(e)

    def upload_missing_bulls(self, missing_bulls: List[Dict]) -> Tuple[bool, str]:
        """
        上传缺失公牛记录

        Args:
            missing_bulls: 缺失公牛记录列表

        Returns:
            Tuple[bool, str]: (成功标志, 消息)
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/data/missing_bulls",
                json={'bulls': missing_bulls},
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            if data.get('success'):
                count = data['data'].get('uploaded_count', 0)
                return True, f"成功上传{count}条缺失公牛记录"
            else:
                return False, data.get('message', '上传失败')

        except requests.exceptions.RequestException as e:
            logger.error(f"上传缺失公牛记录失败: {e}")
            return False, str(e)

    def sync_bull_library(self) -> Tuple[bool, Optional[Dict], str]:
        """
        同步公牛库数据（替代check_and_update_database）

        Returns:
            Tuple[bool, Optional[Dict], str]: (成功标志, 数据字典, 消息)
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/data/sync_bull_library",
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            if data.get('success'):
                sync_data = data.get('data', {})
                total = sync_data.get('total_records', 0)
                version = sync_data.get('version', 'unknown')
                return True, sync_data, f"成功同步{total}条记录，版本{version}"
            else:
                return False, None, data.get('message', '同步失败')

        except requests.exceptions.RequestException as e:
            logger.error(f"同步公牛库数据失败: {e}")
            return False, None, str(e)

    def check_connection(self) -> bool:
        """
        检查API连接是否正常

        Returns:
            bool: 连接是否正常
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/health",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False

# 全局客户端实例
_data_client = None

def get_data_client() -> DataAPIClient:
    """获取数据API客户端实例"""
    global _data_client
    if _data_client is None:
        _data_client = DataAPIClient()

        # 尝试从认证服务获取令牌
        try:
            from auth.token_manager import get_token_manager
            token_manager = get_token_manager()
            token = token_manager.get_token()
            if token:
                _data_client.set_token(token)
                logger.info("数据API客户端已设置认证令牌")
        except Exception as e:
            logger.warning(f"无法为数据API客户端设置令牌: {e}")

    return _data_client

# ==================== 兼容性函数 ====================
# 这些函数提供与原有直接数据库连接相同的接口

def get_cloud_db_version() -> Optional[str]:
    """
    获取云端数据库版本（兼容接口）

    Returns:
        Optional[str]: 版本号，失败返回None
    """
    client = get_data_client()
    success, version, message = client.get_database_version()
    if success:
        return version
    else:
        logger.error(f"获取版本失败: {message}")
        return None

def fetch_cloud_bull_library() -> Optional[List[Dict]]:
    """
    获取云端公牛库数据（兼容接口）

    Returns:
        Optional[List[Dict]]: 公牛记录列表，失败返回None
    """
    client = get_data_client()
    success, records, message = client.get_bull_library()
    if success:
        return records
    else:
        logger.error(f"获取公牛库失败: {message}")
        return None

def upload_missing_bulls_to_cloud(missing_bulls: List[Dict]) -> bool:
    """
    上传缺失公牛到云端（兼容接口）

    Args:
        missing_bulls: 缺失公牛记录列表

    Returns:
        bool: 是否成功
    """
    client = get_data_client()
    success, message = client.upload_missing_bulls(missing_bulls)
    if success:
        logger.info(message)
    else:
        logger.error(f"上传失败: {message}")
    return success