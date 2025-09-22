#!/usr/bin/env python3
"""
准备预装数据库文件
在GitHub Actions构建时下载或创建数据库
"""

import os
import sys
from pathlib import Path
import requests
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_database(target_path: Path) -> bool:
    """下载数据库文件"""
    # 优先从OSS下载
    oss_url = "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/bull_library/bull_library.db"

    try:
        logger.info(f"正在从OSS下载数据库: {oss_url}")

        response = requests.get(oss_url, stream=True, timeout=180)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        # 写入文件并显示进度
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = downloaded / total_size * 100
                        logger.info(f"下载进度: {progress:.1f}% ({downloaded/1024/1024:.1f}/{total_size/1024/1024:.1f} MB)")

        logger.info(f"数据库下载成功: {target_path}")
        return True

    except Exception as e:
        logger.warning(f"从OSS下载失败: {e}")

        # OSS下载失败，不再尝试API
        logger.error(f"OSS下载失败，无备用方案")
        return False

def create_empty_database(target_path: Path) -> bool:
    """创建空数据库作为备用"""
    try:
        logger.info("创建空数据库...")
        conn = sqlite3.connect(target_path)
        cursor = conn.cursor()

        # 创建bull_library表结构
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bull_library (
                `BULL NAAB` TEXT PRIMARY KEY,
                `BULL REG` TEXT,
                `NM$` REAL,
                `TPI` REAL,
                `HH1` TEXT,
                `HH2` TEXT,
                `HH3` TEXT,
                `HH4` TEXT,
                `HH5` TEXT,
                `HH6` TEXT
            )
        """)

        # 插入一条示例数据
        cursor.execute("""
            INSERT OR IGNORE INTO bull_library
            (`BULL NAAB`, `BULL REG`, `NM$`, `TPI`)
            VALUES ('SAMPLE001', 'Sample Bull', 100.0, 200.0)
        """)

        conn.commit()
        conn.close()
        logger.info(f"空数据库创建成功: {target_path}")
        return True

    except Exception as e:
        logger.error(f"创建空数据库失败: {e}")
        return False

def main():
    """主函数"""
    # 创建目录
    data_dir = Path("data/databases")
    data_dir.mkdir(parents=True, exist_ok=True)

    db_path = data_dir / "bull_library.db"

    # 如果文件已存在且大小合理，跳过
    if db_path.exists() and db_path.stat().st_size > 1024 * 1024:  # > 1MB
        logger.info(f"数据库已存在: {db_path} ({db_path.stat().st_size / 1024 / 1024:.1f} MB)")
        return 0

    # 尝试下载
    if download_database(db_path):
        return 0

    # 下载失败，创建空数据库
    if create_empty_database(db_path):
        logger.warning("使用空数据库，用户首次运行时需要更新")
        return 0

    logger.error("无法准备数据库文件")
    return 1

if __name__ == "__main__":
    sys.exit(main())