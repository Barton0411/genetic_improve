"""
Sheet 9: 已用公牛性状明细 - 数据收集器

按年份展示每年使用的冻精明细及其性状
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


class UsedBullsDetailCollector:
    """已用公牛性状明细数据收集器"""

    # 基础列（不是性状列）
    BASE_COLUMNS = [
        '配种日期', '冻精编号', '配种年份', '母牛号', '耳号',
        '配种公牛号', '原始公牛号', '配种类型', '使用支数', 'bull_id',
        '父号',  # 公牛父号，不是性状列
        '冻精类型'  # 冻精类型（性控/普通），不是性状列
    ]

    def __init__(self, project_path: Path):
        """
        初始化数据收集器

        Args:
            project_path: 项目路径
        """
        self.project_path = project_path
        self.data_file = project_path / "analysis_results" / "processed_mated_bull_traits.xlsx"

    def collect(self) -> Dict:
        """
        收集已用公牛性状明细数据

        Returns:
            包含以下键的字典:
            - yearly_details: 字典，键为年份，值为该年的公牛明细DataFrame
            - trait_columns: 性状列列表
            - year_range: 年份范围列表（倒序，从新到旧）
        """
        logger.info("开始收集已用公牛性状明细数据...")

        try:
            # 1. 读取数据
            if not self.data_file.exists():
                logger.warning(f"数据文件不存在: {self.data_file}")
                logger.warning("请先执行【配种公牛性状查询】功能生成数据文件")
                return {
                    'yearly_details': {},
                    'trait_columns': [],
                    'year_range': []
                }

            # 读取Excel，指定dtype避免类型转换错误
            df = pd.read_excel(self.data_file, dtype={'bull_id': str, '冻精编号': str})
            logger.info(f"读取到 {len(df)} 条配种记录")

            # 2. 确保配种年份列存在
            if '配种年份' not in df.columns and '配种日期' in df.columns:
                df['配种年份'] = pd.to_datetime(df['配种日期']).dt.year

            # 3. 动态识别性状列
            trait_columns = self._identify_trait_columns(df)
            logger.info(f"识别到 {len(trait_columns)} 个性状列")

            # 4. 动态获取年份范围（倒序）
            year_range = self._get_year_range(df, reverse=True)
            logger.info(f"年份范围: {year_range[0]} - {year_range[-1]} (共{len(year_range)}年，倒序)")

            # 5. 按年份汇总公牛使用明细
            yearly_details = self._calculate_yearly_details(df, trait_columns, year_range)

            result = {
                'yearly_details': yearly_details,
                'trait_columns': trait_columns,
                'year_range': year_range
            }

            logger.info("已用公牛性状明细数据收集完成")
            return result

        except Exception as e:
            logger.error(f"收集数据失败: {e}", exc_info=True)
            raise

    def _identify_trait_columns(self, df: pd.DataFrame) -> List[str]:
        """
        动态识别性状列

        Args:
            df: 数据DataFrame

        Returns:
            性状列名列表
        """
        # 排除基础列，剩下的就是性状列
        trait_columns = [col for col in df.columns if col not in self.BASE_COLUMNS]
        return trait_columns

    def _get_year_range(self, df: pd.DataFrame, reverse: bool = False) -> List[int]:
        """
        获取数据中的年份范围

        Args:
            df: 数据DataFrame
            reverse: 是否倒序（从新到旧）

        Returns:
            排序后的年份列表
        """
        years = df['配种年份'].dropna().unique()
        sorted_years = sorted([int(y) for y in years], reverse=reverse)
        return sorted_years

    def _calculate_yearly_details(
        self,
        df: pd.DataFrame,
        trait_columns: List[str],
        year_range: List[int]
    ) -> Dict[int, pd.DataFrame]:
        """
        按年份汇总公牛使用明细

        Args:
            df: 数据DataFrame
            trait_columns: 性状列列表
            year_range: 年份范围

        Returns:
            字典，键为年份，值为该年的公牛明细DataFrame
        """
        yearly_details = {}

        for year in year_range:
            year_data = df[df['配种年份'] == year]

            # 按冻精编号分组统计
            detail_rows = []

            grouped = year_data.groupby('冻精编号')

            for bull_id, bull_data in grouped:
                # 使用'冻精类型'列（而非'配种类型'）
                semen_type = '未知'
                if '冻精类型' in bull_data.columns and len(bull_data['冻精类型'].mode()) > 0:
                    semen_type = bull_data['冻精类型'].mode()[0]
                elif '配种类型' in bull_data.columns and len(bull_data['配种类型'].mode()) > 0:
                    semen_type = bull_data['配种类型'].mode()[0]

                row = {
                    '冻精编号': bull_id,
                    '配种类型': semen_type,
                    '使用次数': len(bull_data)
                }

                # 统计各性状值（取第一条非空值，或平均值）
                for trait in trait_columns:
                    if trait == 'Eval Date':
                        # Eval Date取最新日期
                        valid_dates = bull_data[trait].dropna()
                        if len(valid_dates) > 0:
                            row[trait] = valid_dates.iloc[-1]
                        else:
                            row[trait] = None
                    else:
                        # 其他性状取平均值（如果有多条记录）
                        trait_values = bull_data[trait].dropna()
                        if len(trait_values) > 0:
                            # 如果所有值相同(公牛性状应该相同)，取第一个
                            # 如果不同(异常情况)，取平均值
                            unique_values = trait_values.unique()
                            if len(unique_values) == 1:
                                row[trait] = unique_values[0]
                            else:
                                row[trait] = trait_values.mean()
                        else:
                            row[trait] = None

                detail_rows.append(row)

            # 创建DataFrame
            detail_df = pd.DataFrame(detail_rows)

            # 按使用次数降序排序
            if not detail_df.empty:
                detail_df = detail_df.sort_values('使用次数', ascending=False)

            yearly_details[year] = detail_df

        return yearly_details


def test_collector():
    """测试数据收集器"""
    import sys
    from pathlib import Path

    # 假设测试项目路径
    test_project = Path("/path/to/test/project")

    if not test_project.exists():
        print("测试项目路径不存在")
        return

    try:
        collector = UsedBullsDetailCollector(test_project)
        result = collector.collect()

        print("=" * 60)
        print("数据收集成功！")
        print("=" * 60)
        print(f"\n性状列数量: {len(result['trait_columns'])}")
        print(f"年份范围: {result['year_range']}")
        print(f"\n各年份数据:")

        for year, detail_df in result['yearly_details'].items():
            print(f"\n{year}年:")
            print(f"  使用公牛数: {len(detail_df)}")
            print(f"  总配种头次: {detail_df['使用次数'].sum()}")
            print(f"  数据形状: {detail_df.shape}")
            print(f"\n  前3名公牛:")
            print(detail_df.head(3)[['冻精编号', '配种类型', '使用次数']])

    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_collector()
