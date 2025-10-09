"""
对比牧场Excel文件解析工具
解析"关键育种性状分析结果.xlsx"文件
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TraitsExcelParser:
    """育种性状Excel文件解析器"""

    def __init__(self, excel_path: Path):
        """
        初始化解析器

        Args:
            excel_path: Excel文件路径
        """
        self.excel_path = Path(excel_path)

    def validate(self) -> tuple[bool, str]:
        """
        验证Excel文件是否有效

        Returns:
            (是否有效, 错误信息)
        """
        if not self.excel_path.exists():
            return False, "文件不存在"

        if not self.excel_path.suffix.lower() in ['.xlsx', '.xls']:
            return False, "文件格式不正确，请选择Excel文件"

        try:
            # 尝试读取Excel
            excel_file = pd.ExcelFile(self.excel_path)

            # 检查是否包含必需的 sheet
            required_sheets = ['在群母牛年份汇总', '全部母牛年份汇总']
            missing_sheets = [s for s in required_sheets if s not in excel_file.sheet_names]

            if missing_sheets:
                return False, f"文件中未找到以下sheet: {', '.join(missing_sheets)}"

            return True, ""

        except Exception as e:
            return False, f"读取文件失败: {str(e)}"

    def _parse_sheet(self, sheet_name: str) -> Optional[Dict]:
        """
        解析单个sheet

        Args:
            sheet_name: sheet名称

        Returns:
            sheet数据字典
        """
        try:
            df = pd.read_excel(self.excel_path, sheet_name=sheet_name)

            if df.empty:
                logger.error(f"{sheet_name} sheet为空")
                return None

            # 提取年份行（第一列）
            year_rows = df.iloc[:, 0].tolist()

            # 提取性状列（所有"平均"开头的列）
            trait_columns = [col for col in df.columns if str(col).startswith('平均')]

            if not trait_columns:
                logger.error(f"未找到任何性状列（以'平均'开头）")
                return None

            # 提取总头数（从总计行）
            total_row_name = '在群母牛总计' if '在群' in sheet_name else '全部母牛总计'
            total_row = df[df.iloc[:, 0] == total_row_name]
            cow_count = 0
            if not total_row.empty and '头数' in df.columns:
                cow_count = int(total_row['头数'].iloc[0])

            # 提取所有数据
            data = {}
            for idx, row in df.iterrows():
                year = row.iloc[0]  # 第一列是年份
                if pd.notna(year):
                    year_data = {}
                    for trait_col in trait_columns:
                        value = row[trait_col]
                        if pd.notna(value):
                            year_data[trait_col] = float(value)
                        else:
                            year_data[trait_col] = None
                    data[str(year)] = year_data

            # 提取最后出生年份（用于表格备注）
            year_only = [str(y) for y in year_rows if pd.notna(y) and '总计' not in str(y)]
            latest_year = None
            if year_only:
                # 从最后一个年份字符串中提取数字年份
                last_year_str = year_only[-1]
                # 提取数字部分，如"2025年" -> 2025
                import re
                year_match = re.search(r'(\d{4})', last_year_str)
                if year_match:
                    latest_year = int(year_match.group(1))

            result = {
                'year_rows': [str(y) for y in year_rows if pd.notna(y)],
                'traits': trait_columns,
                'cow_count': cow_count,
                'data': data,
                'latest_year': latest_year  # 最后出生年份
            }

            return result

        except Exception as e:
            logger.error(f"解析{sheet_name}失败: {e}", exc_info=True)
            return None

    def parse(self) -> Optional[Dict]:
        """
        解析Excel文件，提取所有数据

        Returns:
            数据字典，包含：
            {
                'present_summary': {
                    'year_rows': ['2021年及以前', '2022年', ...],
                    'traits': ['平均NM$', '平均TPI', ...],
                    'cow_count': 380,
                    'latest_year': 2025,
                    'data': {
                        '2021年及以前': {'平均NM$': 850, '平均TPI': 2500, ...},
                        '2022年': {...},
                        ...
                    }
                },
                'all_summary': {
                    'year_rows': [...],
                    'traits': [...],
                    'cow_count': 520,
                    'latest_year': 2025,
                    'data': {...}
                }
            }
        """
        try:
            logger.info(f"开始解析Excel文件: {self.excel_path}")

            # 解析在群母牛年份汇总
            present_data = self._parse_sheet('在群母牛年份汇总')
            if not present_data:
                logger.error("解析在群母牛年份汇总失败")
                return None

            # 解析全部母牛年份汇总
            all_data = self._parse_sheet('全部母牛年份汇总')
            if not all_data:
                logger.error("解析全部母牛年份汇总失败")
                return None

            result = {
                'present_summary': present_data,
                'all_summary': all_data
            }

            logger.info(f"✓ 解析成功: 在群母牛 {len(present_data['year_rows'])}个年份, "
                       f"全部母牛 {len(all_data['year_rows'])}个年份")
            return result

        except Exception as e:
            logger.error(f"解析Excel文件失败: {e}", exc_info=True)
            return None

    def get_preview_info(self) -> Optional[str]:
        """
        获取数据预览信息（用于UI显示）

        Returns:
            预览文本
        """
        data = self.parse()
        if not data:
            return None

        present_data = data['present_summary']
        all_data = data['all_summary']

        # 生成预览文本
        preview = "✓ 在群母牛年份汇总\n"

        # 年份范围
        year_rows = present_data['year_rows']
        if year_rows:
            # 过滤掉总计行
            year_only = [y for y in year_rows if '总计' not in y]
            if year_only:
                preview += f"  - 年份数据: {len(year_only)}个年份\n"
            if any('总计' in y for y in year_rows):
                preview += f"  - 包含总计行\n"

        # 性状列表
        traits = present_data['traits']
        if traits:
            trait_names = [t.replace('平均', '') for t in traits[:5]]  # 只显示前5个
            preview += f"  - 包含性状: {', '.join(trait_names)}"
            if len(traits) > 5:
                preview += f"等{len(traits)}个"
            preview += "\n"

        # 总头数
        cow_count = present_data['cow_count']
        if cow_count > 0:
            preview += f"  - 在群头数: {cow_count}头\n"

        # 全部母牛信息
        preview += "\n✓ 全部母牛年份汇总\n"
        all_cow_count = all_data['cow_count']
        if all_cow_count > 0:
            preview += f"  - 全部头数: {all_cow_count}头\n"

        # 最后出生年份
        if present_data.get('latest_year'):
            preview += f"\n数据年份: {present_data['latest_year']}年\n"

        return preview
