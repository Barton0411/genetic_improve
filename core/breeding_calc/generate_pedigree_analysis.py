"""
基于processed_cow_data_key_traits_detail.xlsx生成系谱识别分析结果
"""

import pandas as pd
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_pedigree_analysis_result(project_path: Path) -> bool:
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

        df = pd.read_excel(detail_file)

        # 只保留母牛（排除公牛）
        df = df[df['sex'] == '母'].copy()

        # 定义年份分组
        def get_year_group(year):
            if pd.isna(year):
                return '未知'
            year = int(year)
            if year <= 2020:
                return '2020年及以前'
            elif year == 2021:
                return '2021'
            elif year == 2022:
                return '2022'
            elif year == 2023:
                return '2023'
            elif year >= 2024:
                return '2024'
            else:
                return '未知'

        df['birth_year_group'] = df['birth_year'].apply(get_year_group)

        # 按是否在场和年份分组统计
        result_list = []

        for status in ['是', '否', '总计']:
            if status == '总计':
                group_df = df
            else:
                group_df = df[df['是否在场'] == status]

            for year_group in ['2020年及以前', '2021', '2022', '2023', '2024']:
                year_df = group_df[group_df['birth_year_group'] == year_group]

                if len(year_df) == 0:
                    continue

                total_count = len(year_df)
                sire_count = year_df['sire_identified'].sum()
                mgs_count = year_df['mgs_identified'].sum()
                mmgs_count = year_df['mmgs_identified'].sum()

                sire_rate = sire_count / total_count if total_count > 0 else 0
                mgs_rate = mgs_count / total_count if total_count > 0 else 0
                mmgs_rate = mmgs_count / total_count if total_count > 0 else 0

                result_list.append({
                    '是否在场': status,
                    'birth_year_group': year_group,
                    '头数': total_count,
                    '父号可识别头数': int(sire_count),
                    '父号识别率': f'{sire_rate:.2%}',
                    '外祖父可识别头数': int(mgs_count),
                    '外祖父识别率': f'{mgs_rate:.2%}',
                    '外曾外祖父可识别头数': int(mmgs_count),
                    '外曾外祖父识别率': f'{mmgs_rate:.2%}'
                })

        # 创建结果DataFrame
        result_df = pd.DataFrame(result_list)

        # 按是否在场和年份排序
        status_order = {'是': 1, '否': 2, '总计': 3}
        year_order = {'2020年及以前': 1, '2021': 2, '2022': 3, '2023': 4, '2024': 5}

        result_df['status_sort'] = result_df['是否在场'].map(status_order)
        result_df['year_sort'] = result_df['birth_year_group'].map(year_order)
        result_df = result_df.sort_values(['status_sort', 'year_sort'])
        result_df = result_df.drop(['status_sort', 'year_sort'], axis=1)

        # 保存结果
        output_file = project_path / "analysis_results" / "系谱识别分析结果.xlsx"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        result_df.to_excel(output_file, index=False)

        logger.info(f"✓ 系谱识别分析结果已保存: {output_file}")
        logger.info(f"  - 总头数: {len(df)}头")
        logger.info(f"  - 在场母牛: {len(df[df['是否在场'] == '是'])}头")
        logger.info(f"  - 离场母牛: {len(df[df['是否在场'] == '否'])}头")

        return True

    except Exception as e:
        logger.error(f"生成系谱识别分析结果失败: {e}", exc_info=True)
        return False
