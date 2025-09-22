"""
数据库配置文件
直接连接阿里云 RDS
"""

# 阿里云 RDS MySQL 配置
CLOUD_DB_CONFIG = {
    'host': 'defectgene-new.mysql.polardb.rds.aliyuncs.com',
    'port': 3306,
    'user': 'defect_genetic_checking',
    'password': 'Jaybz@890411',
    'database': 'bull_library',
    'charset': 'utf8mb4'
}

# 本地缓存数据库路径
LOCAL_CACHE_DB = '/Users/bozhenwang/.genetic_improve/bull_library_cache.db'