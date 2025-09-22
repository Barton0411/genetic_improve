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
import requests
import json

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

def download_from_oss(local_path: Path) -> Tuple[bool, str]:
    """
    从OSS下载数据库文件

    Args:
        local_path: 本地保存路径

    Returns:
        Tuple[bool, str]: (成功标志, 消息)
    """
    try:
        # OSS数据库URL
        oss_url = "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/bull_library/bull_library.db"

        logger.info(f"从OSS下载数据库: {oss_url}")

        # 下载文件
        response = requests.get(oss_url, stream=True, timeout=180)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        logger.info(f"文件大小: {total_size / 1024 / 1024:.1f} MB")

        # 确保目录存在
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        downloaded = 0
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded % (10 * 1024 * 1024) == 0:  # 每10MB记录一次
                        logger.info(f"已下载 {downloaded//1024//1024}MB / {total_size//1024//1024}MB")

        # 验证数据库
        conn = sqlite3.connect(local_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bull_library")
        count = cursor.fetchone()[0]
        conn.close()

        logger.info(f"成功从OSS下载数据库，包含{count}条记录")
        return True, f"数据库下载成功，包含{count}条记录"

    except Exception as e:
        logger.error(f"从OSS下载失败: {e}")
        return False, f"从OSS下载失败: {e}"

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

    logger.info("本地缓存不存在或无效，尝试获取数据库...")

    # 优先尝试从OSS下载（速度更快，更稳定）
    try:
        success, msg = download_from_oss(connector.local_cache_path)
        if success:
            return success, msg
    except Exception as e:
        logger.warning(f"OSS下载失败: {e}")

    # 备用方案：同步云数据库
    logger.info("尝试从云数据库同步...")
    return connector.sync_bull_library()