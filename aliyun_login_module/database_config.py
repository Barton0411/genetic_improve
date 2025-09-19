# database_config.py
# API服务配置模块
# 注意：此模块已从硬编码数据库连接迁移到API服务模式

import os
import logging
from api.api_client import get_api_client

# 弃用警告
logging.warning("database_config.py 已弃用硬编码数据库连接，请使用API服务")

# API服务配置
def get_api_config():
    """
    获取API服务配置

    Returns:
        dict: API配置信息
    """
    return {
        'api_base_url': os.getenv('API_BASE_URL', 'https://api.genepop.com'),
        'timeout': int(os.getenv('API_TIMEOUT', '15')),
        'verify_ssl': os.getenv('API_VERIFY_SSL', 'true').lower() == 'true'
    }

def get_encrypted_db_config():
    """
    已弃用：获取解密后的数据库配置
    请使用API服务进行数据访问

    Returns:
        dict: 抛出弃用警告
    """
    raise DeprecationWarning("硬编码数据库连接已弃用，请使用API服务")

def get_sqlalchemy_url():
    """
    已弃用：获取SQLAlchemy格式的数据库连接URL
    请使用API服务进行数据访问

    Returns:
        str: 抛出弃用警告
    """
    raise DeprecationWarning("硬编码数据库连接已弃用，请使用API服务")

def get_encrypted_sqlalchemy_url():
    """
    已弃用：使用加密配置获取SQLAlchemy格式的数据库连接URL
    请使用API服务进行数据访问

    Returns:
        str: 抛出弃用警告
    """
    raise DeprecationWarning("硬编码数据库连接已弃用，请使用API服务")

# 新的API服务接口
def get_api_client_instance():
    """
    获取API客户端实例

    Returns:
        APIClient: 配置好的API客户端
    """
    return get_api_client() 