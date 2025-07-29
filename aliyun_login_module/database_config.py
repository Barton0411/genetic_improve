# database_config.py
# 阿里云数据库连接配置模块

import urllib.parse
from cryptography.fernet import Fernet
import logging

# 阿里云 MySQL 数据库连接参数
# CLOUD_DB_HOST = 'defectgene-new.mysql.polardb.rds.aliyuncs.com'
CLOUD_DB_HOST = '8.147.221.122'  # 使用IP地址避免DNS解析问题
CLOUD_DB_PORT = 3306
CLOUD_DB_USER = 'defect_genetic_checking'
CLOUD_DB_PASSWORD_RAW = 'Jaybz@890411'  # 原始密码
CLOUD_DB_NAME = 'bull_library'

# URL编码密码（用于SQLAlchemy连接）
CLOUD_DB_PASSWORD = urllib.parse.quote_plus(CLOUD_DB_PASSWORD_RAW)

# 加密配置
ENCRYPTION_KEY = b'XGf7ZRXtj53qNCm9Ziuey22yXXEkzSq9FBTWZpfJiow='
cipher_suite = Fernet(ENCRYPTION_KEY)

# 加密的数据库连接信息
ENCODED_HOST = cipher_suite.encrypt(b'defectgene-new.mysql.polardb.rds.aliyuncs.com')
ENCODED_PORT = cipher_suite.encrypt(b'3306')
ENCODED_USER = cipher_suite.encrypt(b'defect_genetic_checking')
ENCODED_PASSWORD = cipher_suite.encrypt(b'Jaybz@890411')
ENCODED_DB = cipher_suite.encrypt(b'bull_library')

def get_encrypted_db_config():
    """
    获取解密后的数据库配置
    
    Returns:
        dict: 包含数据库连接信息的字典
    """
    try:
        return {
            'host': cipher_suite.decrypt(ENCODED_HOST).decode(),
            'port': int(cipher_suite.decrypt(ENCODED_PORT).decode()),
            'user': cipher_suite.decrypt(ENCODED_USER).decode(),
            'password': cipher_suite.decrypt(ENCODED_PASSWORD).decode(),
            'database': cipher_suite.decrypt(ENCODED_DB).decode(),
            'charset': 'utf8mb4'
        }
    except Exception as e:
        logging.error(f"解密数据库配置失败: {e}")
        raise

def get_sqlalchemy_url():
    """
    获取SQLAlchemy格式的数据库连接URL
    
    Returns:
        str: SQLAlchemy数据库连接字符串
    """
    return f"mysql+pymysql://{CLOUD_DB_USER}:{CLOUD_DB_PASSWORD}@{CLOUD_DB_HOST}:{CLOUD_DB_PORT}/{CLOUD_DB_NAME}?charset=utf8mb4"

def get_encrypted_sqlalchemy_url():
    """
    使用加密配置获取SQLAlchemy格式的数据库连接URL
    
    Returns:
        str: SQLAlchemy数据库连接字符串
    """
    config = get_encrypted_db_config()
    password_encoded = urllib.parse.quote_plus(config['password'])
    return f"mysql+pymysql://{config['user']}:{password_encoded}@{config['host']}:{config['port']}/{config['database']}?charset=utf8mb4" 