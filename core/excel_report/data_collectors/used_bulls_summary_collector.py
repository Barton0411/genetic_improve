"""
Sheet 8: 已用公牛性状汇总分析 - 数据收集器

收集已配公牛的性状数据，按年份统计汇总
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class UsedBullsSummaryCollector:
    """已用公牛性状汇总数据收集器"""

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
        收集已用公牛性状汇总数据

        Returns:
            包含以下键的字典:
            - summary_data: 汇总表数据 (DataFrame)
            - progress_data: 性状进展数据 (DataFrame)
            - trait_columns: 性状列列表
            - year_range: 年份范围列表
            - scatter_data_all: 全部配种记录散点图数据
            - scatter_data_12m: 近12个月配种记录散点图数据
        """
        logger.info("开始收集已用公牛性状汇总数据...")

        try:
            # 1. 读取数据
            if not self.data_file.exists():
                logger.warning(f"数据文件不存在: {self.data_file}")
                logger.warning("请先执行【配种公牛性状查询】功能生成数据文件")
                return {
                    'summary_data': pd.DataFrame(),
                    'progress_data': pd.DataFrame(),
                    'trait_columns': [],
                    'year_range': [],
                    'scatter_data_all': pd.DataFrame(),
                    'scatter_data_12m': pd.DataFrame()
                }

            # 读取Excel，指定dtype避免类型转换错误
            df = pd.read_excel(self.data_file, dtype={'bull_id': str, '冻精编号': str})
            logger.info(f"读取到 {len(df)} 条配种记录")

            # 2. 确保配种年份列存在
            if '配种年份' not in df.columns and '配种日期' in df.columns:
                df['配种年份'] = pd.to_datetime(df['配种日期']).dt.year

            # 3. 动态识别性状列
            trait_columns = self._identify_trait_columns(df)
            logger.info(f"识别到 {len(trait_columns)} 个性状列: {', '.join(trait_columns[:10])}...")

            # 4. 动态获取年份范围
            year_range = self._get_year_range(df)
            logger.info(f"年份范围: {year_range[0]} - {year_range[-1]} (共{len(year_range)}年)")

            # 5. 按年份统计汇总
            summary_data = self._calculate_summary_by_year(df, trait_columns, year_range)

            # 6. 计算性状进展数据
            progress_data = self._calculate_trait_progress(summary_data, trait_columns, year_range)

            # 7. 准备散点图数据
            scatter_data_all = self._prepare_scatter_data(df, all_data=True)
            scatter_data_12m = self._prepare_scatter_data(df, all_data=False)

            result = {
                'summary_data': summary_data,
                'progress_data': progress_data,
                'trait_columns': trait_columns,
                'year_range': year_range,
                'scatter_data_all': scatter_data_all,
                'scatter_data_12m': scatter_data_12m
            }

            logger.info("已用公牛性状汇总数据收集完成")
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

        # 进一步排除可能的非性状列（如Eval Date）
        # 但保留它以便用户选择
        return trait_columns

    def _get_year_range(self, df: pd.DataFrame) -> List[int]:
        """
        获取数据中的年份范围

        Args:
            df: 数据DataFrame

        Returns:
            排序后的年份列表
        """
        years = df['配种年份'].dropna().unique()
        return sorted([int(y) for y in years])

    def _calculate_summary_by_year(
        self,
        df: pd.DataFrame,
        trait_columns: List[str],
        year_range: List[int]
    ) -> pd.DataFrame:
        """
        按年份统计汇总数据

        Args:
            df: 数据DataFrame
            trait_columns: 性状列列表
            year_range: 年份范围

        Returns:
            汇总数据DataFrame
        """
        summary_rows = []

        for year in year_range:
            year_data = df[df['配种年份'] == year]

            row = {
                '年份': year,
                '使用公牛数': year_data['冻精编号'].nunique(),  # 去重统计
                '配种头次': len(year_data)  # 包括所有记录，即使性状为空
            }

            # 统计各性状平均值（只统计非空值）
            for trait in trait_columns:
                if trait in year_data.columns:
                    # 排除 Eval Date 等非数值列
                    if trait == 'Eval Date':
                        continue

                    trait_values = year_data[trait].dropna()
                    if len(trait_values) > 0:
                        row[f'平均{trait}'] = trait_values.mean()
                    else:
                        row[f'平均{trait}'] = None

            summary_rows.append(row)

        summary_df = pd.DataFrame(summary_rows)

        # 添加总平均行
        total_row = {'年份': '总平均'}
        total_row['使用公牛数'] = int(summary_df['使用公牛数'].mean())
        total_row['配种头次'] = int(summary_df['配种头次'].mean())

        for trait in trait_columns:
            if trait == 'Eval Date':
                continue
            col_name = f'平均{trait}'
            if col_name in summary_df.columns:
                avg_value = summary_df[col_name].mean()
                total_row[col_name] = avg_value if pd.notna(avg_value) else None

        summary_df = pd.concat([summary_df, pd.DataFrame([total_row])], ignore_index=True)

        return summary_df

    def _calculate_trait_progress(
        self,
        summary_df: pd.DataFrame,
        trait_columns: List[str],
        year_range: List[int]
    ) -> pd.DataFrame:
        """
        计算性状进展数据

        Args:
            summary_df: 汇总数据DataFrame
            trait_columns: 性状列列表
            year_range: 年份范围

        Returns:
            性状进展数据DataFrame
        """
        progress_rows = []

        for trait in trait_columns:
            if trait == 'Eval Date':
                continue

            col_name = f'平均{trait}'
            if col_name not in summary_df.columns:
                continue

            # 获取各年份的值（排除总平均行）
            yearly_values = summary_df[summary_df['年份'] != '总平均'][col_name].tolist()

            # 跳过全是空值的性状
            if all(pd.isna(v) for v in yearly_values):
                continue

            row = {'性状': trait}

            # 计算逐年增长
            yearly_growth = []
            for i in range(len(yearly_values) - 1):
                if pd.notna(yearly_values[i]) and pd.notna(yearly_values[i + 1]):
                    growth = yearly_values[i + 1] - yearly_values[i]
                    yearly_growth.append(growth)
                    row[f'{year_range[i]}→{year_range[i+1]}'] = growth
                else:
                    row[f'{year_range[i]}→{year_range[i+1]}'] = None

            # 计算年均增长
            if yearly_growth:
                row['年均增长'] = sum(yearly_growth) / len(yearly_growth)
            else:
                row['年均增长'] = None

            # 计算累计增长
            first_valid = next((v for v in yearly_values if pd.notna(v)), None)
            last_valid = next((v for v in reversed(yearly_values) if pd.notna(v)), None)

            if first_valid is not None and last_valid is not None and first_valid != 0:
                cumulative = last_valid - first_valid
                growth_rate = (cumulative / abs(first_valid)) * 100
                row[f'{len(year_range)}年累计'] = cumulative
                row['增长率'] = growth_rate

                # 调试日志
                logger.debug(f"    {trait}: first={first_valid:.3f}, last={last_valid:.3f}, cumulative={cumulative:.3f}, rate={growth_rate:.2f}%")
            else:
                row[f'{len(year_range)}年累计'] = None
                row['增长率'] = None

            progress_rows.append(row)

        return pd.DataFrame(progress_rows)

    def _prepare_scatter_data(
        self,
        df: pd.DataFrame,
        all_data: bool = True
    ) -> pd.DataFrame:
        """
        准备散点图数据

        Args:
            df: 数据DataFrame
            all_data: True=全部数据，False=近12个月

        Returns:
            散点图数据DataFrame
        """
        scatter_df = df.copy()

        # 筛选近12个月数据
        if not all_data:
            today = datetime.now()
            twelve_months_ago = today - pd.Timedelta(days=365)
            scatter_df['配种日期'] = pd.to_datetime(scatter_df['配种日期'])
            scatter_df = scatter_df[scatter_df['配种日期'] >= twelve_months_ago]

        # 确保配种类型列存在（兼容"配种类型"和"冻精类型"两种列名）
        if '配种类型' not in scatter_df.columns:
            if '冻精类型' in scatter_df.columns:
                scatter_df['配种类型'] = scatter_df['冻精类型']
            else:
                scatter_df['配种类型'] = '其他'

        # 将没有性状数据的记录标记为"其他"类型
        # 检查所有性状列是否都为空
        trait_cols = [col for col in scatter_df.columns if col not in self.BASE_COLUMNS and col != 'Eval Date']
        if len(trait_cols) > 0:
            all_traits_null = scatter_df[trait_cols].isna().all(axis=1)
            scatter_df.loc[all_traits_null, '配种类型'] = '其他'

        # 按配种类型和公牛号排序
        # 配种类型排序：性控 → 常规 → 其他
        type_order = {'性控': 1, '常规': 2, '其他': 3}
        scatter_df['type_sort'] = scatter_df['配种类型'].map(type_order).fillna(4)
        scatter_df = scatter_df.sort_values(['type_sort', '冻精编号'])

        # 返回需要的列
        return scatter_df[['配种日期', '冻精编号', '配种类型']].copy()


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
        collector = UsedBullsSummaryCollector(test_project)
        result = collector.collect()

        print("=" * 60)
        print("数据收集成功！")
        print("=" * 60)
        print(f"\n性状列数量: {len(result['trait_columns'])}")
        print(f"年份范围: {result['year_range']}")
        print(f"\n汇总表形状: {result['summary_data'].shape}")
        print(f"进展表形状: {result['progress_data'].shape}")
        print(f"\n全部散点数据: {len(result['scatter_data_all'])} 条")
        print(f"近12个月散点数据: {len(result['scatter_data_12m'])} 条")

        print("\n汇总表预览:")
        print(result['summary_data'].head())

        print("\n进展表预览:")
        print(result['progress_data'].head())

    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_collector()
