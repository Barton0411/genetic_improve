"""
自动分析运行器 - 无GUI依赖

提供所有数据分析的纯函数封装，供 AutoReportWorker 在后台线程中调用。
"""

import sqlite3
import logging
import datetime
import math
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

import pandas as pd

from core.data.update_manager import LOCAL_DB_PATH
from core.inbreeding.analysis_scope import (
    ORIGINAL_BULL_ID_COLUMN,
    STANDARDIZED_BULL_ID_COLUMN,
    build_inbreeding_analysis_scope,
)

logger = logging.getLogger(__name__)


class ProjectPathProxy:
    """模拟 main_window，提供 selected_project_path 和 username 属性"""
    def __init__(self, project_path):
        self.selected_project_path = Path(project_path)
        self.username = "auto_report"


# 默认性状列表和权重
DEFAULT_TRAITS = [
    'NM$', 'TPI', 'MILK', 'FAT', 'FAT %', 'PROT', 'PROT%',
    'SCS', 'PL', 'DPR', 'PTAT', 'UDC', 'FLC', 'RFI'
]

DEFAULT_WEIGHT = "NM$权重"

# 隐性基因列表
DEFECT_GENES = [
    "HH1", "HH2", "HH3", "HH4", "HH5", "HH6",
    "BLAD", "Chondrodysplasia", "Citrullinemia",
    "DUMPS", "Factor XI", "CVM", "Brachyspina",
    "Mulefoot", "Cholesterol deficiency", "MW"
]


# ============ 母牛性状分析 ============

def run_cow_traits(project_path, selected_traits=None, progress_cb=None):
    """
    母牛性状分析 - 复用 TraitsCalculation.process_data()
    """
    from core.breeding_calc.traits_calculation import TraitsCalculation
    calc = TraitsCalculation()
    proxy = ProjectPathProxy(project_path)
    traits = selected_traits or DEFAULT_TRAITS
    return calc.process_data(proxy, traits, progress_cb)


# ============ 备选公牛性状分析 ============

def run_bull_traits(
    project_path,
    selected_traits=None,
    progress_cb=None,
    *,
    allow_missing_bull_upload=True,
):
    """
    备选公牛性状分析 - 无GUI版本
    从 processed_bull_data.xlsx 读取公牛ID，逐个查询本地数据库获取性状数据
    """
    traits = selected_traits or DEFAULT_TRAITS
    project_path = Path(project_path)

    # 检查输入文件
    bull_data_path = project_path / "standardized_data" / "processed_bull_data.xlsx"
    if not bull_data_path.exists():
        return False, "未找到备选公牛数据文件"

    try:
        bull_df = pd.read_excel(bull_data_path)
    except Exception as e:
        return False, f"读取备选公牛数据文件失败：{str(e)}"

    # 检查数据库
    import os
    if not os.path.exists(LOCAL_DB_PATH):
        from core.data.bull_library_downloader import ensure_bull_library_exists
        if not ensure_bull_library_exists(LOCAL_DB_PATH):
            return False, "无法下载公牛数据库"

    # 查询每个公牛的性状数据
    missing_bulls = []
    trait_data = []

    for idx, row in bull_df.iterrows():
        bull_id = str(row['bull_id'])
        if pd.isna(bull_id) or bull_id.strip() == '':
            continue

        try:
            conn = sqlite3.connect(LOCAL_DB_PATH)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM bull_library WHERE `BULL NAAB`=?",
                    (bull_id,)
                )
                result = cursor.fetchone()

                if not result:
                    cursor.execute(
                        "SELECT * FROM bull_library WHERE `BULL REG`=?",
                        (bull_id,)
                    )
                    result = cursor.fetchone()

                if result:
                    column_names = [desc[0] for desc in cursor.description]
                    result_dict = dict(zip(column_names, result))
                    bull_data = dict(row)
                    for trait in traits:
                        bull_data[trait] = result_dict.get(trait)
                    trait_data.append(bull_data)
                else:
                    missing_bulls.append(bull_id)
                    bull_data = dict(row)
                    for trait in traits:
                        bull_data[trait] = None
                    trait_data.append(bull_data)
            finally:
                conn.close()
        except Exception as e:
            logger.warning(f"查询公牛 {bull_id} 失败: {e}")
            bull_data = dict(row)
            for trait in traits:
                bull_data[trait] = None
            trait_data.append(bull_data)

    # 上传缺失公牛（静默处理）
    if missing_bulls and allow_missing_bull_upload:
        _upload_missing_bulls(missing_bulls, 'bull_key_traits')

    # 保存结果
    result_df = pd.DataFrame(trait_data)
    output_dir = project_path / "analysis_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "processed_bull_data_key_traits.xlsx"

    try:
        result_df.to_excel(output_path, index=False)
        return True, f"备选公牛性状分析完成，{len(missing_bulls)} 个公牛未在数据库中找到"
    except Exception as e:
        return False, f"保存结果失败: {e}"


# ============ 已配公牛性状分析 ============

def run_mated_bull_traits(project_path, selected_traits=None, progress_cb=None):
    """
    已配公牛性状分析 - 无GUI版本
    从配种记录中提取公牛ID，批量查询数据库后merge
    """
    traits = selected_traits or DEFAULT_TRAITS
    project_path = Path(project_path)

    # 读取配种记录
    breeding_data_path = project_path / "standardized_data" / "processed_breeding_data.xlsx"
    if not breeding_data_path.exists():
        return False, "未找到配种记录文件"

    try:
        breeding_df = pd.read_excel(breeding_data_path, dtype={'耳号': str, '父号': str, '冻精编号': str})
        from core.data.processor import add_farm_lineage_columns
        breeding_df = add_farm_lineage_columns(
            breeding_df, project_path, animal_id_column='耳号'
        )
        breeding_df['配种年份'] = pd.to_datetime(breeding_df['配种日期']).dt.year
    except Exception as e:
        return False, f"读取配种记录失败：{str(e)}"

    # 按ID长度分组
    short_ids = breeding_df[breeding_df['冻精编号'].str.len() <= 10]['冻精编号'].unique()
    long_ids = breeding_df[breeding_df['冻精编号'].str.len() > 10]['冻精编号'].unique()

    # 检查数据库
    import os
    if not os.path.exists(LOCAL_DB_PATH):
        from core.data.bull_library_downloader import ensure_bull_library_exists
        if not ensure_bull_library_exists(LOCAL_DB_PATH):
            return False, "无法下载公牛数据库"

    conn = sqlite3.connect(LOCAL_DB_PATH)
    try:
        traits_data = []

        # 查询短ID公牛
        if len(short_ids) > 0:
            placeholders = ','.join(['?' for _ in short_ids])
            naab_query = f"""SELECT `BULL NAAB` as bull_id, {
                ','.join(f'`{trait}`' for trait in traits)
            } FROM bull_library WHERE `BULL NAAB` IN ({placeholders})"""
            naab_df = pd.read_sql(naab_query, conn, params=list(short_ids))
            traits_data.append(naab_df)

        # 查询长ID公牛
        if len(long_ids) > 0:
            placeholders = ','.join(['?' for _ in long_ids])
            reg_query = f"""SELECT `BULL REG` as bull_id, {
                ','.join(f'`{trait}`' for trait in traits)
            } FROM bull_library WHERE `BULL REG` IN ({placeholders})"""
            reg_df = pd.read_sql(reg_query, conn, params=list(long_ids))
            traits_data.append(reg_df)

        if traits_data:
            bull_traits_df = pd.concat(traits_data, ignore_index=True)
        else:
            bull_traits_df = pd.DataFrame(columns=['bull_id'] + traits)
    finally:
        conn.close()

    # merge
    result_df = pd.merge(
        breeding_df,
        bull_traits_df,
        left_on='冻精编号',
        right_on='bull_id',
        how='left'
    ).drop('bull_id', axis=1)

    # 保存结果
    output_dir = project_path / "analysis_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "processed_mated_bull_traits.xlsx"

    try:
        result_df.to_excel(output_path, index=False)
        return True, "已配公牛性状分析完成"
    except Exception as e:
        return False, f"保存结果失败: {e}"


# ============ 母牛指数排名 ============

def run_cow_index(
    project_path,
    weight_name=None,
    progress_cb=None,
    *,
    weight_values=None,
):
    """
    母牛指数排名 - 复用 IndexCalculation.process_cow_index()
    """
    from core.breeding_calc.index_calculation import IndexCalculation
    calc = IndexCalculation()
    proxy = ProjectPathProxy(project_path)
    weight = weight_name or DEFAULT_WEIGHT
    return calc.process_cow_index(
        proxy,
        weight,
        progress_cb,
        weight_values=weight_values,
    )


# ============ 备选公牛指数排名 ============

def run_bull_index(
    project_path,
    weight_name=None,
    progress_cb=None,
    *,
    weight_values=None,
    allow_missing_bull_upload=True,
):
    """
    备选公牛指数排名 - 复用 IndexCalculation.process_bull_index()
    """
    from core.breeding_calc.index_calculation import IndexCalculation
    calc = IndexCalculation()
    proxy = ProjectPathProxy(project_path)
    weight = weight_name or DEFAULT_WEIGHT
    return calc.process_bull_index(
        proxy,
        weight,
        progress_cb,
        weight_values=weight_values,
        allow_missing_bull_upload=allow_missing_bull_upload,
    )


# ============ 近交分析 ============

COW_SELF_INBREEDING_FILENAME = "母牛近交系数分析结果.xlsx"


def run_cow_self_inbreeding_analysis(
    project_path,
    progress_cb=None,
):
    """在无 GUI 环境中执行母牛自身近交及父系隐性基因分析。

    计算口径与 ``InbreedingPage.analyze_cow_self`` 保持一致：
    母牛自身近交系数按其父号与母号的潜在后代近交系数计算；隐性
    基因状态取母牛父系公牛记录。结果使用 UI 手工分析相同的固定
    文件名，便于子项目完成后直接打开。
    """
    project_path = Path(project_path)

    def emit_progress(pct, msg):
        if progress_cb:
            try:
                progress_cb(pct, msg)
            except Exception:
                pass
        logger.info("[母牛近交分析] %s%% - %s", pct, msg)

    try:
        cow_file = (
            project_path
            / "standardized_data"
            / "processed_cow_data.xlsx"
        )
        if not cow_file.is_file():
            return False, "未找到母牛数据文件"

        emit_progress(5, "读取母牛数据...")
        from config.breed_constants import filter_dairy_cows
        from core.data.processor import add_farm_lineage_columns
        from core.data.update_manager import get_pedigree_db
        from core.inbreeding.path_inbreeding_calculator import (
            PathInbreedingCalculator,
        )
        from utils.large_excel_writer import (
            normalize_identifier_key,
            read_excel_identifier_safe,
        )

        cow_df = read_excel_identifier_safe(cow_file)
        cow_df = add_farm_lineage_columns(
            cow_df,
            project_path,
            animal_id_column="cow_id",
        )
        cow_df = filter_dairy_cows(
            cow_df,
            log_prefix="母牛近交分析：",
        )

        emit_progress(10, "构建母牛系谱库...")
        pedigree_db = get_pedigree_db()

        def pedigree_progress(value, message):
            try:
                mapped = 10 + int(float(value) * 0.15)
            except (TypeError, ValueError):
                mapped = 10
            emit_progress(max(10, min(mapped, 25)), message)

        pedigree_db.build_cow_pedigree(
            cow_file,
            pedigree_progress,
        )
        calculator = PathInbreedingCalculator(max_generations=6)
        emit_progress(25, "母牛系谱库构建完成")

        columns = list(cow_df.columns)
        rows_cache = []
        sire_ids = set()
        for row in cow_df.itertuples(index=False, name=None):
            row_dict = dict(zip(columns, row))
            cow_id = normalize_identifier_key(
                row_dict.get("cow_id", "")
            )
            if not cow_id:
                continue

            original_sire = normalize_identifier_key(
                row_dict.get("sire", "")
            )
            sire_id = (
                normalize_identifier_key(
                    pedigree_db.standardize_animal_id(
                        original_sire,
                        "bull",
                    )
                )
                if original_sire
                else ""
            )
            if sire_id:
                sire_ids.add(sire_id)

            standardized_cow_id = normalize_identifier_key(
                pedigree_db.standardize_animal_id(cow_id, "cow")
            )
            cow_info = calculator.pedigree_db.pedigree.get(
                standardized_cow_id or cow_id,
                {},
            )
            dam_id = normalize_identifier_key(
                cow_info.get("dam", "")
            )
            if not dam_id:
                original_dam = normalize_identifier_key(
                    row_dict.get("dam", "")
                )
                dam_id = (
                    normalize_identifier_key(
                        pedigree_db.standardize_animal_id(
                            original_dam,
                            "cow",
                        )
                    )
                    if original_dam
                    else ""
                )

            rows_cache.append(
                (
                    row_dict,
                    cow_id,
                    original_sire,
                    sire_id,
                    dam_id,
                )
            )

        emit_progress(35, "查询母牛父系隐性基因...")
        sire_genes_map, _ = _query_bull_genes(sire_ids)
        results = []
        total = len(rows_cache)

        for index, (
            row_dict,
            cow_id,
            original_sire,
            sire_id,
            dam_id,
        ) in enumerate(rows_cache):
            if index % 50 == 0:
                progress = (
                    40 + int(index / total * 45)
                    if total
                    else 85
                )
                emit_progress(
                    progress,
                    f"计算母牛近交系数 ({index + 1}/{total})",
                )

            try:
                if sire_id and dam_id:
                    f_val, contrib, paths = (
                        calculator
                        .calculate_potential_offspring_inbreeding(
                            sire_id,
                            dam_id,
                        )
                    )
                    if math.isnan(f_val):
                        f_val = 0.0
                else:
                    f_val, contrib, paths = 0.0, {}, {}
            except Exception:
                logger.exception("计算一头母牛的自身近交系数失败")
                f_val, contrib, paths = 0.0, {}, {}

            result = {
                "牧场编号": row_dict.get("牧场编号", ""),
                "牧场名称": row_dict.get("牧场名称", ""),
                "母牛号": cow_id,
                "父号": sire_id,
                "原始父号": (
                    original_sire
                    if original_sire != sire_id
                    else ""
                ),
                "母号": dam_id,
                "出生日期": row_dict.get("birth_date", ""),
                "胎次": row_dict.get("lac", ""),
                "是否在场": row_dict.get("是否在场", ""),
                "近交系数": f"{f_val:.3%}",
                "近交详情": {
                    "system": f_val,
                    "common_ancestors": contrib,
                    "paths": paths,
                },
            }

            sire_genes = sire_genes_map.get(sire_id, {})
            for gene in DEFECT_GENES:
                gene_value = sire_genes.get(gene, "missing data")
                if gene_value == "missing data":
                    result[gene] = "缺少母牛父亲信息"
                elif gene_value == "C":
                    result[gene] = "仅母牛父亲携带"
                elif gene_value == "F":
                    result[gene] = "-"
                else:
                    result[gene] = gene_value
                result[f"{gene}(父)"] = gene_value

            results.append(result)

        emit_progress(90, "收集异常与统计...")
        abnormal_df, stats_df = _collect_cow_self_abnormal(results)
        results_df = pd.DataFrame(results)
        if results_df.empty:
            results_df = pd.DataFrame(
                columns=[
                    "牧场编号",
                    "牧场名称",
                    "母牛号",
                    "父号",
                    "原始父号",
                    "母号",
                    "出生日期",
                    "胎次",
                    "是否在场",
                    "近交系数",
                    "近交详情",
                    *DEFECT_GENES,
                    *(f"{gene}(父)" for gene in DEFECT_GENES),
                ]
            )

        output_dir = project_path / "analysis_results"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / COW_SELF_INBREEDING_FILENAME

        emit_progress(95, "保存母牛近交分析结果...")
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            results_df.to_excel(
                writer,
                sheet_name="配对明细表",
                index=False,
            )
            if not abnormal_df.empty:
                abnormal_df.to_excel(
                    writer,
                    sheet_name="异常明细表",
                    index=False,
                )
            if not stats_df.empty:
                stats_df.to_excel(
                    writer,
                    sheet_name="统计表",
                    index=False,
                )
            farm_stats_df = _build_farm_abnormal_stats(abnormal_df)
            if not farm_stats_df.empty:
                farm_stats_df.to_excel(
                    writer,
                    sheet_name="分牧场统计表",
                    index=False,
                )

        emit_progress(100, "母牛近交分析完成")
        return True, f"母牛近交分析完成，共 {len(results)} 头母牛"
    except Exception as exc:
        logger.exception("母牛近交分析失败: %s", exc)
        return False, f"母牛近交分析失败: {exc}"


def run_inbreeding_analysis(
    project_path,
    analysis_type,
    progress_cb=None,
    *,
    allow_missing_bull_upload=True,
):
    """
    近交系数及隐性基因分析 - 无GUI版本

    Args:
        project_path: 项目路径
        analysis_type: 'mated' 或 'candidate'
        progress_cb: 进度回调 (percent, message)
        allow_missing_bull_upload: 是否将数据库缺失公牛上报服务端。
            默认 True 保持现有自动分析行为；离线验收、重算和其它不得产生
            外部写入的调用方必须显式传 False。

    Returns:
        Tuple[bool, str]: (成功, 消息)
    """
    project_path = Path(project_path)

    def emit_progress(pct, msg):
        if progress_cb:
            try:
                progress_cb(pct, msg)
            except Exception:
                pass
        print(f"[近交分析] {pct}% - {msg}")

    try:
        # 1. 初始化数据库连接
        emit_progress(5, "初始化数据库连接...")
        db_conn = sqlite3.connect(LOCAL_DB_PATH)
        db_conn.row_factory = sqlite3.Row

        # 2. 构建母牛系谱库
        emit_progress(10, "构建母牛系谱库...")
        from core.data.update_manager import get_pedigree_db
        pedigree_db = get_pedigree_db()

        cow_file = project_path / "standardized_data" / "processed_cow_data.xlsx"
        if not cow_file.exists():
            return False, "未找到母牛数据文件"

        pedigree_db.build_cow_pedigree(cow_file)
        emit_progress(25, "母牛系谱库构建完成")

        # 3. 收集需要查询的公牛号
        emit_progress(30, "收集公牛号...")
        required_bulls, bull_sources = _collect_required_bulls(
            analysis_type, project_path, pedigree_db
        )
        emit_progress(35, f"收集到 {len(required_bulls)} 个公牛号")

        # 4. 查询公牛基因信息
        emit_progress(40, "查询公牛基因信息...")
        bull_genes, missing_bulls = _query_bull_genes(required_bulls)
        emit_progress(45, f"找到 {len(bull_genes)} 个公牛基因信息")

        # 5. 处理缺失公牛（静默上传）
        if missing_bulls and allow_missing_bull_upload:
            _upload_missing_bulls(missing_bulls, f'隐性基因筛查_{analysis_type}')

        # 6. 分析配对
        emit_progress(50, "分析配对...")
        if analysis_type == "mated":
            results = _analyze_mated_pairs(project_path, bull_genes, pedigree_db, progress_cb)
        else:
            results = _analyze_candidate_pairs(project_path, bull_genes, pedigree_db, progress_cb)
        emit_progress(70, f"配对分析完成，共 {len(results)} 条结果")

        # 7. 计算近交系数
        emit_progress(72, "计算近交系数...")
        results = _calculate_inbreeding_coefficients(results, progress_cb)
        emit_progress(88, "近交系数计算完成")

        # 8. 收集异常配对
        emit_progress(90, "收集异常配对...")
        abnormal_df, stats_df = _collect_abnormal_pairs(results)

        # 9. 保存结果
        emit_progress(95, "保存分析结果...")
        results_df = pd.DataFrame(results)
        # 移除不可序列化的详情字段
        for col in ['后代近交详情', '近交详情']:
            if col in results_df.columns:
                results_df = results_df.drop(columns=[col])

        output_dir = project_path / "analysis_results"
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if analysis_type == "mated":
            filename = f"已配公牛_近交系数及隐性基因分析结果_{timestamp}.xlsx"
        else:
            filename = f"备选公牛_近交系数及隐性基因分析结果_{timestamp}.xlsx"

        output_path = output_dir / filename

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            if not results_df.empty:
                results_df.to_excel(writer, sheet_name='配对明细表', index=False)
            if not abnormal_df.empty:
                abnormal_df.to_excel(writer, sheet_name='异常明细表', index=False)
            if not stats_df.empty:
                stats_df.to_excel(writer, sheet_name='统计表', index=False)
            farm_stats_df = _build_farm_abnormal_stats(abnormal_df)
            if not farm_stats_df.empty:
                farm_stats_df.to_excel(writer, sheet_name='分牧场统计表', index=False)

        emit_progress(100, "近交分析完成")
        db_conn.close()
        return True, f"{analysis_type}近交分析完成"

    except Exception as e:
        logger.exception(f"近交分析失败: {e}")
        return False, f"近交分析失败: {str(e)}"


# ============ 近交分析子方法 ============

def _collect_required_bulls(analysis_type, project_path, pedigree_db):
    """收集需要查询的公牛号并标准化为REG格式"""
    required_bulls = set()
    bull_sources = {}

    cow_file = project_path / "standardized_data" / "processed_cow_data.xlsx"
    cow_df = pd.read_excel(cow_file, dtype={'cow_id': str, 'sire': str})

    if analysis_type == 'mated':
        breeding_file = project_path / "standardized_data" / "processed_breeding_data.xlsx"
        breeding_df = pd.read_excel(
            breeding_file,
            dtype={'耳号': str, '父号': str, '冻精编号': str},
        )
        scope = build_inbreeding_analysis_scope(
            analysis_type,
            cow_df,
            breeding_df=breeding_df,
        )
    else:
        bull_file = project_path / "standardized_data" / "processed_bull_data.xlsx"
        bull_df = pd.read_excel(bull_file, dtype={'bull_id': str})
        scope = build_inbreeding_analysis_scope(
            analysis_type,
            cow_df,
            candidate_bull_df=bull_df,
            standardize_bull_id=lambda value: pedigree_db.standardize_animal_id(
                value, 'bull'
            ),
        )

    # 收集母牛父号
    sire_ids = scope.cows['sire'].dropna().astype(str).unique()
    for sire_id in sire_ids:
        if sire_id and sire_id.strip():
            standardized = pedigree_db.standardize_animal_id(sire_id, 'bull')
            if standardized:
                required_bulls.add(standardized)
                bull_sources[standardized] = 'sire'

    # 收集配种/备选公牛号
    if analysis_type == 'mated':
        bull_ids = (
            scope.breeding_records['冻精编号'].dropna().astype(str).unique()
        )
        for bull_id in bull_ids:
            if bull_id and bull_id.strip():
                standardized = pedigree_db.standardize_animal_id(bull_id, 'bull')
                if standardized:
                    required_bulls.add(standardized)
                    bull_sources[standardized] = 'breeding'
    else:
        for standardized in scope.candidate_bulls[STANDARDIZED_BULL_ID_COLUMN]:
            if standardized:
                required_bulls.add(standardized)
                bull_sources[standardized] = 'candidate'

    required_bulls = {b for b in required_bulls if b and b.strip()}
    return required_bulls, bull_sources


def _query_bull_genes(bull_ids):
    """查询公牛基因信息"""
    bull_genes = {}
    missing_bulls = []

    if not bull_ids:
        return bull_genes, missing_bulls

    valid_ids = {bid for bid in bull_ids if bid and not pd.isna(bid) and bid.strip()}
    if not valid_ids:
        return bull_genes, list(bull_ids)

    try:
        bull_ids_str = "', '".join(valid_ids)
        query = f"""
            SELECT `BULL NAAB`, `BULL REG`,
                HH1, HH2, HH3, HH4, HH5, HH6,
                BLAD, Chondrodysplasia, Citrullinemia,
                DUMPS, `Factor XI`, CVM, Brachyspina,
                Mulefoot, `Cholesterol deficiency`, MW
            FROM bull_library
            WHERE `BULL NAAB` IN ('{bull_ids_str}')
            OR `BULL REG` IN ('{bull_ids_str}')
        """

        conn = sqlite3.connect(LOCAL_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchall()

        found_bulls = set()
        for row in result:
            row_dict = dict(row)
            naab = row_dict.get('BULL NAAB')
            reg = row_dict.get('BULL REG')

            gene_data = {}
            for gene in DEFECT_GENES:
                value = row_dict.get(gene)
                if pd.isna(value) if not isinstance(value, str) else False:
                    gene_data[gene] = 'F'
                elif value is None:
                    gene_data[gene] = 'F'
                else:
                    value = str(value).strip().upper()
                    gene_data[gene] = value if value in ('C', 'F') else value

            if naab:
                bull_genes[str(naab)] = gene_data
                found_bulls.add(str(naab))
            if reg:
                bull_genes[str(reg)] = gene_data
                found_bulls.add(str(reg))

        missing_bulls = list(valid_ids - found_bulls)
        cursor.close()
        conn.close()

        return bull_genes, missing_bulls

    except Exception as e:
        logger.error(f"查询公牛基因信息失败: {e}")
        return {}, list(bull_ids)


def _analyze_gene_safety(cow_genes, bull_genes_data):
    """分析基因配对安全性"""
    result = {}
    for gene in DEFECT_GENES:
        mgs_gene = cow_genes.get(gene, 'missing data')
        bull_gene = bull_genes_data.get(gene, 'missing data')

        mgs_found = (mgs_gene != 'missing data')

        if bull_gene == 'missing data' and not mgs_found:
            result[gene] = '缺少双方信息'
        elif bull_gene == 'missing data':
            result[gene] = '缺少公牛信息'
        elif not mgs_found:
            result[gene] = '缺少母牛父亲信息'
        elif bull_gene == 'C' and mgs_gene == 'C':
            result[gene] = '高风险'
        elif bull_gene == 'C' and mgs_gene == 'F':
            result[gene] = '仅公牛携带'
        elif bull_gene == 'F' and mgs_gene == 'C':
            result[gene] = '仅母牛父亲携带'
        else:
            result[gene] = '-'

    return result


def _analyze_mated_pairs(project_path, bull_genes, pedigree_db, progress_cb=None):
    """分析已配公牛对"""
    results = []
    breeding_file = project_path / "standardized_data" / "processed_breeding_data.xlsx"
    df = pd.read_excel(breeding_file, dtype={'耳号': str, '父号': str, '冻精编号': str})
    from core.data.processor import add_farm_lineage_columns
    df = add_farm_lineage_columns(
        df, project_path, animal_id_column='耳号'
    )
    cow_file = project_path / "standardized_data" / "processed_cow_data.xlsx"
    cow_df = pd.read_excel(cow_file, dtype={'cow_id': str, 'sire': str})
    scope = build_inbreeding_analysis_scope(
        'mated',
        cow_df,
        breeding_df=df,
    )
    df = scope.breeding_records

    missing_gene_default = {gene: 'missing data' for gene in DEFECT_GENES}

    for i, (_, row) in enumerate(df.iterrows()):
        cow_id = str(row['耳号']).strip() if pd.notna(row['耳号']) else ''
        breeding_date = row['配种日期'] if '配种日期' in row and pd.notna(row['配种日期']) else ''

        original_sire_id = str(row['父号']) if pd.notna(row['父号']) else ''
        sire_id = pedigree_db.standardize_animal_id(original_sire_id, 'bull')

        original_bull_id = str(row['冻精编号']) if pd.notna(row['冻精编号']) else ''
        bull_id = pedigree_db.standardize_animal_id(original_bull_id, 'bull')

        sire_genes = bull_genes.get(sire_id, missing_gene_default)
        bull_genes_data = bull_genes.get(bull_id, missing_gene_default)

        gene_results = _analyze_gene_safety(sire_genes, bull_genes_data)

        result_dict = {
            '牧场编号': row.get('牧场编号', ''),
            '牧场名称': row.get('牧场名称', ''),
            '母牛号': cow_id,
            '配种日期': breeding_date,
            '父号': sire_id,
            '原始父号': original_sire_id if original_sire_id != sire_id else '',
            '配种公牛号': bull_id,
            '原始公牛号': original_bull_id if original_bull_id != bull_id else '',
            '近交系数': "0.00%",
        }

        for gene in DEFECT_GENES:
            result_dict[gene] = gene_results[gene]
            result_dict[f"{gene}(母)"] = sire_genes.get(gene, 'missing data')
            result_dict[f"{gene}(公)"] = bull_genes_data.get(gene, 'missing data')

        results.append(result_dict)

    return results


def _analyze_candidate_pairs(project_path, bull_genes, pedigree_db, progress_cb=None):
    """分析备选公牛对"""
    results = []
    cow_file = project_path / "standardized_data" / "processed_cow_data.xlsx"
    bull_file = project_path / "standardized_data" / "processed_bull_data.xlsx"

    cow_df = pd.read_excel(cow_file, dtype={'cow_id': str, 'sire': str})
    from core.data.processor import add_farm_lineage_columns
    cow_df = add_farm_lineage_columns(
        cow_df, project_path, animal_id_column='cow_id'
    )
    bull_df = pd.read_excel(bull_file, dtype={'bull_id': str})

    scope = build_inbreeding_analysis_scope(
        'candidate',
        cow_df,
        candidate_bull_df=bull_df,
        standardize_bull_id=lambda value: pedigree_db.standardize_animal_id(
            value, 'bull'
        ),
    )
    cow_df = scope.cows
    bull_df = scope.candidate_bulls
    missing_gene_default = {gene: 'missing data' for gene in DEFECT_GENES}

    for _, cow_row in cow_df.iterrows():
        cow_id = str(cow_row['cow_id'])
        original_sire_id = str(cow_row['sire']) if pd.notna(cow_row['sire']) else ''
        sire_id = pedigree_db.standardize_animal_id(original_sire_id, 'bull')
        cow_genes = bull_genes.get(sire_id, missing_gene_default)

        for _, bull_row in bull_df.iterrows():
            original_bull_id = str(bull_row[ORIGINAL_BULL_ID_COLUMN])
            bull_id_std = str(bull_row[STANDARDIZED_BULL_ID_COLUMN])
            candidate_genes = bull_genes.get(bull_id_std, missing_gene_default)

            gene_results = _analyze_gene_safety(cow_genes, candidate_genes)

            result_dict = {
                '牧场编号': cow_row.get('牧场编号', ''),
                '牧场名称': cow_row.get('牧场名称', ''),
                '母牛号': cow_id,
                '父号': sire_id,
                '原始父号': original_sire_id if original_sire_id != sire_id else '',
                '备选公牛号': bull_id_std,
                '原始备选公牛号': original_bull_id if original_bull_id != bull_id_std else '',
                '近交系数': "0.00%",
            }

            for gene in DEFECT_GENES:
                result_dict[gene] = gene_results[gene]
                result_dict[f"{gene}(母)"] = cow_genes.get(gene, 'missing data')
                result_dict[f"{gene}(公)"] = candidate_genes.get(gene, 'missing data')

            results.append(result_dict)

    return results


def _calculate_inbreeding_coefficients(results, progress_cb=None):
    """计算近交系数并更新结果"""
    try:
        from core.inbreeding.path_inbreeding_calculator import PathInbreedingCalculator
        calculator = PathInbreedingCalculator(max_generations=6)

        total_count = len(results)
        for i, result in enumerate(results):
            cow_id = result['母牛号']
            sire_id = result['父号']
            bull_id = result.get('配种公牛号', result.get('备选公牛号', ''))

            if bull_id:
                try:
                    offspring_inbreeding, offspring_contributions, offspring_paths = \
                        calculator.calculate_potential_offspring_inbreeding(bull_id, cow_id)

                    if math.isnan(offspring_inbreeding):
                        offspring_inbreeding = 0.0

                    # 父女配兜底：母牛 cow_id 在 pedigree 中查不到时，通径法会返回 0；
                    # 但上层 result 里"父号"已经标准化好，若与配种公牛号一致，至少保证不漏报 0.25 这个直系血亲场景
                    if offspring_inbreeding == 0.0 and sire_id and sire_id == bull_id:
                        bull_f, _, _ = calculator.calculate_inbreeding_coefficient(bull_id)
                        offspring_inbreeding = 0.25 * (1 + bull_f)
                        offspring_contributions = {bull_id: offspring_inbreeding}
                        offspring_paths = {bull_id: [(f"{bull_id} → 后代 ← {cow_id} ← {bull_id}", offspring_inbreeding, 0, 1, bull_f)]}

                    # 保留到0.001个百分点，避免6.25%阈值附近因显示值
                    # 过早四舍五入而改变后续选配判断。
                    result['后代近交系数'] = f"{offspring_inbreeding:.3%}"
                    result['后代近交详情'] = {
                        'system': offspring_inbreeding,
                        'common_ancestors': offspring_contributions,
                        'paths': offspring_paths
                    }
                except Exception as e:
                    result['后代近交系数'] = "0.00%"
                    result['后代近交详情'] = {'system': 0.0, 'common_ancestors': {}, 'paths': {}}
            else:
                result['后代近交系数'] = "0.00%"
                result['后代近交详情'] = {'system': 0.0, 'common_ancestors': {}, 'paths': {}}

            # 更新进度（每100条更新一次）
            if progress_cb and i % 100 == 0 and total_count > 0:
                pct = int(72 + (i / total_count) * 16)
                try:
                    progress_cb(pct, f"计算近交系数 ({i+1}/{total_count})")
                except Exception:
                    pass

        return results

    except Exception as e:
        logger.error(f"计算近交系数失败: {e}")
        # 设置默认值
        for result in results:
            if '后代近交系数' not in result:
                result['后代近交系数'] = "0.00%"
                result['后代近交详情'] = {'system': 0.0, 'common_ancestors': {}, 'paths': {}}
        return results


def _collect_abnormal_pairs(results):
    """收集异常配对和统计信息"""
    abnormal_records = []
    gene_stats = {gene: 0 for gene in DEFECT_GENES}
    inbreeding_count = 0

    for result in results:
        for gene in DEFECT_GENES:
            if result.get(gene) == '高风险':
                abnormal_records.append({
                    '牧场编号': result.get('牧场编号', ''),
                    '牧场名称': result.get('牧场名称', ''),
                    '母牛号': result['母牛号'],
                    '父号': result['父号'],
                    '公牛号': result.get('配种公牛号', result.get('备选公牛号')),
                    '异常类型': gene,
                    '状态': '公牛与母牛父亲共同携带隐性基因'
                })
                gene_stats[gene] += 1

        if '后代近交系数' in result:
            try:
                inbreeding_str = result['后代近交系数']
                inbreeding_value = float(inbreeding_str.strip('%')) / 100
                if inbreeding_value > 0.0625:
                    abnormal_records.append({
                        '牧场编号': result.get('牧场编号', ''),
                        '牧场名称': result.get('牧场名称', ''),
                        '母牛号': result['母牛号'],
                        '父号': result['父号'],
                        '公牛号': result.get('配种公牛号', result.get('备选公牛号')),
                        '异常类型': '近交系数过高',
                        '状态': f'{inbreeding_value:.3%}'
                    })
                    inbreeding_count += 1
            except (ValueError, TypeError):
                pass

    abnormal_df = pd.DataFrame(abnormal_records)

    stats_records = [
        {'异常类型': gene, '数量': count}
        for gene, count in gene_stats.items()
        if count > 0
    ]
    if inbreeding_count > 0:
        stats_records.append({'异常类型': '近交系数过高', '数量': inbreeding_count})

    stats_df = pd.DataFrame(stats_records)
    return abnormal_df, stats_df


def _collect_cow_self_abnormal(results):
    """按 UI 母牛近交分析口径生成异常明细与统计。"""
    abnormal_records = []
    gene_stats = {gene: 0 for gene in DEFECT_GENES}
    inbreeding_count = 0

    for result in results:
        for gene in DEFECT_GENES:
            if result.get(gene) == "仅母牛父亲携带":
                abnormal_records.append(
                    {
                        "牧场编号": result.get("牧场编号", ""),
                        "牧场名称": result.get("牧场名称", ""),
                        "母牛号": result["母牛号"],
                        "父号": result["父号"],
                        "公牛号": "",
                        "异常类型": gene,
                        "状态": "母牛父系携带隐性基因",
                    }
                )
                gene_stats[gene] += 1

        try:
            value = (
                float(
                    str(result.get("近交系数", "0%"))
                    .strip("%")
                )
                / 100
            )
        except (TypeError, ValueError):
            continue
        if value > 0.0625:
            abnormal_records.append(
                {
                    "牧场编号": result.get("牧场编号", ""),
                    "牧场名称": result.get("牧场名称", ""),
                    "母牛号": result["母牛号"],
                    "父号": result["父号"],
                    "公牛号": "",
                    "异常类型": "近交系数过高",
                    "状态": f"{value:.3%}",
                }
            )
            inbreeding_count += 1

    abnormal_df = pd.DataFrame(abnormal_records)
    stats_records = [
        {"异常类型": gene, "数量": count}
        for gene, count in gene_stats.items()
        if count > 0
    ]
    if inbreeding_count > 0:
        stats_records.append(
            {
                "异常类型": "近交系数过高",
                "数量": inbreeding_count,
            }
        )
    return abnormal_df, pd.DataFrame(stats_records)


def _build_farm_abnormal_stats(abnormal_df):
    required = ['牧场编号', '牧场名称', '异常类型']
    if abnormal_df.empty or not all(column in abnormal_df.columns for column in required):
        return pd.DataFrame()
    source = abnormal_df.copy()
    source['牧场编号'] = source['牧场编号'].fillna('').astype(str).str.strip()
    source['牧场名称'] = source['牧场名称'].fillna('').astype(str).str.strip()
    source = source[source['牧场编号'] != '']
    if source['牧场编号'].nunique() <= 1:
        return pd.DataFrame()
    return (
        source.groupby(required, dropna=False)
        .size()
        .reset_index(name='数量')
        .sort_values(['牧场编号', '异常类型'])
    )


def _upload_missing_bulls(missing_bulls, source):
    """静默上传缺失公牛信息"""
    try:
        from api.api_client import get_api_client
        api_client = get_api_client()
        bulls_data = [{
            'bull': bull_id,
            'source': source,
            'time': datetime.datetime.now().isoformat(),
            'user': 'auto_report'
        } for bull_id in missing_bulls]
        api_client.upload_missing_bulls(bulls_data)
    except Exception as e:
        logger.warning(f"上传缺失公牛信息失败（不影响主流程）: {e}")


# ============ Excel报告 ============

def run_excel_report(
    project_path,
    progress_cb=None,
    service_staff=None,
    farm_name=None,
    max_workers=6,
    include_mating=True,
):
    """生成Excel综合报告"""
    from core.excel_report.generator import ExcelReportGenerator
    gen = ExcelReportGenerator(project_path, service_staff=service_staff,
                                progress_callback=progress_cb,
                                farm_name=farm_name,
                                max_workers=max_workers,
                                include_mating=include_mating)
    return gen.generate()


# ============ PPT报告 ============

def run_ppt_report(project_path, farm_name="牧场", progress_cb=None, reporter_name=None):
    """生成PPT汇报材料"""
    from core.ppt_report.generator import ExcelBasedPPTGenerator
    gen = ExcelBasedPPTGenerator(project_path, farm_name=farm_name,
                                  reporter_name=reporter_name or "用户")
    return gen.generate_ppt(progress_cb)
