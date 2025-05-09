# core/data/update_manager.py


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
CLOUD_DB_HOST = 'defectgene-new.mysql.polardb.rds.aliyuncs.com'
CLOUD_DB_PORT = 3306
CLOUD_DB_USER = 'defect_genetic_checking'
CLOUD_DB_PASSWORD_RAW = 'Jaybz@890411'  # 原始密码
CLOUD_DB_PASSWORD = urllib.parse.quote_plus(CLOUD_DB_PASSWORD_RAW)  # URL 编码后的密码
CLOUD_DB_NAME = 'bull_library'

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
LOCAL_DB_DIR = PROJECT_ROOT  # 直接使用项目根目录
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

# 设置 SQLAlchemy 引擎用于云端 MySQL
CLOUD_DB_URI = f"mysql+pymysql://{CLOUD_DB_USER}:{CLOUD_DB_PASSWORD}@{CLOUD_DB_HOST}:{CLOUD_DB_PORT}/{CLOUD_DB_NAME}?charset=utf8mb4"
cloud_engine = create_engine(CLOUD_DB_URI, echo=False)

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

def initialize_local_db_version(initial_version: str = "1.0.0"):
    """
    初始化本地数据库版本信息。如果 db_version 表为空，则插入初始版本号。
    
    Args:
        initial_version (str): 初始版本号，默认为 "1.0.0"。
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
    获取云端数据库的当前版本号。
    
    Returns:
        str: 云端数据库的版本号，如果获取失败则返回 None。
    """
    try:
        with cloud_engine.connect() as connection:
            result = connection.execute(text("SELECT version FROM db_version ORDER BY id DESC LIMIT 1")).fetchone()
            if result:
                version = result['version'] if isinstance(result, dict) else result[0]
                logging.info(f"云端数据库当前版本: {version}")
                return version
            else:
                logging.warning("云端数据库版本信息不存在。")
                return None
    except Exception as e:
        logging.error(f"获取云端数据库版本失败: {e}")
        return None

def fetch_cloud_bull_library():
    """
    从云端 MySQL 数据库中获取 bull_library 表的数据。
    
    Returns:
        pandas.DataFrame: bull_library 表的数据。
    """
    try:
        query = "SELECT * FROM bull_library"
        df = pd.read_sql(query, cloud_engine)  # 使用 cloud_engine
        logging.info(f"成功从云端数据库获取 bull_library 表，共 {len(df)} 条记录。")
        
        # 添加调试信息
        if not df.empty:
            logging.info(f"提取的前5行数据:\n{df.head()}")
            
            # 验证是否有表头行作为数据行
            if 'BULL NAAB' in df.columns:
                header_rows = df[df['BULL NAAB'] == 'BULL NAAB']
                if not header_rows.empty:
                    logging.warning(f"数据中包含 {len(header_rows)} 条表头行，将进行过滤。")
                    df = df[df['BULL NAAB'] != 'BULL NAAB']
                    logging.info(f"过滤表头后的记录数: {len(df)}")
                else:
                    logging.info("数据中不包含表头行。")
            else:
                logging.warning("'BULL NAAB' 列不存在，无法进行表头行过滤。")
        else:
            logging.warning("提取的数据为空。")
        
        return df
    except Exception as e:
        logging.error(f"从云端数据库获取 bull_library 表数据失败: {e}")
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
            initialize_local_db_version(initial_version=cloud_version or "1.0.0")
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
            print(f"本地数据库已更新到版本: {cloud_version}")
            logging.info(f"本地数据库已更新到版本: {cloud_version}")
            
            # 数据库更新后，更新系谱库
            if progress_callback:
                progress_callback(75, "开始更新系谱库...")
            
            # 强制更新系谱库
            get_pedigree_db(force_update=True, progress_callback=lambda p, m: progress_callback(75 + int(p * 0.25), m) if progress_callback else None)
            
            if progress_callback:
                progress_callback(100, "本地数据库和系谱库已更新到最新版本。")
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
    initialize_local_db_version(initial_version='1.0.0')
    
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
        initialize_local_db_version(initial_version='1.0.0')
        
        # 执行版本检查和更新
        check_and_update_database()
    except Exception as e:
        logging.error(f"更新过程失败: {e}")
        raise

if __name__ == "__main__":
    # 初始化本地数据库和版本信息
    initialize_local_db()
    initialize_local_db_version(initial_version='1.0.0')
    
    # 执行版本检查和更新
    check_and_update_database()
    
    # 获取并打印系谱库信息
    pedigree_db = get_pedigree_db()
    print(f"系谱库包含动物数量: {len(pedigree_db.pedigree)}")
    print(f"系谱库包含虚拟节点数量: {len(pedigree_db.virtual_nodes)}")