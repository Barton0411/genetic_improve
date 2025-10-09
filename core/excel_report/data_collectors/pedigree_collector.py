"""
系谱识别分析数据收集器
收集Sheet 2所需的所有数据
"""

from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def collect_pedigree_data(analysis_folder: Path) -> dict:
    """
    收集系谱识别分析数据

    Args:
        analysis_folder: 分析结果文件夹路径

    Returns:
        数据字典包含:
        {
            'summary': 汇总数据DataFrame (按出生年份),
            'detail': 明细数据DataFrame,
            'total_stats': 总体统计 {
                'total_count': 总头数,
                'sire_identified': 父号可识别头数,
                'sire_rate': 父号识别率,
                'mgs_identified': 外祖父可识别头数,
                'mgs_rate': 外祖父识别率,
                'mggs_identified': 外曾外祖父可识别头数,
                'mggs_rate': 外曾外祖父识别率
            }
        }
    """
    logger.info("收集系谱识别分析数据...")

    # 查找系谱识别分析结果文件（汇总数据）
    pedigree_file = None
    for pattern in ['系谱识别分析结果.xlsx', '结果-系谱识别情况分析.xlsx']:
        found_files = list(analysis_folder.glob(pattern))
        if found_files:
            pedigree_file = found_files[0]
            break

    if not pedigree_file or not pedigree_file.exists():
        logger.warning(f"系谱识别分析结果文件不存在: {analysis_folder}")
        return {
            'summary': pd.DataFrame(),
            'detail': pd.DataFrame(),
            'total_stats': {}
        }

    # 查找原始明细数据文件（用于饼图统计和明细表）
    # 文件可能在 analysis_results 或 分析结果 文件夹
    detail_file = None
    for folder_name in ['analysis_results', '分析结果']:
        possible_path = analysis_folder.parent / folder_name / 'processed_cow_data_key_traits_detail.xlsx'
        if possible_path.exists():
            detail_file = possible_path
            break

    if detail_file is None:
        logger.warning(f"原始明细数据文件不存在，查找路径: {analysis_folder}")
        return {
            'summary': pd.DataFrame(),
            'detail': pd.DataFrame(),
            'total_stats': {}
        }

    try:
        # 读取汇总数据文件
        summary_source_df = pd.read_excel(pedigree_file, sheet_name=0)

        if summary_source_df.empty:
            logger.warning("系谱识别分析结果文件为空")
            return {
                'summary': pd.DataFrame(),
                'detail': pd.DataFrame(),
                'total_stats': {}
            }

        # 读取原始明细数据文件
        detail_source_df = pd.read_excel(detail_file)
        # 只保留母牛
        detail_source_df = detail_source_df[detail_source_df['sex'] == '母'].copy()

        # 处理汇总数据（按出生年份）- 只显示在群母牛
        summary_df = summary_source_df[summary_source_df['是否在场'] == '是'].copy()

        # 重命名列
        summary_df = summary_df.rename(columns={
            'birth_year_group': '出生年份',
            '头数': '总头数',
            '父号可识别头数': '可识别父号牛数',
            '父号识别率': '可识别父号占比',
            '外祖父可识别头数': '可识别外祖父牛数',
            '外祖父识别率': '可识别外祖父占比',
            '外曾外祖父可识别头数': '可识别外曾外祖父牛数',
            '外曾外祖父识别率': '可识别外曾外祖父占比'
        })

        # 选择需要的列
        summary_df = summary_df[[
            '出生年份', '总头数',
            '可识别父号牛数', '可识别父号占比',
            '可识别外祖父牛数', '可识别外祖父占比',
            '可识别外曾外祖父牛数', '可识别外曾外祖父占比'
        ]]

        # 计算合计行
        total_count = summary_df['总头数'].sum()
        sire_identified = summary_df['可识别父号牛数'].sum()
        mgs_identified = summary_df['可识别外祖父牛数'].sum()
        mggs_identified = summary_df['可识别外曾外祖父牛数'].sum()

        sire_rate = round(sire_identified / total_count * 100, 1) if total_count > 0 else 0
        mgs_rate = round(mgs_identified / total_count * 100, 1) if total_count > 0 else 0
        mggs_rate = round(mggs_identified / total_count * 100, 1) if total_count > 0 else 0

        # 添加合计行
        total_row = pd.DataFrame([{
            '出生年份': '合计',
            '总头数': total_count,
            '可识别父号牛数': sire_identified,
            '可识别父号占比': f'{sire_rate}%',
            '可识别外祖父牛数': mgs_identified,
            '可识别外祖父占比': f'{mgs_rate}%',
            '可识别外曾外祖父牛数': mggs_identified,
            '可识别外曾外祖父占比': f'{mggs_rate}%'
        }])

        summary_df = pd.concat([summary_df, total_row], ignore_index=True)

        # 总体统计（用于饼图）- 从原始明细数据统计在群母牛
        active_detail = detail_source_df[detail_source_df['是否在场'] == '是'].copy()
        active_total = len(active_detail)

        # 统计识别情况（使用布尔列）
        active_sire = active_detail['sire_identified'].sum() if 'sire_identified' in active_detail.columns else 0
        active_mgs = active_detail['mgs_identified'].sum() if 'mgs_identified' in active_detail.columns else 0
        active_mggs = active_detail['mmgs_identified'].sum() if 'mmgs_identified' in active_detail.columns else 0

        total_stats = {
            'total_count': active_total,
            'sire_identified': int(active_sire),
            'sire_unidentified': int(active_total - active_sire),
            'sire_rate': round(active_sire / active_total * 100, 1) if active_total > 0 else 0,
            'mgs_identified': int(active_mgs),
            'mgs_unidentified': int(active_total - active_mgs),
            'mgs_rate': round(active_mgs / active_total * 100, 1) if active_total > 0 else 0,
            'mggs_identified': int(active_mggs),
            'mggs_unidentified': int(active_total - active_mggs),
            'mggs_rate': round(active_mggs / active_total * 100, 1) if active_total > 0 else 0
        }

        logger.info(f"✓ 系谱识别数据收集完成: {total_count}头牛（在群: {active_total}头）")

        # 分离在群和全群明细数据
        detail_active = detail_source_df[detail_source_df['是否在场'] == '是'].copy()  # 在群母牛
        detail_all = detail_source_df.copy()  # 全群母牛（已在前面过滤了只保留母牛）

        return {
            'summary': summary_df,
            'detail_active': detail_active,  # 在群母牛明细
            'detail_all': detail_all,  # 全群母牛明细
            'total_stats': total_stats
        }

    except Exception as e:
        logger.error(f"读取系谱识别分析结果失败: {e}", exc_info=True)
        return {
            'summary': pd.DataFrame(),
            'detail': pd.DataFrame(),
            'total_stats': {}
        }
