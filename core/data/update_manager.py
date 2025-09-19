# core/data/update_manager.py


import os
import sys
import logging
import datetime
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, DateTime, MetaData, Table, inspect, text
from sqlalchemy.orm import sessionmaker
import pandas as pd
import urllib.parse
from typing import Callable, Optional

# 导入系谱库管理模块
from core.inbreeding.pedigree_database import load_or_build_pedigree, update_pedigree, PedigreeDatabase

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 云端 MySQL 数据库连接参数
# 完全API化模式 - 客户端不再需要数据库密码
# 所有数据库操作通过API服务进行
CLOUD_DB_HOST = 'defectgene-new.mysql.polardb.rds.aliyuncs.com'  # 仅供参考，不再使用
CLOUD_DB_PORT = 3306  # 仅供参考，不再使用
CLOUD_DB_USER = 'defect_genetic_checking'  # 仅供参考，不再使用
CLOUD_DB_PASSWORD = None  # 已移除，使用API服务
CLOUD_DB_NAME = 'bull_library'  # 仅供参考，不再使用

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

PROJECT_ROOT = get_project_root()

# 获取用户数据目录，避免权限问题
if os.name == 'nt':  # Windows
    USER_DATA_DIR = Path(os.environ.get('APPDATA', os.path.expanduser('~'))) / 'GeneticImprove'
else:  # Mac/Linux
    USER_DATA_DIR = Path.home() / '.genetic_improve'

# 确保用户数据目录存在
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

LOCAL_DB_DIR = USER_DATA_DIR  # 使用用户数据目录
LOCAL_DB_PATH = LOCAL_DB_DIR / 'local_bull_library.db'  # 本地数据库文件路径
LOCAL_DB_URI = f'sqlite:///{LOCAL_DB_PATH}'
PEDIGREE_CACHE_PATH = LOCAL_DB_DIR / 'pedigree_cache.pkl'  # 系谱库缓存路径

logging.info(f"本地数据库路径: {LOCAL_DB_PATH}")

# 设置 SQLAlchemy 引擎
engine = create_engine(LOCAL_DB_URI, echo=False)

# 创建会话
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

# 定义数据库版本管理表
metadata = MetaData()

db_version_table = Table(
    'db_version',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('version', String(50), nullable=False),
    Column('update_time', DateTime, default=datetime.datetime.utcnow)
)

# 云端数据库引擎已废弃 - 使用API服务
# 导入数据API客户端
try:
    from api.data_client import (
        get_cloud_db_version as api_get_cloud_db_version,
        fetch_cloud_bull_library as api_fetch_cloud_bull_library,
        get_data_client
    )
    USE_API = True
except ImportError:
    USE_API = False
    logging.warning("数据API客户端未安装，某些功能可能不可用")

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
    """
    try:
        if not LOCAL_DB_DIR.exists():
            LOCAL_DB_DIR.mkdir(parents=True)
            logging.info(f"已创建本地数据库目录: {LOCAL_DB_DIR}")
        metadata.create_all(engine)
        logging.info("本地数据库已初始化。")
        
        # 打印创建的表
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logging.info(f"已创建的表: {tables}")
        
        # 确认 db_version 表是否存在
        if 'db_version' in tables:
            logging.info("db_version 表已存在。")
        else:
            logging.error("db_version 表未被创建。")
    except Exception as e:
        logging.error(f"初始化本地数据库失败: {e}")
        raise

def get_local_db_version():
    """
    获取本地数据库的当前版本号。
    """
    try:
        result = session.execute(
            db_version_table.select().order_by(db_version_table.c.id.desc()).limit(1)
        ).fetchone()
        if result:
            # 根据查询结果的类型，决定如何访问数据
            if isinstance(result, dict):
                version = result['version']
            else:
                # 如果是元组，假设 'version' 是第二个元素
                version = result[1]
            logging.info(f"本地数据库当前版本: {version}")
            return version
        else:
            logging.info("本地数据库版本信息不存在。")
            return None
    except Exception as e:
        logging.error(f"获取本地数据库版本失败: {e}")
        return None

def set_local_db_version(version: str):
    """
    设置本地数据库的版本号。
    
    Args:
        version (str): 要设置的版本号。
    """
    try:
        insert_stmt = db_version_table.insert().values(version=version, update_time=datetime.datetime.utcnow())
        session.execute(insert_stmt)
        session.commit()
        logging.info(f"已更新本地数据库版本为: {version}")
    except Exception as e:
        logging.error(f"设置本地数据库版本失败: {e}")
        session.rollback()
        raise

def initialize_local_db_version(initial_version: str = "0.0.0"):
    """
    初始化本地数据库版本信息。如果 db_version 表为空，则插入初始版本号。
    
    Args:
        initial_version (str): 初始版本号，默认为 "0.0.0"。
    """
    try:
        version_count = session.query(db_version_table).count()
        if version_count == 0:
            set_local_db_version(initial_version)
            logging.info(f"本地数据库版本初始化为: {initial_version}")
        else:
            current_version = get_local_db_version()
            logging.info(f"本地数据库已存在版本: {current_version}")
    except Exception as e:
        logging.error(f"初始化本地数据库版本信息失败: {e}")
        raise

def get_cloud_db_version():
    """
    获取云端数据库的当前版本号（通过API）。

    Returns:
        str: 云端数据库的版本号，如果获取失败则返回 None。
    """
    if USE_API:
        try:
            # 使用API获取版本
            return api_get_cloud_db_version()
        except Exception as e:
            logging.error(f"通过API获取数据库版本失败: {e}")
            return None
    else:
        logging.error("数据API客户端未安装，无法获取云端数据库版本")
        return None

def fetch_cloud_bull_library():
    """
    从云端获取 bull_library 表的数据（通过API）。

    Returns:
        pandas.DataFrame: bull_library 表的数据。
    """
    if USE_API:
        try:
            # 使用API获取公牛库数据
            records = api_fetch_cloud_bull_library()
            if records:
                df = pd.DataFrame(records)
                logging.info(f"成功从API获取 bull_library 表，共 {len(df)} 条记录。")
                return df
            else:
                logging.warning("API返回的数据为空")
                return None
        except Exception as e:
            logging.error(f"通过API获取公牛库数据失败: {e}")
            return None
    else:
        logging.error("数据API客户端未安装，无法获取云端公牛库数据")
        return None

def update_local_bull_library(df: pd.DataFrame):
    """
    将 DataFrame 数据写入本地 SQLite 数据库的 bull_library 表，覆盖现有数据。
    
    Args:
        df (pandas.DataFrame): 要写入的数据。
    """
    try:
        # 确认 DataFrame 中不包含表头行
        if 'BULL NAAB' in df.columns:
            initial_count = len(df)
            df = df[df['BULL NAAB'] != 'BULL NAAB']
            filtered_count = len(df)
            if initial_count != filtered_count:
                logging.info(f"过滤表头后的记录数: {filtered_count}，过滤掉 {initial_count - filtered_count} 条表头记录。")
        
        # 将数据写入 SQLite，覆盖现有的 bull_library 表
        df.to_sql('bull_library', con=engine, if_exists='replace', index=False)
        logging.info(f"成功更新本地 SQLite 数据库的 bull_library 表，共 {len(df)} 条记录。")
    except Exception as e:
        logging.error(f"更新本地 SQLite 数据库的 bull_library 表失败: {e}")
        raise

def check_and_update_database(progress_callback=None):
    """
    检查本地和云端数据库的版本号，如果不一致，则从云端更新本地数据库。
    成功更新后，同时更新系谱库。
    """
    try:
        if progress_callback:
            progress_callback(0, "开始检查数据库版本...")
        # 获取本地和云端数据库版本号
        if progress_callback:
            progress_callback(45, "获取本地数据库版本号...")
        local_version = get_local_db_version()
        if progress_callback:
            progress_callback(50, "获取云端数据库版本号...")
        cloud_version = get_cloud_db_version()

        print(f"本地数据库版本: {local_version}")
        print(f"云端数据库版本: {cloud_version}")
        if progress_callback:
            progress_callback(10, f"本地版本: {local_version}, 云端版本: {cloud_version}")

        if local_version is None:
            logging.warning("本地数据库版本号不存在，将执行初始化。")
            if progress_callback:
                progress_callback(55, "初始化本地数据库版本号...")
            # 初始化本地数据库版本
            initialize_local_db_version(initial_version=cloud_version or "0.0.0")
            # 重新获取本地版本号
            local_version = get_local_db_version()

            if progress_callback:
                progress_callback(20, "本地数据库已初始化。")

        if local_version != cloud_version:
            if cloud_version is None:
                logging.error("无法获取云端数据库版本号，无法执行更新。")
                if progress_callback:
                    progress_callback(-1, "无法获取云端数据库版本号，更新操作终止。")
                return

            print("本地数据库版本与云端数据库版本不一致，开始更新本地数据库...")
            logging.info("开始从云端数据库下载 bull_library 表的数据并更新本地数据库。")

            if progress_callback:
                progress_callback(30, "开始从云端下载数据...")


            # 获取云端 bull_library 表的数据
            cloud_bull_library_df = fetch_cloud_bull_library()
            if cloud_bull_library_df is None:
                logging.error("无法获取云端 bull_library 表的数据，更新操作终止。")
                if progress_callback:
                    progress_callback(100, "无法获取云端 bull_library 表的数据，更新操作终止。")
                return

            if progress_callback:
                progress_callback(60, "已下载云端数据，开始更新本地数据库...")


            # 更新本地 SQLite 数据库的 bull_library 表
            update_local_bull_library(cloud_bull_library_df)

            if progress_callback:
                progress_callback(70, "更新本地数据库版本号...")

            # 更新本地数据库的版本号
            set_local_db_version(cloud_version)
            from datetime import datetime
            update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"数据库版本已更新为 {cloud_version} ({update_time})")
            logging.info(f"数据库版本已更新为 {cloud_version} ({update_time})")
            
            # 数据库更新后，更新系谱库
            if progress_callback:
                progress_callback(75, "开始更新系谱库...")
            
            # 强制更新系谱库
            get_pedigree_db(force_update=True, progress_callback=lambda p, m: progress_callback(75 + int(p * 0.25), m) if progress_callback else None)
            
            if progress_callback:
                from datetime import datetime
                update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                progress_callback(100, f"数据库版本已更新为 {cloud_version} ({update_time})")
        else:
            print("本地数据库版本与云端数据库版本一致，无需更新。")
            logging.info("本地数据库版本与云端数据库版本一致，无需更新。")
            
            # 检查系谱库是否存在，不存在则创建
            if not PEDIGREE_CACHE_PATH.exists():
                if progress_callback:
                    progress_callback(60, "系谱库缓存不存在，开始构建系谱库...")
                
                # 加载或构建系谱库
                get_pedigree_db(progress_callback=lambda p, m: progress_callback(60 + int(p * 0.4), m) if progress_callback else None)
                
                if progress_callback:
                    progress_callback(100, "系谱库已构建完成。")
            else:
                if progress_callback:
                    progress_callback(100, "本地数据库版本与云端数据库版本一致，无需更新。")
    except Exception as e:
        logging.error(f"检查和更新数据库时发生错误: {e}")
        if progress_callback:
            progress_callback(-1, f"检查和更新数据库时发生错误: {e}")
        raise


def run_update_process(progress_callback=None):
    """
    封装的函数，用于执行数据库检查和更新，同时提供进度回调。
    
    Args:
        progress_callback (callable, optional): 接受两个参数的回调函数，progress (int), message (str)
    """
    check_and_update_database(progress_callback=progress_callback)

def initialize_and_update_db(progress_callback=None):
    """
    初始化本地数据库，并检查和更新与云端数据库的版本。
    可以通过 progress_callback 传递进度更新。
    """
    if progress_callback:
        progress_callback("初始化本地数据库...")
    initialize_local_db()
    
    if progress_callback:
        progress_callback("初始化本地数据库版本信息...")
    initialize_local_db_version(initial_version='0.0.0')
    
    if progress_callback:
        progress_callback("检查并更新数据库版本...")
    check_and_update_database()
    
    if progress_callback:
        progress_callback("数据库初始化和更新完成。")


def run_update_process():
    """
    初始化本地数据库和版本信息，并执行版本检查和更新。
    """
    try:
        # 初始化本地数据库和版本信息
        initialize_local_db()
        initialize_local_db_version(initial_version='0.0.0')
        
        # 执行版本检查和更新
        check_and_update_database()
    except Exception as e:
        logging.error(f"更新过程失败: {e}")
        raise

if __name__ == "__main__":
    # 初始化本地数据库和版本信息
    initialize_local_db()
    initialize_local_db_version(initial_version='0.0.0')
    
    # 执行版本检查和更新
    check_and_update_database()
    
    # 获取并打印系谱库信息
    pedigree_db = get_pedigree_db()
    print(f"系谱库包含动物数量: {len(pedigree_db.pedigree)}")
    print(f"系谱库包含虚拟节点数量: {len(pedigree_db.virtual_nodes)}")