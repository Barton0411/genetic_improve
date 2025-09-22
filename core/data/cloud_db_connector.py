"""
云数据库连接器
直接从阿里云 RDS 读取数据并缓存到本地
"""

import os
import sqlite3
import pymysql
import pandas as pd
from pathlib import Path
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class CloudDBConnector:
    """云数据库连接器"""

    def __init__(self):
        """初始化连接器"""
        from config.db_config import CLOUD_DB_CONFIG, LOCAL_CACHE_DB
        self.cloud_config = CLOUD_DB_CONFIG
        self.local_cache_path = Path(LOCAL_CACHE_DB)
        self.local_cache_path.parent.mkdir(parents=True, exist_ok=True)

    def sync_bull_library(self) -> Tuple[bool, str]:
        """
        从云数据库同步 bull_library 表到本地

        Returns:
            Tuple[bool, str]: (成功标志, 消息)
        """
        try:
            logger.info("开始从云数据库同步数据...")

            # 连接云数据库
            cloud_conn = pymysql.connect(
                host=self.cloud_config['host'],
                port=self.cloud_config['port'],
                user=self.cloud_config['user'],
                password=self.cloud_config['password'],
                database=self.cloud_config['database'],
                charset=self.cloud_config['charset']
            )

            try:
                # 读取 bull_library 表
                query = "SELECT * FROM bull_library"
                df = pd.read_sql(query, cloud_conn)
                logger.info(f"从云数据库读取了 {len(df)} 条记录")

                # 保存到本地 SQLite
                local_conn = sqlite3.connect(self.local_cache_path)
                df.to_sql('bull_library', local_conn, if_exists='replace', index=False)

                # 创建索引以提高查询性能
                cursor = local_conn.cursor()
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_bull_naab ON bull_library(`BULL NAAB`)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_bull_reg ON bull_library(`BULL REG`)")
                local_conn.commit()

                # 验证数据
                cursor.execute("SELECT COUNT(*) FROM bull_library")
                count = cursor.fetchone()[0]
                local_conn.close()

                logger.info(f"成功同步到本地，共 {count} 条记录")
                return True, f"成功同步 {count} 条记录"

            finally:
                cloud_conn.close()

        except pymysql.Error as e:
            error_msg = f"数据库连接错误: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"同步失败: {e}"
            logger.error(error_msg)
            return False, error_msg

    def get_local_db_path(self) -> Path:
        """获取本地缓存数据库路径"""
        return self.local_cache_path

    def check_local_cache(self) -> Tuple[bool, int]:
        """
        检查本地缓存是否存在且有效

        Returns:
            Tuple[bool, int]: (是否有效, 记录数)
        """
        if not self.local_cache_path.exists():
            return False, 0

        try:
            conn = sqlite3.connect(self.local_cache_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM bull_library")
            count = cursor.fetchone()[0]
            conn.close()
            return True, count
        except:
            return False, 0

# 全局实例
_connector = None

def get_cloud_connector() -> CloudDBConnector:
    """获取云数据库连接器实例"""
    global _connector
    if _connector is None:
        _connector = CloudDBConnector()
    return _connector

def ensure_database_ready() -> Tuple[bool, str]:
    """
    确保数据库准备就绪

    Returns:
        Tuple[bool, str]: (成功标志, 消息)
    """
    connector = get_cloud_connector()

    # 检查本地缓存
    valid, count = connector.check_local_cache()
    if valid and count > 0:
        logger.info(f"使用本地缓存，包含 {count} 条记录")
        return True, f"本地缓存可用 ({count} 条记录)"

    # 同步云数据库
    logger.info("本地缓存不存在或无效，开始同步云数据库...")
    return connector.sync_bull_library()