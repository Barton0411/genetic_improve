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

        # 处理 sex 字段：空值默认为 '母'
        if 'sex' in df.columns:
            df['sex'] = df['sex'].fillna('母')

        # 只保留母牛（排除公牛）
        df = df[df['sex'] == '母'].copy()

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

        # 按是否在场和年份分组统计
        result_list = []

        for status in ['是', '否', '总计']:
            if status == '总计':
                group_df = df
            else:
                group_df = df[df['是否在场'] == status]

            # 使用动态生成的年份标签
            for year_group in labels:
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
        # 动态创建年份排序映射
        year_order = {year_label: i+1 for i, year_label in enumerate(labels)}

        result_df['status_sort'] = result_df['是否在场'].map(status_order)
        result_df['year_sort'] = result_df['birth_year_group'].map(year_order)
        result_df = result_df.sort_values(['status_sort', 'year_sort'])
        result_df = result_df.drop(['status_sort', 'year_sort'], axis=1)

        # 保存结果
        output_file = project_path / "analysis_results" / "系谱识别分析结果.xlsx"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 确保cow_id保持为字符串格式
        if 'cow_id' in result_df.columns:
            result_df['cow_id'] = result_df['cow_id'].astype(str)

        result_df.to_excel(output_file, index=False)

        logger.info(f"✓ 系谱识别分析结果已保存: {output_file}")
        logger.info(f"  - 总头数: {len(df)}头")
        logger.info(f"  - 在场母牛: {len(df[df['是否在场'] == '是'])}头")
        logger.info(f"  - 离场母牛: {len(df[df['是否在场'] == '否'])}头")

        return True

    except Exception as e:
        logger.error(f"生成系谱识别分析结果失败: {e}", exc_info=True)
        return False
