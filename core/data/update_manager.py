# core/data/update_manager.py

import os
import sys
import logging
import datetime
from pathlib import Path
import pandas as pd
# pymysql import removed - not needed after removing database connections
from typing import Callable, Optional
import json

# 导入系谱库管理模块
from core.inbreeding.pedigree_database import load_or_build_pedigree, update_pedigree, PedigreeDatabase

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 本地 SQLite 数据库连接参数
def get_project_root() -> Path:
    """
    获取项目的根目录路径。

    Returns:
        Path: 项目根目录路径。
    """
    try:
        if getattr(sys, 'frozen', False):
            # 如果是打包后的应用程序
            application_path = Path(sys.executable).parent
        else:
            # 如果是开发环境
            application_path = Path(__file__).parent.parent.parent  # 假设 update_manager.py 位于 core/data/
        logging.info(f"项目根目录: {application_path}")
        return application_path
    except Exception as e:
        logging.error(f"获取项目根目录失败: {e}")
        raise

# 获取本地数据库路径
LOCAL_DB_DIR = Path.home() / ".genetic_improve"
# 优先使用云数据库同步的本地缓存
LOCAL_DB_CACHE_PATH = LOCAL_DB_DIR / "bull_library_cache.db"
# 如果缓存存在就使用缓存，否则用原路径
LOCAL_DB_PATH = LOCAL_DB_CACHE_PATH if LOCAL_DB_CACHE_PATH.exists() else LOCAL_DB_DIR / "local_bull_library.db"

# 系谱缓存路径
PEDIGREE_CACHE_PATH = LOCAL_DB_DIR / "pedigree_cache.pkl"

# 确保本地数据库目录存在
LOCAL_DB_DIR.mkdir(parents=True, exist_ok=True)

logging.info(f"本地数据库路径: {LOCAL_DB_PATH}")

def get_cloud_engine():
    """
    获取云端数据库引擎（已废弃）

    此函数保留仅为向后兼容，实际不再提供数据库连接
    请使用API服务进行所有数据库操作

    Raises:
        NotImplementedError: 总是抛出异常，提示使用API服务
    """
    raise NotImplementedError(
        "直接数据库连接已废弃，请使用API服务。\n"
        "确保已登录并配置了认证令牌。\n"
        "如需帮助，请联系系统管理员。"
    )

# 全局系谱库管理器实例
pedigree_db_instance = None

def get_pedigree_db(force_update=False, progress_callback=None):
    """
    获取系谱库管理器实例，如果不存在则创建

    Args:
        force_update: 是否强制更新系谱库
        progress_callback: 进度回调函数

    Returns:
        PedigreeDatabase: 系谱库管理器实例
    """
    global pedigree_db_instance

    try:
        if force_update or pedigree_db_instance is None:
            if force_update:
                logging.info("强制更新系谱库")
                pedigree_db_instance = update_pedigree(
                    db_path=LOCAL_DB_PATH,
                    pedigree_cache_path=PEDIGREE_CACHE_PATH,
                    progress_callback=progress_callback
                )
            else:
                logging.info("加载或构建系谱库")
                pedigree_db_instance = load_or_build_pedigree(
                    db_path=LOCAL_DB_PATH,
                    pedigree_cache_path=PEDIGREE_CACHE_PATH,
                    progress_callback=progress_callback
                )

        return pedigree_db_instance
    except Exception as e:
        logging.error(f"获取系谱库失败: {e}")
        raise

def initialize_local_db():
    """
    初始化本地 SQLite 数据库，创建必要的表。
    使用 pymysql 代替 SQLAlchemy
    """
    try:
        if not LOCAL_DB_DIR.exists():
            LOCAL_DB_DIR.mkdir(parents=True)
            logging.info(f"已创建本地数据库目录: {LOCAL_DB_DIR}")

        # 不再创建初始版本文件，让下载过程创建正确的版本
        # 这样可以确保版本号与OSS一致
        version_file = LOCAL_DB_PATH.parent / "bull_library_version.json"
        if version_file.exists():
            logging.info(f"本地数据库版本文件已存在: {version_file}")
        else:
            logging.info("本地数据库版本文件不存在，将在下载时创建")

        logging.info("本地数据库已初始化。")

    except Exception as e:
        logging.error(f"初始化本地数据库失败: {e}")
        raise

def get_local_db_version():
    """
    获取本地数据库的当前版本号。
    从 JSON 文件读取，而不是数据库
    """
    try:
        version_file = LOCAL_DB_PATH.parent / "bull_library_version.json"
        if version_file.exists():
            with open(version_file, 'r') as f:
                version_info = json.load(f)
                version = version_info.get('version', 0)
                logging.info(f"本地数据库当前版本: {version}")
                return version
        else:
            logging.info("本地数据库版本信息不存在。")
            return None
    except Exception as e:
        logging.error(f"获取本地数据库版本失败: {e}")
        return None

def set_local_db_version(version: int):
    """
    设置本地数据库的版本号。
    保存到 JSON 文件
    """
    try:
        version_file = LOCAL_DB_PATH.parent / "bull_library_version.json"
        version_info = {
            "version": version,
            "update_time": datetime.datetime.now().isoformat()
        }
        with open(version_file, 'w') as f:
            json.dump(version_info, f)
        logging.info(f"本地数据库版本已更新为: {version}")
    except Exception as e:
        logging.error(f"设置本地数据库版本失败: {e}")
        raise

def get_local_db_version_with_time():
    """
    获取本地数据库的版本号和更新时间
    """
    try:
        version_file = LOCAL_DB_PATH.parent / "bull_library_version.json"
        if version_file.exists():
            with open(version_file, 'r') as f:
                version_info = json.load(f)
                version = version_info.get('version', None)

                # 处理版本号为0的情况，返回None
                if version == 0 or version == '0':
                    logging.warning("版本号为0，需要重新下载数据库")
                    return None, None

                update_time = version_info.get('update_time', 'Unknown')
                return version, update_time
        else:
            # 如果文件不存在，返回None
            logging.info("版本文件不存在")
            return None, None
    except Exception as e:
        logging.error(f"获取本地数据库版本和时间失败: {e}")
        return None, None

def run_update_process(force_update: bool = False, progress_callback: Optional[Callable] = None) -> bool:
    """
    执行数据库更新流程

    Args:
        force_update: 是否强制更新
        progress_callback: 进度回调函数

    Returns:
        bool: 更新是否成功
    """
    try:
        # 初始化本地数据库
        initialize_local_db()

        # 首先确保bull_library数据库存在
        from core.data.bull_library_downloader import ensure_bull_library_exists
        if progress_callback:
            progress_callback(10, "检查bull_library数据库...")

        if not ensure_bull_library_exists(LOCAL_DB_PATH, progress_callback):
            logging.error("无法获取bull_library数据库")
            # 不返回False，继续尝试更新系谱库
        else:
            logging.info("bull_library数据库已就绪")

        # 获取系谱库（会自动更新）
        pedigree_db = get_pedigree_db(force_update=force_update, progress_callback=progress_callback)

        if pedigree_db:
            logging.info("数据库更新成功")
            return True
        else:
            logging.error("数据库更新失败")
            return False

    except Exception as e:
        logging.error(f"数据库更新过程出错: {e}")
        return False

# 为了兼容性，保留这些变量但不使用
session = None
engine = None
metadata = None
db_version_table = None