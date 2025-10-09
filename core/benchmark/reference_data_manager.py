"""
外部参考数据管理模块
用于管理外部对比数据（如行业参考数据、参测牛数据等）
"""

import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ReferenceDataTemplate:
    """外部参考数据模板生成器"""

    # 完整的性状列表（与系统中的性状代码对应）
    FULL_TRAIT_LIST = [
        'TPI', 'NM$', 'CM$', 'FM$', 'GM$',
        'MILK', 'FAT', 'PROT', 'FAT %', 'PROT%',
        'SCS', 'DPR', 'HCR', 'CCR', 'PL',
        'SCE', 'DCE', 'SSB', 'DSB',
        'PTAT', 'UDC', 'FLC', 'BDC',
        'ST', 'SG', 'BD', 'DF', 'RA', 'RW',
        'LS', 'LR', 'FA', 'FLS', 'FU',
        'UH', 'UW', 'UC', 'UD', 'FT',
        'RT', 'TL', 'FE', 'FI', 'HI',
        'LIV', 'GL', 'MAST', 'MET', 'RP',
        'KET', 'DA', 'MFV', 'EFC',
        'HLiv', 'FS', 'RFI', 'Milk Speed'
    ]

    @staticmethod
    def generate_template(output_path: Path, trait_columns: List[str] = None) -> bool:
        """
        生成外部参考数据模板Excel文件

        Args:
            output_path: 输出文件路径
            trait_columns: 性状列名列表（如果为None，使用完整列表）

        Returns:
            是否成功
        """
        try:
            # 使用完整的性状列表
            if trait_columns is None:
                # 所有性状前面加"平均"
                trait_columns = [f'平均{trait}' for trait in ReferenceDataTemplate.FULL_TRAIT_LIST]

            # 创建示例数据（可以有更多年份，这里提供10年作为示例）
            example_data = {
                '出生年份': [
                    '2016年',
                    '2017年',
                    '2018年',
                    '2019年',
                    '2020年',
                    '2021年',
                    '2022年',
                    '2023年',
                    '2024年',
                    '2025年',
                ]
            }

            # 添加性状列（示例值）
            for trait in trait_columns:
                example_data[trait] = [None, None, None, None, None, None, None, None, None, None]

            df = pd.DataFrame(example_data)

            # 创建说明sheet
            instructions = pd.DataFrame({
                '使用说明': [
                    '1. 本模板用于上传外部参考数据（如行业数据、参测牛数据等）',
                    '2. 请在"参考数据"sheet中填写数据',
                    '3. "出生年份"列：填写年份（格式：2024年、2023年等）',
                    '4. 性状列：填写对应年份的平均值',
                    '5. 可以包含任意多年的数据（7年、8年或更多）',
                    '6. 如果某个性状没有数据，可以留空',
                    '7. 导入时系统会智能匹配有数据的性状',
                    '8. 外部参考数据仅用于折线图对比，不会添加到表格中',
                    '9. 保存后直接上传到软件中即可使用',
                    '',
                    '注意事项：',
                    '- 性状列名必须是"平均"开头的英文代码（如"平均TPI"、"平均NM$"）',
                    '- 年份格式：统一使用"YYYY年"格式（如"2024年"）',
                    '- 不要添加总计行，外部参考数据仅用于折线图',
                    '- 数据类型应为数值',
                    '- 模板包含57个性状列，根据实际数据填写',
                    '- 可以根据需要增加或删除年份行',
                ]
            })

            # 保存到Excel
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                instructions.to_excel(writer, sheet_name='使用说明', index=False)
                df.to_excel(writer, sheet_name='参考数据', index=False)

            logger.info(f"✓ 外部参考数据模板已生成: {output_path}")
            return True

        except Exception as e:
            logger.error(f"生成外部参考数据模板失败: {e}", exc_info=True)
            return False

    @staticmethod
    def generate_template_from_project(project_path: Path, output_path: Path) -> bool:
        """
        根据项目的关键育种性状分析结果生成匹配的模板

        Args:
            project_path: 项目路径
            output_path: 输出模板路径

        Returns:
            是否成功
        """
        try:
            # 读取项目的关键育种性状分析结果
            analysis_file = project_path / "analysis_results" / "关键育种性状分析结果.xlsx"

            if not analysis_file.exists():
                logger.warning(f"项目中未找到关键育种性状分析结果，使用默认模板")
                return ReferenceDataTemplate.generate_template(output_path)

            # 读取sheet获取列名
            df = pd.read_excel(analysis_file, sheet_name='在群母牛年份汇总')

            # 提取所有性状列（以"平均"开头的列）
            trait_columns = [col for col in df.columns if col.startswith('平均')]

            if not trait_columns:
                logger.warning("未找到性状列，使用默认模板")
                return ReferenceDataTemplate.generate_template(output_path)

            logger.info(f"从项目中提取到 {len(trait_columns)} 个性状列")
            return ReferenceDataTemplate.generate_template(output_path, trait_columns)

        except Exception as e:
            logger.error(f"根据项目生成模板失败: {e}", exc_info=True)
            return ReferenceDataTemplate.generate_template(output_path)


class ReferenceDataParser:
    """外部参考数据解析器"""

    def __init__(self, excel_path: Path):
        """
        初始化解析器

        Args:
            excel_path: Excel文件路径
        """
        self.excel_path = Path(excel_path)

    def validate(self) -> Tuple[bool, str]:
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

            # 检查是否包含"参考数据" sheet（优先）或第一个sheet
            if '参考数据' in excel_file.sheet_names:
                sheet_name = '参考数据'
            else:
                sheet_name = excel_file.sheet_names[0]

            df = pd.read_excel(self.excel_path, sheet_name=sheet_name)

            # 检查必需列
            if '出生年份' not in df.columns and df.columns[0] not in ['出生年份', '出生年', '年份']:
                return False, "文件中未找到'出生年份'列（第一列应为年份）"

            # 检查是否有性状列（以"平均"开头）
            trait_columns = [col for col in df.columns if str(col).startswith('平均')]
            if not trait_columns:
                return False, "文件中未找到任何性状列（列名应以'平均'开头）"

            return True, ""

        except Exception as e:
            return False, f"读取文件失败: {str(e)}"

    def parse(self) -> Optional[Dict]:
        """
        解析外部参考数据

        Returns:
            数据字典，格式与内部对比牧场一致：
            {
                'year_rows': ['2021年', '2022年', ...],
                'traits': ['平均NM$', '平均TPI', ...],
                'cow_count': 0,  # 外部数据可能没有总头数
                'latest_year': 2025,
                'data': {
                    '2021年': {'平均NM$': 850, '平均TPI': 2500, ...},
                    ...
                }
            }
        """
        try:
            logger.info(f"开始解析外部参考数据: {self.excel_path}")

            # 读取数据
            excel_file = pd.ExcelFile(self.excel_path)

            if '参考数据' in excel_file.sheet_names:
                sheet_name = '参考数据'
            else:
                sheet_name = excel_file.sheet_names[0]

            df = pd.read_excel(self.excel_path, sheet_name=sheet_name)

            if df.empty:
                logger.error(f"{sheet_name} sheet为空")
                return None

            # 获取年份列（第一列）
            year_col_name = df.columns[0]
            year_rows = df[year_col_name].tolist()

            # 提取性状列（所有"平均"开头的列）
            trait_columns = [col for col in df.columns if str(col).startswith('平均')]

            if not trait_columns:
                logger.error("未找到任何性状列（以'平均'开头）")
                return None

            # 外部参考数据不需要头数
            cow_count = 0

            # 提取所有数据
            data = {}
            for idx, row in df.iterrows():
                year = row[year_col_name]  # 第一列是年份
                if pd.notna(year):
                    year_data = {}
                    for trait_col in trait_columns:
                        value = row[trait_col]
                        if pd.notna(value):
                            try:
                                year_data[trait_col] = float(value)
                            except:
                                year_data[trait_col] = None
                        else:
                            year_data[trait_col] = None
                    data[str(year)] = year_data

            # 提取最后出生年份
            year_only = [str(y) for y in year_rows if pd.notna(y) and '总计' not in str(y)]
            latest_year = None
            if year_only:
                import re
                last_year_str = year_only[-1]
                year_match = re.search(r'(\d{4})', last_year_str)
                if year_match:
                    latest_year = int(year_match.group(1))

            result = {
                'year_rows': [str(y) for y in year_rows if pd.notna(y)],
                'traits': trait_columns,
                'cow_count': cow_count,
                'data': data,
                'latest_year': latest_year
            }

            logger.info(f"✓ 解析成功: {len(result['year_rows'])}个年份, {len(result['traits'])}个性状")
            return result

        except Exception as e:
            logger.error(f"解析外部参考数据失败: {e}", exc_info=True)
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

        year_rows = data['year_rows']
        traits = data['traits']

        # 生成预览文本
        preview = "✓ 外部参考数据\n"

        # 年份范围
        if year_rows:
            year_only = [y for y in year_rows if '总计' not in y]
            if year_only:
                preview += f"  - 年份数据: {len(year_only)}个年份\n"
            if any('总计' in y for y in year_rows):
                preview += f"  - 包含总计行\n"

        # 性状列表
        if traits:
            trait_names = [t.replace('平均', '') for t in traits[:5]]
            preview += f"  - 包含性状: {', '.join(trait_names)}"
            if len(traits) > 5:
                preview += f"等{len(traits)}个"
            preview += "\n"

        # 最后年份
        if data.get('latest_year'):
            preview += f"  - 数据年份: {data['latest_year']}年\n"

        preview += f"\n注：外部参考数据仅用于折线图对比"

        return preview
