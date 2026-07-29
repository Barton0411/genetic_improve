"""
基于processed_cow_data_key_traits_detail.xlsx生成系谱识别分析结果
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Optional

from config.breed_constants import is_dairy_breed

logger = logging.getLogger(__name__)
FARM_COLUMNS = ['牧场编号', '牧场名称']


def _build_pedigree_summary(df: pd.DataFrame, labels: list[str]) -> pd.DataFrame:
    result_list = []
    for status in ['是', '否', '总计']:
        group_df = df if status == '总计' else df[df['是否在场'] == status]

        for year_group in labels:
            year_df = group_df[group_df['birth_year_group'] == year_group]
            if year_df.empty:
                continue

            total_count = len(year_df)
            sire_count = year_df['sire_identified'].sum()
            mgs_count = year_df['mgs_identified'].sum()
            mmgs_count = year_df['mmgs_identified'].sum()
            result_list.append({
                '是否在场': status,
                'birth_year_group': year_group,
                '头数': total_count,
                '父号可识别头数': int(sire_count),
                '父号识别率': f'{sire_count / total_count:.2%}',
                '外祖父可识别头数': int(mgs_count),
                '外祖父识别率': f'{mgs_count / total_count:.2%}',
                '外曾外祖父可识别头数': int(mmgs_count),
                '外曾外祖父识别率': f'{mmgs_count / total_count:.2%}',
            })

    result_df = pd.DataFrame(result_list)
    if result_df.empty:
        return result_df

    status_order = {'是': 1, '否': 2, '总计': 3}
    year_order = {year_label: i + 1 for i, year_label in enumerate(labels)}
    result_df['status_sort'] = result_df['是否在场'].map(status_order)
    result_df['year_sort'] = result_df['birth_year_group'].map(year_order)
    return (
        result_df.sort_values(['status_sort', 'year_sort'])
        .drop(['status_sort', 'year_sort'], axis=1)
    )


def generate_pedigree_analysis_result(
    project_path: Path,
    source_df: Optional[pd.DataFrame] = None,
) -> bool:
    """
    基于processed_cow_data_key_traits_detail.xlsx生成系谱识别分析结果

    Args:
        project_path: 项目路径

    Returns:
        是否成功
    """
    try:
        logger.info("开始生成系谱识别分析结果...")

        # 读取processed_cow_data_key_traits_detail.xlsx
        detail_file = project_path / "analysis_results" / "processed_cow_data_key_traits_detail.xlsx"

        if not detail_file.exists():
            logger.error(f"文件不存在: {detail_file}")
            return False

        # 系谱汇总只使用下列字段。大型明细可能有数百列，限制读取列可以
        # 避免汇总阶段再次把整张宽表加载、复制到内存。
        required_columns = {
            'cow_id',
            'sex',
            'breed',
            'birth_year',
            '是否在场',
            'sire_identified',
            'mgs_identified',
            'mmgs_identified',
            *FARM_COLUMNS,
        }
        if source_df is None:
            df = pd.read_excel(
                detail_file,
                usecols=lambda column: str(column) in required_columns,
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
                if str(column) in required_columns
            ]
            df = source_df.loc[:, selected_columns].copy()
        from core.data.processor import add_farm_lineage_columns
        df = add_farm_lineage_columns(
            df, project_path, animal_id_column='cow_id'
        )

        # 处理 sex 字段：空值默认为 '母'
        if 'sex' in df.columns:
            df['sex'] = df['sex'].fillna('母')

        # 只保留母牛（排除公牛）
        df = df[df['sex'] == '母'].copy()

        # 系谱完整性仅统计奶牛品种，排除肉牛品种（如西门塔尔、安格斯等）
        if 'breed' in df.columns:
            before_count = len(df)
            df = df[df['breed'].apply(is_dairy_breed)].copy()
            excluded = before_count - len(df)
            if excluded > 0:
                logger.info(f"  - 已排除非奶牛品种 {excluded} 头（系谱完整性仅统计奶牛）")
        else:
            logger.warning("  - 数据缺少 breed 列，无法按品种过滤，结果可能包含肉牛")
        df['_farm_code_norm'] = (
            df['牧场编号'].fillna('').astype(str).str.strip()
        )

        # 使用当前年份动态生成年份分组（最近4年 + 5年及以前）
        # 例如2025年：bins=[-inf, 2021, 2022, 2023, 2024, 2025]
        #           labels=['2021年及以前', '2022', '2023', '2024', '2025']
        current_year = pd.Timestamp.now().year
        bins = [-float('inf')] + list(range(current_year-4, current_year+1))
        labels = [f'{current_year-4}年及以前'] + [str(year) for year in range(current_year-3, current_year+1)]

        df['birth_year_group'] = pd.cut(
            df['birth_year'],
            bins=bins,
            labels=labels
        )

        result_df = _build_pedigree_summary(df, labels)

        # 保存结果
        output_file = project_path / "analysis_results" / "系谱识别分析结果.xlsx"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 确保cow_id保持为字符串格式
        if 'cow_id' in result_df.columns:
            result_df['cow_id'] = result_df['cow_id'].astype(str)

        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            result_df.to_excel(writer, sheet_name='Sheet1', index=False)

            if all(column in df.columns for column in FARM_COLUMNS):
                farm_keys = (
                    df[FARM_COLUMNS]
                    .fillna('')
                    .astype(str)
                    .drop_duplicates()
                )
                farm_keys = farm_keys[farm_keys['牧场编号'].str.strip() != '']
                if len(farm_keys) > 1:
                    farm_results = []
                    for _, farm in farm_keys.iterrows():
                        farm_code = farm['牧场编号'].strip()
                        farm_name = farm['牧场名称'].strip()
                        farm_df = df[
                            df['_farm_code_norm'] == farm_code
                        ]
                        farm_result = _build_pedigree_summary(farm_df, labels)
                        farm_result.insert(0, '牧场名称', farm_name)
                        farm_result.insert(0, '牧场编号', farm_code)
                        farm_results.append(farm_result)

                    pd.concat(farm_results, ignore_index=True).to_excel(
                        writer, sheet_name='分牧场汇总', index=False
                    )

        logger.info(f"✓ 系谱识别分析结果已保存: {output_file}")
        logger.info(f"  - 总头数: {len(df)}头")
        logger.info(f"  - 在场母牛: {len(df[df['是否在场'] == '是'])}头")
        logger.info(f"  - 离场母牛: {len(df[df['是否在场'] == '否'])}头")

        return True

    except Exception as e:
        logger.error(f"生成系谱识别分析结果失败: {e}", exc_info=True)
        return False
