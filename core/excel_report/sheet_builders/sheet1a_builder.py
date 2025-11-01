"""
Sheet 2构建器: 牧场牛群原始数据
使用统一格式的明细表样式
"""

from .base_builder import BaseSheetBuilder
from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class Sheet1ABuilder(BaseSheetBuilder):
    """Sheet 2: 牧场牛群原始数据（使用统一明细表格式）"""

    def build(self, data: dict):
        """
        构建Sheet 2 - 使用统一明细表格式显示原始数据

        Args:
            data: {
                'raw_file_path': Path  # 原始Excel文件路径
            }
        """
        try:
            logger.info("构建Sheet 2: 牧场牛群原始数据")

            raw_file_path = data.get('raw_file_path')
            if not raw_file_path or not Path(raw_file_path).exists():
                logger.warning(f"原始母牛数据文件不存在: {raw_file_path}")
                # 创建空Sheet
                self._create_sheet("牧场牛群原始数据")
                self.ws.cell(row=1, column=1, value="暂无原始数据")
                return

            # 创建Sheet
            self._create_sheet("牧场牛群原始数据")

            # 使用pandas读取Excel文件（更快更简单）
            logger.info(f"读取原始数据文件: {Path(raw_file_path).name}")
            df = pd.read_excel(raw_file_path)

            total_rows = len(df)
            total_cols = len(df.columns)
            logger.info(f"原始数据: {total_rows} 行 × {total_cols} 列")

            # 报告进度
            if self.progress_callback:
                self.progress_callback(18, f"写入数据...")

            # 设置默认列宽（统一12）
            column_widths = {i: 12 for i in range(1, total_cols + 1)}

            # 使用快速方法写入数据
            current_row = self._write_dataframe_fast(
                df,
                start_row=1,
                data_alignment='center',
                column_widths=column_widths,
                progress_callback_interval=500
            )

            # 冻结首行
            self._freeze_panes('A2')

            logger.info(f"✓ Sheet 2构建完成: {total_rows}行 × {total_cols}列")

        except Exception as e:
            logger.error(f"构建Sheet 2失败: {e}", exc_info=True)
            raise
