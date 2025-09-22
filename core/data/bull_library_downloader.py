"""
Bull Library数据库下载器
自动下载和初始化bull_library.db
"""

import logging
import sqlite3
import requests
from pathlib import Path
from typing import Optional, Callable, Tuple
import json
import pandas as pd

logger = logging.getLogger(__name__)

def download_bull_library(
    local_db_path: Path,
    progress_callback: Optional[Callable] = None
) -> Tuple[bool, str]:
    """
    下载bull_library数据库

    Args:
        local_db_path: 本地数据库路径
        progress_callback: 进度回调函数 (progress: int, message: str)

    Returns:
        Tuple[bool, str]: (成功标志, 消息)
    """
    try:
        # 检查数据库是否已存在
        if local_db_path.exists():
            # 检查是否有bull_library表
            conn = sqlite3.connect(local_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bull_library'")
            if cursor.fetchone():
                conn.close()
                logger.info("bull_library表已存在，跳过下载")
                return True, "数据库已存在"
            conn.close()

        logger.info(f"开始下载bull_library数据库到: {local_db_path}")

        if progress_callback:
            progress_callback(10, "正在连接服务器...")

        # 尝试从API下载
        try:
            from api.data_client import get_data_client
            client = get_data_client()

            if progress_callback:
                progress_callback(20, "正在下载公牛数据...")

            # 获取数据库版本信息
            success, version, message = client.get_database_version()
            if success:
                logger.info(f"服务器数据库版本: {version}")

            if progress_callback:
                progress_callback(30, "正在下载bull_library数据...")

            # 下载bull_library数据
            success, file_path = client.download_bull_library(str(local_db_path))

            if success:
                if progress_callback:
                    progress_callback(90, "数据下载完成")
                logger.info("bull_library数据库下载成功")
                return True, "数据库下载成功"
            else:
                logger.warning("API下载失败，尝试备用方案")

        except Exception as e:
            logger.warning(f"API下载失败: {e}，尝试备用方案")

        # 备用方案：从OSS直接下载
        if progress_callback:
            progress_callback(40, "使用备用源下载...")

        return download_from_oss(local_db_path, progress_callback)

    except Exception as e:
        error_msg = f"下载bull_library失败: {e}"
        logger.error(error_msg)
        return False, error_msg

def download_from_oss(
    local_db_path: Path,
    progress_callback: Optional[Callable] = None
) -> Tuple[bool, str]:
    """
    从备用源下载数据库

    Args:
        local_db_path: 本地数据库路径
        progress_callback: 进度回调函数

    Returns:
        Tuple[bool, str]: (成功标志, 消息)
    """
    # 使用域名作为备用源
    backup_urls = [
        "https://api.genepop.com/api/data/bull_library",
    ]

    for url in backup_urls:
        try:
            logger.info(f"尝试从备用源下载: {url}")

            if progress_callback:
                progress_callback(50, f"正在从备用源下载...")

            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))

            # 确保目录存在
            local_db_path.parent.mkdir(parents=True, exist_ok=True)

            # 下载并写入文件
            downloaded = 0
            with open(local_db_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress = 50 + int((downloaded / total_size) * 40)
                            progress_callback(progress, f"已下载 {downloaded//1024//1024}MB / {total_size//1024//1024}MB")

            # 验证数据库
            conn = sqlite3.connect(local_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM bull_library")
            count = cursor.fetchone()[0]
            conn.close()

            if progress_callback:
                progress_callback(100, "下载完成")

            logger.info(f"成功从备用源下载数据库，包含{count}条记录")
            return True, f"数据库下载成功，包含{count}条记录"

        except Exception as e:
            logger.error(f"从{url}下载失败: {e}")
            continue

    return False, "所有下载源都失败了"

def ensure_bull_library_exists(
    local_db_path: Path,
    progress_callback: Optional[Callable] = None
) -> bool:
    """
    确保bull_library数据库存在，如果不存在则自动下载

    Args:
        local_db_path: 本地数据库路径
        progress_callback: 进度回调函数

    Returns:
        bool: 数据库是否可用
    """
    try:
        # 检查文件是否存在
        if not local_db_path.exists():
            logger.info("bull_library.db不存在，开始自动下载")
            success, msg = download_bull_library(local_db_path, progress_callback)
            if not success:
                logger.error(f"自动下载失败: {msg}")
                return False

        # 验证数据库完整性
        conn = sqlite3.connect(local_db_path)
        cursor = conn.cursor()

        # 检查bull_library表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bull_library'")
        if not cursor.fetchone():
            conn.close()
            logger.warning("数据库文件存在但缺少bull_library表，重新下载")
            local_db_path.unlink()  # 删除损坏的文件
            success, msg = download_bull_library(local_db_path, progress_callback)
            if not success:
                logger.error(f"重新下载失败: {msg}")
                return False
        else:
            # 检查记录数
            cursor.execute("SELECT COUNT(*) FROM bull_library")
            count = cursor.fetchone()[0]
            conn.close()

            if count == 0:
                logger.warning("bull_library表为空，重新下载")
                local_db_path.unlink()
                success, msg = download_bull_library(local_db_path, progress_callback)
                if not success:
                    logger.error(f"重新下载失败: {msg}")
                    return False
            else:
                logger.info(f"bull_library数据库正常，包含{count}条记录")

        return True

    except Exception as e:
        logger.error(f"确保数据库存在时出错: {e}")
        return False