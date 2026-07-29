"""
基于processed_cow_data_key_traits_final.xlsx生成关键育种性状分析结果
"""

import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)
FARM_COLUMNS = ['牧场编号', '牧场名称']


def _calculate_dynamic_distribution(df: pd.DataFrame, score_column: str, step: int) -> pd.DataFrame:
    """
    计算分布统计（固定9组，以0为基准，整数步长）

    Args:
        df: 数据DataFrame
        score_column: 育种值列名
        step: 步长（已废弃，保留参数以保持兼容性）

    Returns:
        分布统计DataFrame
    """
    # 获取有效数据
    valid_data = df[df[score_column].notna()][score_column]
    total_count = len(valid_data)

    if total_count == 0:
        return pd.DataFrame(columns=['分布区间', '头数', '占比'])

    # 获取最小值和最大值
    min_val = valid_data.min()
    max_val = valid_data.max()

    # 计算总范围
    range_size = max_val - min_val

    # 计算理想步长（使得9组能覆盖范围）
    ideal_step = range_size / 9

    # 选择合适的整数步长（10, 30, 50, 100, 200, 500, 1000等）
    step_candidates = [10, 30, 50, 100, 200, 300, 500, 1000, 2000, 5000]
    actual_step = 10  # 默认步长

    for candidate in step_candidates:
        if candidate >= ideal_step:
            actual_step = candidate
            break
    else:
        # 如果所有候选步长都不够，使用最大的或计算更大的
        actual_step = ((int(ideal_step) // 1000) + 1) * 1000

    # 确定起始点（以0为基准）
    # 负数方向：找到能覆盖min_val的最小起点
    if min_val < 0:
        start_point = -((-int(min_val) // actual_step) + 1) * actual_step
    else:
        start_point = (int(min_val) // actual_step) * actual_step

    # 生成9个区间
    bins = [start_point + i * actual_step for i in range(10)]

    # 确保bins能覆盖max_val
    while bins[-1] < max_val:
        bins = [b + actual_step for b in bins]

    distribution_data = []

    for i in range(9):
        lower = bins[i]
        upper = bins[i + 1]

        # 最后一个区间包含上界
        if i == 8:
            count = ((valid_data >= lower) & (valid_data <= upper)).sum()
        else:
            count = ((valid_data >= lower) & (valid_data < upper)).sum()

        # 格式化区间显示
        range_name = f'{int(lower)}~{int(upper)}'
        percentage = (count / total_count * 100)

        distribution_data.append({
            '分布区间': range_name,
            '头数': int(count),
            '占比': f'{percentage:.1f}%'
        })

    return pd.DataFrame(distribution_data)


def _calculate_year_summary(
    df: pd.DataFrame,
    year_groups: list[str],
    score_columns: list[str],
    total_label: str,
) -> pd.DataFrame:
    rows = []
    for year_group in year_groups:
        year_df = df[df['year_group'] == year_group]
        if year_df.empty:
            continue

        row_data = {'出生年份': year_group, '头数': len(year_df)}
        for score_col in score_columns:
            trait_name = score_col.replace('_score', '')
            avg_value = year_df[score_col].mean()
            row_data[f'平均{trait_name}'] = (
                round(avg_value, 2) if pd.notna(avg_value) else None
            )
        rows.append(row_data)

    total_row = {'出生年份': total_label, '头数': len(df)}
    for score_col in score_columns:
        trait_name = score_col.replace('_score', '')
        avg_value = df[score_col].mean()
        total_row[f'平均{trait_name}'] = (
            round(avg_value, 2) if pd.notna(avg_value) else None
        )
    rows.append(total_row)
    return pd.DataFrame(rows)


def _with_farm_columns(frame: pd.DataFrame, farm_code: str, farm_name: str) -> pd.DataFrame:
    result = frame.copy()
    result.insert(0, '牧场名称', farm_name)
    result.insert(0, '牧场编号', farm_code)
    return result


def generate_key_traits_analysis_result(
    project_path: Path,
    source_df: Optional[pd.DataFrame] = None,
) -> bool:
    """
    基于processed_cow_data_key_traits_final.xlsx生成关键育种性状分析结果

    Args:
        project_path: 项目路径

    Returns:
        是否成功
    """
    try:
        logger.info("开始生成关键育种性状分析结果...")

        # 读取processed_cow_data_key_traits_final.xlsx
        final_file = project_path / "analysis_results" / "processed_cow_data_key_traits_final.xlsx"

        if not final_file.exists():
            logger.error(f"文件不存在: {final_file}")
            return False

        # 最终明细可能有几十万行、数百列。汇总只需要基础字段和
        # ``*_score``，按列读取可避免为无关的三代性状/来源列占用数 GB 内存。
        required_columns = {
            'cow_id',
            'sex',
            '是否在场',
            'birth_year',
            *FARM_COLUMNS,
        }
        if source_df is None:
            df = pd.read_excel(
                final_file,
                usecols=lambda column: (
                    str(column) in required_columns
                    or str(column).endswith('_score')
                ),
                dtype={
                    'cow_id': str,
                    '牧场编号': str,
                    '牧场名称': str,
                },
            )
        else:
            selected_columns = [
                column
                for column in source_df.columns
                if (
                    str(column) in required_columns
                    or str(column).endswith('_score')
                )
            ]
            df = source_df.loc[:, selected_columns].copy()
        from core.data.processor import add_farm_lineage_columns
        df = add_farm_lineage_columns(
            df, project_path, animal_id_column='cow_id'
        )

        # 只保留母牛（排除公牛）
        df_all = df[df['sex'] == '母'].copy()
        del df
        df_all['_farm_code_norm'] = (
            df_all['牧场编号'].fillna('').astype(str).str.strip()
        )

        # 区分在群母牛和全部母牛
        df_present = df_all[df_all['是否在场'] == '是'].copy()  # 在群母牛

        # 定义动态年份分组（最近4年 + 第5年及以前）
        current_year = datetime.now().year
        max_year = df_all['birth_year'].max()
        if pd.notna(max_year):
            reference_year = int(max_year)
        else:
            reference_year = current_year

        def get_year_group(year):
            if pd.isna(year):
                return '未知'
            year = int(year)

            # 动态计算最近4年
            if year >= reference_year:
                return f'{reference_year}年'
            elif year == reference_year - 1:
                return f'{reference_year - 1}年'
            elif year == reference_year - 2:
                return f'{reference_year - 2}年'
            elif year == reference_year - 3:
                return f'{reference_year - 3}年'
            else:
                return f'{reference_year - 4}年及以前'

        df_all['year_group'] = df_all['birth_year'].apply(get_year_group)
        df_present['year_group'] = df_present['birth_year'].apply(get_year_group)

        # 获取所有_score列
        score_columns = [col for col in df_all.columns if col.endswith('_score')]

        year_groups = [
            f'{reference_year - 4}年及以前',
            f'{reference_year - 3}年',
            f'{reference_year - 2}年',
            f'{reference_year - 1}年',
            f'{reference_year}年'
        ]

        result_df_present = _calculate_year_summary(
            df_present, year_groups, score_columns, '在群母牛总计'
        )
        result_df_all = _calculate_year_summary(
            df_all, year_groups, score_columns, '全部母牛总计'
        )

        # === 生成NM$分布统计（步长300，以0为基准） ===
        nm_distribution_present = _calculate_dynamic_distribution(df_present, 'NM$_score', step=300)
        nm_distribution_all = _calculate_dynamic_distribution(df_all, 'NM$_score', step=300)

        # === 生成TPI分布统计（步长500，以0为基准） ===
        tpi_distribution_present = _calculate_dynamic_distribution(df_present, 'TPI_score', step=500)
        tpi_distribution_all = _calculate_dynamic_distribution(df_all, 'TPI_score', step=500)

        # 保存到Excel（多个sheet）
        output_file = project_path / "analysis_results" / "关键育种性状分析结果.xlsx"

        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            result_df_present.to_excel(writer, sheet_name='在群母牛年份汇总', index=False)
            result_df_all.to_excel(writer, sheet_name='全部母牛年份汇总', index=False)
            nm_distribution_present.to_excel(writer, sheet_name='在群母牛NM$分布', index=False)
            nm_distribution_all.to_excel(writer, sheet_name='全部母牛NM$分布', index=False)
            tpi_distribution_present.to_excel(writer, sheet_name='在群母牛TPI分布', index=False)
            tpi_distribution_all.to_excel(writer, sheet_name='全部母牛TPI分布', index=False)

            if all(column in df_all.columns for column in FARM_COLUMNS):
                farm_keys = (
                    df_all[FARM_COLUMNS]
                    .fillna('')
                    .astype(str)
                    .drop_duplicates()
                )
                farm_keys = farm_keys[farm_keys['牧场编号'].str.strip() != '']
                if len(farm_keys) > 1:
                    farm_present_years = []
                    farm_all_years = []
                    farm_present_nm = []
                    farm_all_nm = []
                    farm_present_tpi = []
                    farm_all_tpi = []

                    for _, farm in farm_keys.iterrows():
                        farm_code = farm['牧场编号'].strip()
                        farm_name = farm['牧场名称'].strip()
                        all_subset = df_all[
                            df_all['_farm_code_norm'] == farm_code
                        ]
                        present_subset = df_present[
                            df_present['_farm_code_norm'] == farm_code
                        ]

                        farm_present_years.append(_with_farm_columns(
                            _calculate_year_summary(
                                present_subset, year_groups, score_columns, '在群母牛总计'
                            ),
                            farm_code,
                            farm_name,
                        ))
                        farm_all_years.append(_with_farm_columns(
                            _calculate_year_summary(
                                all_subset, year_groups, score_columns, '全部母牛总计'
                            ),
                            farm_code,
                            farm_name,
                        ))
                        farm_present_nm.append(_with_farm_columns(
                            _calculate_dynamic_distribution(
                                present_subset, 'NM$_score', step=300
                            ),
                            farm_code,
                            farm_name,
                        ))
                        farm_all_nm.append(_with_farm_columns(
                            _calculate_dynamic_distribution(all_subset, 'NM$_score', step=300),
                            farm_code,
                            farm_name,
                        ))
                        farm_present_tpi.append(_with_farm_columns(
                            _calculate_dynamic_distribution(
                                present_subset, 'TPI_score', step=500
                            ),
                            farm_code,
                            farm_name,
                        ))
                        farm_all_tpi.append(_with_farm_columns(
                            _calculate_dynamic_distribution(all_subset, 'TPI_score', step=500),
                            farm_code,
                            farm_name,
                        ))

                    pd.concat(farm_present_years, ignore_index=True).to_excel(
                        writer, sheet_name='分牧场在群年份汇总', index=False
                    )
                    pd.concat(farm_all_years, ignore_index=True).to_excel(
                        writer, sheet_name='分牧场全部年份汇总', index=False
                    )
                    pd.concat(farm_present_nm, ignore_index=True).to_excel(
                        writer, sheet_name='分牧场在群NM$分布', index=False
                    )
                    pd.concat(farm_all_nm, ignore_index=True).to_excel(
                        writer, sheet_name='分牧场全部NM$分布', index=False
                    )
                    pd.concat(farm_present_tpi, ignore_index=True).to_excel(
                        writer, sheet_name='分牧场在群TPI分布', index=False
                    )
                    pd.concat(farm_all_tpi, ignore_index=True).to_excel(
                        writer, sheet_name='分牧场全部TPI分布', index=False
                    )

        logger.info(f"✓ 关键育种性状分析结果已保存: {output_file}")
        logger.info(f"  - 在群母牛: {len(df_present)}头")
        logger.info(f"  - 全部母牛: {len(df_all)}头")
        logger.info(f"  - 性状数量: {len(score_columns)}个")
        logger.info(f"  - 包含6个sheet: 在群/全部母牛的年份汇总、NM$分布、TPI分布")

        return True

    except Exception as e:
        logger.error(f"生成关键育种性状分析结果失败: {e}", exc_info=True)
        return False
