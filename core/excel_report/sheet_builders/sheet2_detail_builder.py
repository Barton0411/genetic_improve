"""
Sheet 2明细构建器: 全群母牛系谱识别明细
"""

from .base_builder import BaseSheetBuilder
from openpyxl.utils import get_column_letter
import logging

logger = logging.getLogger(__name__)

# 英文列名到中文列名的映射（对应原始cow_data.xlsx的列名）
COLUMN_NAME_MAPPING = {
    'cow_id': '耳号',
    'breed': '品种',
    'sex': '性别',
    'sire': '父亲号',
    'dam': '母亲号',
    'mgs': '外祖父',
    'mgd': '外祖母',
    'mmgs': '外曾外祖父',
    'lac': '胎次',
    'calving_date': '最近产犊日期',
    'birth_date': '牛只出生日期',
    'birth_date_dam': '母亲出生日期',
    'birth_date_mgd': '外祖母出生日期',
    'age': '日龄',
    'services_time': '本胎次配次',
    'DIM': '泌乳天数',
    'peak_milk': '峰值奶量',
    'milk_305': '305天奶量',
    'repro_status': '繁育状态',
    'group': '牛只类别',
    '是否在场': '是否在场',
    'birth_year': '出生年份',
    'sire_identified': '父号可识别',
    'mgs_identified': '外祖父可识别',
    'mmgs_identified': '外曾外祖父可识别'
}


class Sheet2DetailBuilder(BaseSheetBuilder):
    """Sheet 2明细: 全群母牛系谱识别明细"""

    def build(self, data: dict):
        """
        构建Sheet 2明细

        Args:
            data: {
                'detail_all': 全群母牛明细数据DataFrame
            }
        """
        try:
            # 创建Sheet
            self._create_sheet("全群母牛系谱识别明细")
            logger.info("构建Sheet 2明细: 全群母牛系谱识别明细")

            detail_df = data.get('detail_all')
            if detail_df is None or detail_df.empty:
                logger.warning("Sheet 2明细数据为空，跳过构建")
                return

            # 只保留指定的列
            required_columns = [
                'cow_id', 'breed', 'sex', 'sire', 'dam', 'mgs', 'mgd', 'mmgs',
                'lac', 'calving_date', 'birth_date', 'birth_date_dam', 'birth_date_mgd',
                'age', 'services_time', 'DIM', 'peak_milk', 'milk_305', 'repro_status',
                'group', '是否在场', 'birth_year', 'sire_identified', 'mgs_identified', 'mmgs_identified'
            ]

            # 过滤出存在的列
            available_columns = [col for col in required_columns if col in detail_df.columns]
            detail_df = detail_df[available_columns].copy()

            current_row = 1

            # 1. 表头（直接开始，不要标题）
            # 使用中文表头（如果有映射的话）
            headers = list(detail_df.columns)
            chinese_headers = [COLUMN_NAME_MAPPING.get(col, col) for col in headers]
            self._write_header(current_row, chinese_headers)
            current_row += 1

            # 2. 数据行
            for idx, row in detail_df.iterrows():
                values = list(row)
                self._write_data_row(current_row, values, alignment='center')
                current_row += 1

            # 3. 设置列宽
            column_widths = {}
            for col_idx, header in enumerate(headers, start=1):
                if header in ['cow_id', 'sire', 'dam', 'mgs', 'mgd', 'mmgs']:
                    column_widths[col_idx] = 12
                elif header in ['breed', 'sex', '是否在场']:
                    column_widths[col_idx] = 10
                elif 'date' in header.lower():
                    column_widths[col_idx] = 12
                elif 'identified' in header.lower():
                    column_widths[col_idx] = 12
                elif header in ['lac', 'age', 'services_time', 'DIM']:
                    column_widths[col_idx] = 10
                elif header in ['peak_milk', 'milk_305']:
                    column_widths[col_idx] = 12
                elif header in ['repro_status', 'group', 'birth_year']:
                    column_widths[col_idx] = 12
                else:
                    column_widths[col_idx] = 12

            self._set_column_widths(column_widths)

            # 4. 冻结首行
            self._freeze_panes('A2')

            logger.info(f"✓ Sheet 2明细构建完成: {len(detail_df)}行数据")

        except Exception as e:
            logger.error(f"构建Sheet 2明细失败: {e}", exc_info=True)
            raise
