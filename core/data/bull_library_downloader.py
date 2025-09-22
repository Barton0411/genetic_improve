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
import sys
import os

logger = logging.getLogger(__name__)

def check_bundled_database() -> Optional[Path]:
    """
    检查是否存在打包的预装数据库

    Returns:
        Path: 预装数据库路径，如果不存在则返回None
    """
    try:
        # 检查是否是打包的应用
        if getattr(sys, 'frozen', False):
            # 打包应用的基础路径
            if sys.platform == 'darwin':
                # macOS .app bundle
                base_path = Path(sys._MEIPASS)
            else:
                # Windows
                base_path = Path(sys.executable).parent

            # 尝试多个可能的位置
            possible_paths = [
                base_path / 'data' / 'databases' / 'bull_library.db',
                base_path / '_internal' / 'data' / 'databases' / 'bull_library.db',
                base_path / 'bull_library.db',
            ]
        else:
            # 开发环境
            base_path = Path(__file__).parent.parent.parent
            possible_paths = [
                base_path / 'data' / 'databases' / 'bull_library.db',
            ]

        # 检查每个可能的路径
        for db_path in possible_paths:
            if db_path.exists():
                logger.info(f"找到预装数据库: {db_path}")
                return db_path

        logger.debug("未找到预装数据库")
        return None

    except Exception as e:
        logger.warning(f"检查预装数据库时出错: {e}")
        return None

def get_local_db_version(local_db_path: Path) -> Optional[str]:
    """
    获取本地数据库版本

    Args:
        local_db_path: 数据库文件路径

    Returns:
        Optional[str]: 版本号，如果不存在则返回None
    """
    try:
        # 版本文件和数据库文件在同一目录
        version_file = local_db_path.parent / "bull_library_version.json"

        if version_file.exists():
            with open(version_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('version')
        return None
    except Exception as e:
        logger.warning(f"读取本地版本失败: {e}")
        return None

def save_local_db_version(local_db_path: Path, version: str):
    """
    保存本地数据库版本

    Args:
        local_db_path: 数据库文件路径
        version: 版本号
    """
    try:
        # 版本文件和数据库文件在同一目录
        version_file = local_db_path.parent / "bull_library_version.json"

        # 确保目录存在
        version_file.parent.mkdir(parents=True, exist_ok=True)

        with open(version_file, 'w', encoding='utf-8') as f:
            json.dump({'version': version}, f, ensure_ascii=False, indent=2)

        logger.info(f"保存本地版本: {version} 到 {version_file}")
    except Exception as e:
        logger.error(f"保存本地版本失败: {e}")

def check_oss_version() -> Optional[str]:
    """
    检查OSS上的数据库版本

    Returns:
        Optional[str]: OSS上的版本号，如果获取失败则返回None
    """
    try:
        version_url = "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/bull_library/bull_library_version.json"
        response = requests.get(version_url, timeout=10)
        response.raise_for_status()

        data = response.json()
        version = data.get('version')
        logger.info(f"OSS数据库版本: {version}")
        return version

    except Exception as e:
        logger.warning(f"获取OSS版本失败: {e}")
        return None

def download_bull_library(
    local_db_path: Path,
    progress_callback: Optional[Callable] = None,
    force_download: bool = False
) -> Tuple[bool, str]:
    """
    下载bull_library数据库

    Args:
        local_db_path: 本地数据库路径
        progress_callback: 进度回调函数 (progress: int, message: str)
        force_download: 是否强制下载（忽略版本检查）

    Returns:
        Tuple[bool, str]: (成功标志, 消息)
    """
    try:
        if progress_callback:
            progress_callback(5, "正在检查数据库版本...")

        # 检查是否需要下载
        if not force_download:
            # 检查本地版本（即使数据库文件不存在也要检查版本）
            local_version = get_local_db_version(local_db_path)

            # 如果数据库文件存在
            if local_db_path.exists():
                if local_version:
                    # 检查OSS版本
                    oss_version = check_oss_version()

                    if oss_version and oss_version == local_version:
                        # 验证数据库完整性
                        try:
                            conn = sqlite3.connect(local_db_path)
                            cursor = conn.cursor()
                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bull_library'")
                            if cursor.fetchone():
                                cursor.execute("SELECT COUNT(*) FROM bull_library")
                                count = cursor.fetchone()[0]
                                conn.close()

                                if count > 0:
                                    logger.info(f"数据库已是最新版本 {local_version}，包含{count}条记录")
                                    if progress_callback:
                                        progress_callback(100, f"数据库已是最新版本 ({count:,}条记录)")
                                    return True, f"数据库已是最新版本 {local_version}"
                            conn.close()
                        except Exception as e:
                            logger.warning(f"数据库验证失败: {e}")

                    if oss_version:
                        logger.info(f"发现新版本: {oss_version} (当前: {local_version})")
                else:
                    logger.info("数据库存在但没有版本信息，将重新下载")
            else:
                # 数据库文件不存在
                if local_version:
                    logger.warning(f"版本文件存在(v{local_version})但数据库文件丢失，将重新下载")
                else:
                    logger.info("首次下载数据库")

        logger.info(f"开始下载bull_library数据库到: {local_db_path}")

        if progress_callback:
            progress_callback(10, "正在连接数据库服务器...")

        # 从OSS下载
        if progress_callback:
            progress_callback(20, "正在准备下载数据库...")

        success, msg = download_from_oss(local_db_path, progress_callback)

        if success:
            # 保存版本信息
            oss_version = check_oss_version()
            if oss_version:
                save_local_db_version(local_db_path, oss_version)
            return True, msg
        else:
            logger.error(f"OSS下载失败: {msg}")
            return False, msg

    except Exception as e:
        error_msg = f"下载bull_library失败: {e}"
        logger.error(error_msg)
        return False, error_msg

def download_from_oss(
    local_db_path: Path,
    progress_callback: Optional[Callable] = None
) -> Tuple[bool, str]:
    """
    从OSS下载数据库

    Args:
        local_db_path: 本地数据库路径
        progress_callback: 进度回调函数

    Returns:
        Tuple[bool, str]: (成功标志, 消息)
    """
    # OSS地址
    oss_url = "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/bull_library/bull_library.db"

    import time
    max_retries = 3  # 最大重试次数
    retry_count = 0

    while retry_count < max_retries:
        try:
            if retry_count > 0:
                logger.info(f"第{retry_count}次重试下载...")
                if progress_callback:
                    progress_callback(25, f"第{retry_count}次重试连接...")
                time.sleep(2)  # 等待2秒再重试

            logger.info(f"从OSS下载: {oss_url}")

            if progress_callback:
                progress_callback(30, "正在连接OSS服务器...")

            # 使用较长的超时时间，因为文件较大（132MB）
            # 连接超时30秒，读取超时300秒
            response = requests.get(oss_url, stream=True, timeout=(30, 300))
            response.raise_for_status()

            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            logger.info(f"文件大小: {total_size / 1024 / 1024:.1f} MB")

            # 确保目录存在
            local_db_path.parent.mkdir(parents=True, exist_ok=True)

            # 下载并写入文件，使用更大的块大小
            downloaded = 0
            last_update_time = time.time()

            # 如果文件已经部分下载，删除并重新下载（避免损坏文件）
            if local_db_path.exists():
                local_db_path.unlink()

            with open(local_db_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # 每秒更新一次进度，避免频繁更新UI
                        current_time = time.time()
                        if progress_callback and total_size > 0 and (current_time - last_update_time) > 0.5:
                            # 计算下载进度（30%开始，90%结束，留畀10%给验证）
                            progress = 30 + int((downloaded / total_size) * 60)
                            # 显示详细进度信息
                            mb_downloaded = downloaded / 1024 / 1024
                            mb_total = total_size / 1024 / 1024
                            progress_callback(progress, f"正在下载数据库... {mb_downloaded:.1f}MB / {mb_total:.1f}MB")
                            last_update_time = current_time

            # 下载成功，跳出重试循环
            break

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            retry_count += 1
            error_msg = f"网络连接错误: {e}"
            logger.warning(f"{error_msg}，重试{retry_count}/{max_retries}")

            # 如果还有重试机会，继续循环
            if retry_count < max_retries:
                continue
            else:
                # 没有重试机会了
                return False, f"下载失败（网络连接问题）: {e}"

        except requests.exceptions.HTTPError as e:
            # HTTP错误一般不重试
            logger.error(f"HTTP错误: {e}")
            return False, f"下载失败（HTTP错误）: {e}"

        except Exception as e:
            # 其他错误
            logger.error(f"下载过程出错: {e}")
            return False, f"下载失败: {e}"

    # 如果所有重试都失败
    if retry_count >= max_retries:
        return False, f"OSS数据库下载失败，已重试{max_retries}次"

    try:
        # 验证数据库
        if progress_callback:
            progress_callback(92, "正在验证数据库完整性...")

        conn = sqlite3.connect(local_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bull_library'")
        if not cursor.fetchone():
            conn.close()
            logger.error("下载的数据库缺少bull_library表")
            # 删除损坏的数据库文件
            if local_db_path.exists():
                local_db_path.unlink()
            return False, "下载的数据库格式错误"

        cursor.execute("SELECT COUNT(*) FROM bull_library")
        count = cursor.fetchone()[0]
        conn.close()

        if count == 0:
            logger.error("数据库为空")
            # 删除空数据库
            if local_db_path.exists():
                local_db_path.unlink()
            return False, "下载的数据库为空"

        if progress_callback:
            progress_callback(100, f"数据库下载完成（{count:,}条记录）")

        logger.info(f"成功从OSS下载数据库，包含{count}条记录")
        return True, f"数据库下载成功，包含{count}条记录"

    except Exception as e:
        logger.error(f"验证数据库时出错: {e}")
        # 删除可能损坏的数据库文件
        if local_db_path.exists():
            local_db_path.unlink()
        return False, f"数据库验证失败: {e}"

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
            # 首先尝试从打包的应用中复制数据库
            bundled_db = check_bundled_database()
            if bundled_db and bundled_db.exists():
                logger.info(f"发现预装数据库: {bundled_db}")
                try:
                    import shutil
                    local_db_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(bundled_db, local_db_path)
                    logger.info(f"成功复制预装数据库到: {local_db_path}")
                    if progress_callback:
                        progress_callback(100, "使用预装数据库")
                except Exception as e:
                    logger.warning(f"复制预装数据库失败: {e}")

            # 如果复制失败或没有预装数据库，则下载
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