"""
牧场基础信息数据收集器
收集Sheet 1所需的所有数据
"""

from pathlib import Path
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def collect_farm_info(project_folder: Path, service_staff: str = None) -> dict:
    """
    收集牧场基础信息

    Args:
        project_folder: 项目文件夹路径
        service_staff: 牧场服务人员（工号 姓名）

    Returns:
        数据字典，包含：
        - basic_info: 基本信息
        - herd_structure: 牛群结构统计
        - upload_summary: 上传数据概览
        - raw_cow_data: 原始母牛数据（未标准化）
    """
    project_folder = Path(project_folder)

    try:
        logger.info("收集牧场基础信息...")

        # 1. 基本信息
        basic_info = _collect_basic_info(project_folder, service_staff)

        # 2. 牛群结构统计
        herd_structure = _collect_herd_structure(project_folder)

        # 3. 上传数据概览
        upload_summary = _collect_upload_summary(project_folder)

        # 4. 原始母牛数据（用于Sheet 1A）
        raw_cow_data = _collect_raw_cow_data(project_folder)

        logger.info("✓ 牧场基础信息收集完成")

        return {
            'basic_info': basic_info,
            'herd_structure': herd_structure,
            'upload_summary': upload_summary,
            'raw_cow_data': raw_cow_data
        }

    except Exception as e:
        logger.error(f"收集牧场基础信息失败: {e}", exc_info=True)
        return {
            'basic_info': {},
            'herd_structure': {},
            'upload_summary': {},
            'raw_cow_data': None
        }


def _collect_basic_info(project_folder: Path, service_staff: str = None) -> dict:
    """
    收集基本信息

    Returns:
        {
            'farm_name': str,
            'report_time': str,
            'service_staff': str
        }
    """
    # 牧场名称（从项目文件夹名称获取，去掉日期后缀）
    # 例如: "ll_2025_10_06_17_13" -> "ll"
    raw_name = project_folder.name
    # 尝试分割，取第一部分（假设用下划线或其他分隔符分隔牧场名和日期）
    farm_name = raw_name.split('_')[0] if '_' in raw_name else raw_name

    # 报告生成时间
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 牧场服务人员
    if not service_staff:
        service_staff = "未指定"

    return {
        'farm_name': farm_name,
        'report_time': report_time,
        'service_staff': service_staff
    }


def _collect_herd_structure(project_folder: Path) -> dict:
    """
    收集牛群结构统计

    Returns:
        {
            'total_count': int,
            'lactating_count': int,
            'heifer_count': int,
            'other_count': int,
            'avg_lactation': float,
            'avg_dim': float,  # 平均泌乳天数
            'lactation_distribution': {...},
            'cow_data': DataFrame  # 原始母牛数据
        }
    """
    # 读取母牛数据
    cow_data_path = project_folder / "standardized_data" / "processed_cow_data.xlsx"

    if not cow_data_path.exists():
        logger.warning(f"母牛数据文件不存在: {cow_data_path}")
        return _get_empty_herd_structure()

    try:
        df = pd.read_excel(cow_data_path)

        # 确保sex列正确填充（处理全NaN的情况，母牛数据默认为'母'）
        if 'sex' in df.columns:
            if df['sex'].isna().all():
                df['sex'] = '母'
            else:
                df['sex'] = df['sex'].fillna('母')

        # 筛选在场母牛（同时筛选性别和是否在场）
        if '是否在场' in df.columns and 'sex' in df.columns:
            df_active = df[(df['是否在场'] == '是') & (df['sex'] == '母')].copy()
        elif '是否在场' in df.columns:
            df_active = df[df['是否在场'] == '是'].copy()
        else:
            df_active = df.copy()

        # 总牛头数
        total_count = len(df_active)

        # 按胎次统计
        if 'lac' in df_active.columns:
            # 成母牛（胎次>0）
            lactating_count = len(df_active[df_active['lac'] > 0])
            # 后备牛（胎次=0）
            heifer_count = len(df_active[df_active['lac'] == 0])
            # 其他
            other_count = total_count - lactating_count - heifer_count

            # 平均胎次（在群母牛）
            avg_lactation = df_active['lac'].mean()

            # 按胎次分布
            lac_0 = len(df_active[df_active['lac'] == 0])
            lac_1 = len(df_active[df_active['lac'] == 1])
            lac_2 = len(df_active[df_active['lac'] == 2])
            lac_3_plus = len(df_active[df_active['lac'] >= 3])

            lactation_distribution = {
                '0胎': lac_0,
                '1胎': lac_1,
                '2胎': lac_2,
                '3胎及以上': lac_3_plus
            }
        else:
            lactating_count = 0
            heifer_count = 0
            other_count = total_count
            avg_lactation = 0
            lactation_distribution = {}

        # 平均泌乳天数（在群母牛，只统计成母牛）
        avg_dim = 0
        dim_col = None
        # 查找泌乳天数列（可能是'DIM'或'dim'）
        if 'DIM' in df_active.columns:
            dim_col = 'DIM'
        elif 'dim' in df_active.columns:
            dim_col = 'dim'

        if dim_col and lactating_count > 0:
            # 只计算成母牛的泌乳天数
            lactating_cows = df_active[df_active['lac'] > 0]
            avg_dim = lactating_cows[dim_col].mean()

        return {
            'total_count': total_count,
            'lactating_count': lactating_count,
            'heifer_count': heifer_count,
            'other_count': other_count,
            'avg_lactation': round(avg_lactation, 2) if avg_lactation else 0,
            'avg_dim': round(avg_dim, 0) if avg_dim else 0,  # 平均泌乳天数取整
            'lactation_distribution': lactation_distribution,
            'cow_data': df_active
        }

    except Exception as e:
        logger.error(f"读取母牛数据失败: {e}", exc_info=True)
        return _get_empty_herd_structure()


def _collect_upload_summary(project_folder: Path) -> dict:
    """
    收集上传数据概览

    Returns:
        {
            'cow_data_count': int,
            'cow_data_active': int,
            'cow_data_inactive': int,
            'breeding_records': int,
            'bull_count': int,
            'body_conformation_count': int,
            'genomic_count': int,
            'last_update_time': str
        }
    """
    standardized_folder = project_folder / "standardized_data"
    upload_folder = project_folder / "上传数据"

    summary = {
        'cow_data_count': 0,
        'cow_data_active': 0,
        'cow_data_inactive': 0,
        'breeding_records': 0,
        'bull_count': 0,
        'body_conformation_count': 0,
        'genomic_count': 0,
        'last_update_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        # 1. 母牛信息数据
        cow_data_path = standardized_folder / "processed_cow_data.xlsx"
        if cow_data_path.exists():
            df_cow = pd.read_excel(cow_data_path)
            summary['cow_data_count'] = len(df_cow)

            if '是否在场' in df_cow.columns:
                # 区分公母
                if 'sex' in df_cow.columns:
                    # 在场母牛
                    active_female = len(df_cow[(df_cow['是否在场'] == '是') & (df_cow['sex'].isin(['F', 'f', '母', 'female', 'Female']))])
                    # 在场公牛
                    active_male = len(df_cow[(df_cow['是否在场'] == '是') & (df_cow['sex'].isin(['M', 'm', '公', 'male', 'Male']))])
                    # 离场母牛
                    inactive_female = len(df_cow[(df_cow['是否在场'] != '是') & (df_cow['sex'].isin(['F', 'f', '母', 'female', 'Female']))])
                    # 离场公牛
                    inactive_male = len(df_cow[(df_cow['是否在场'] != '是') & (df_cow['sex'].isin(['M', 'm', '公', 'male', 'Male']))])

                    summary['cow_data_active'] = active_female + active_male
                    summary['cow_data_inactive'] = inactive_female + inactive_male
                    summary['cow_data_detail'] = f"在场: 母{active_female}头, 公{active_male}头; 离场: 母{inactive_female}头, 公{inactive_male}头"
                else:
                    # 没有性别字段，使用原来的统计方式
                    summary['cow_data_active'] = len(df_cow[df_cow['是否在场'] == '是'])
                    summary['cow_data_inactive'] = len(df_cow[df_cow['是否在场'] != '是'])
                    summary['cow_data_detail'] = f"在场: {summary['cow_data_active']}头, 离场: {summary['cow_data_inactive']}头"

        # 2. 配种记录
        breeding_path = standardized_folder / "processed_breeding_data.xlsx"
        if breeding_path.exists():
            df_breeding = pd.read_excel(breeding_path)
            summary['breeding_records'] = len(df_breeding)

        # 3. 备选公牛数据
        bull_path = standardized_folder / "processed_bull_data.xlsx"
        if bull_path.exists():
            df_bull = pd.read_excel(bull_path)
            summary['bull_count'] = len(df_bull)

        # 4. 体型外貌数据
        body_path = standardized_folder / "processed_body_conformation_data.xlsx"
        if body_path.exists():
            df_body = pd.read_excel(body_path)
            summary['body_conformation_count'] = len(df_body)

        # 5. 基因组数据
        genomic_path = standardized_folder / "processed_genomic_data.xlsx"
        if genomic_path.exists():
            df_genomic = pd.read_excel(genomic_path)
            summary['genomic_count'] = len(df_genomic)

    except Exception as e:
        logger.error(f"收集上传数据概览失败: {e}", exc_info=True)

    return summary


def _get_empty_herd_structure() -> dict:
    """返回空的牛群结构数据"""
    return {
        'total_count': 0,
        'lactating_count': 0,
        'heifer_count': 0,
        'other_count': 0,
        'avg_lactation': 0,
        'avg_dim': 0,
        'lactation_distribution': {},
        'cow_data': pd.DataFrame()
    }


def _collect_raw_cow_data(project_folder: Path) -> Path:
    """
    获取原始母牛数据文件路径

    Args:
        project_folder: 项目文件夹路径

    Returns:
        原始母牛数据文件路径（Path对象），如果不存在则返回None
    """
    # 尝试从raw_data文件夹读取
    raw_data_path = project_folder / "raw_data" / "cow_data.xlsx"

    if raw_data_path.exists():
        logger.info(f"找到原始母牛数据文件: {raw_data_path}")
        return raw_data_path
    else:
        logger.warning(f"原始母牛数据文件不存在: {raw_data_path}")
        return None
