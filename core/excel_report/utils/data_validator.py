"""
数据校验器
校验数据的合法性和完整性
"""

import pandas as pd
import logging

logger = logging.getLogger(__name__)


class DataValidator:
    """数据校验器"""

    @staticmethod
    def validate_farm_name(name: str) -> bool:
        """
        校验牧场名称

        Args:
            name: 牧场名称

        Returns:
            是否合法
        """
        return bool(name and isinstance(name, str) and len(name.strip()) > 0)

    @staticmethod
    def validate_percentage(value: float, min_val: float = 0.0, max_val: float = 100.0) -> bool:
        """
        校验百分比

        Args:
            value: 数值
            min_val: 最小值
            max_val: 最大值

        Returns:
            是否合法
        """
        try:
            val = float(value)
            return min_val <= val <= max_val
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_numeric(value, allow_negative: bool = True) -> bool:
        """
        校验数值

        Args:
            value: 待校验值
            allow_negative: 是否允许负数

        Returns:
            是否合法
        """
        try:
            val = float(value)
            if not allow_negative and val < 0:
                return False
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_dataframe(df: pd.DataFrame, required_columns: list) -> tuple[bool, str]:
        """
        校验DataFrame

        Args:
            df: DataFrame对象
            required_columns: 必需列列表

        Returns:
            (是否合法, 错误消息)
        """
        if df is None or df.empty:
            return False, "数据为空"

        missing_columns = set(required_columns) - set(df.columns)
        if missing_columns:
            return False, f"缺少必需列: {', '.join(missing_columns)}"

        return True, ""
