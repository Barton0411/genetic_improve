"""
数据缓存工具
用于缓存已读取的Excel文件，避免重复读取
"""

from pathlib import Path
import threading
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class DataCache:
    """数据缓存类 - 缓存已读取的Excel文件（线程安全）"""

    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    def get_excel(self, file_path: Path, **read_excel_kwargs) -> pd.DataFrame:
        """
        读取Excel文件（带缓存，线程安全）

        Args:
            file_path: Excel文件路径
            **read_excel_kwargs: pd.read_excel的其他参数

        Returns:
            DataFrame
        """
        # 使用绝对路径作为缓存key
        cache_key = str(Path(file_path).resolve())

        with self._lock:
            if cache_key in self._cache:
                logger.debug(f"从缓存读取: {Path(file_path).name}")
                return self._cache[cache_key].copy()

        # 缓存未命中，在锁外读取文件（IO密集，不阻塞其他线程）
        logger.debug(f"首次读取: {Path(file_path).name}")
        df = pd.read_excel(file_path, **read_excel_kwargs)

        with self._lock:
            # 双重检查：可能另一个线程已经读取了同一文件
            if cache_key not in self._cache:
                self._cache[cache_key] = df
            return self._cache[cache_key].copy()

    def clear(self):
        """清空缓存"""
        self._cache.clear()

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        return {
            'cached_files': len(self._cache),
            'files': [Path(k).name for k in self._cache.keys()]
        }
