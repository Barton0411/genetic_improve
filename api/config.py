"""
API统一配置文件
确保所有API服务使用相同的配置
"""

import os

# JWT配置 - 所有API必须使用相同的密钥
JWT_SECRET = os.getenv('JWT_SECRET', 'genetic-improve-api-secret-key')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRE_HOURS = 24

# 数据库配置
DB_HOST = os.getenv('DB_HOST', 'defectgene-new.mysql.polardb.rds.aliyuncs.com')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER', 'defect_genetic_checking')
DB_PASSWORD = os.getenv('DB_PASSWORD')  # 必须从环境变量获取
DB_NAME = os.getenv('DB_NAME', 'bull_library')

# API端口配置
AUTH_API_PORT = 8000  # 认证API端口
DATA_API_PORT = 8082  # 数据API端口（公牛数据库下载等）

# 服务器配置
PRODUCTION_SERVER = 'http://39.96.189.27'  # 生产服务器地址

# 注意：
# 1. auth_api 运行在 8000 端口，通过 nginx 代理到 80 端口的 /api/auth/* 路径
# 2. data_api 运行在 8082 端口，用于下载公牛数据库等数据操作
# 3. 两个API必须使用相同的JWT_SECRET才能实现统一认证