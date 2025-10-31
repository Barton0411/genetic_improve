"""
备选公牛排名数据收集器
收集Sheet 10所需的所有数据
合并processed_index_bull_scores.xlsx（排名和指数）和processed_bull_data_key_traits.xlsx（性状数据）
从备选公牛隐性基因分析结果中提取基因信息
"""

from pathlib import Path
import pandas as pd
import logging
import glob
from sqlalchemy import create_engine
from core.data.update_manager import LOCAL_DB_PATH

logger = logging.getLogger(__name__)


def _extract_bull_genes(analysis_folder: Path) -> pd.DataFrame:
    """
    从备选公牛隐性基因分析结果中提取基因信息

    Args:
        analysis_folder: 分析结果文件夹路径

    Returns:
        DataFrame包含bull_id和基因列(HH1-HH6, MW)
    """
    try:
        # 查找备选公牛隐性基因分析文件
        gene_files = list(analysis_folder.glob("备选公牛_近交系数及隐性基因分析结果_*.xlsx"))

        if not gene_files:
            logger.warning("未找到备选公牛基因分析文件")
            return pd.DataFrame()

        # 使用最新的文件
        gene_file = sorted(gene_files)[-1]
        logger.info(f"读取基因分析文件: {gene_file.name}")

        # 读取配对明细表
        df = pd.read_excel(gene_file, sheet_name="配对明细表")

        # 获取所有备选公牛（使用原始公牛号作为ID）
        # 原始备选公牛号是短号，与ranking数据匹配
        bulls = df[['备选公牛号', '原始备选公牛号']].drop_duplicates()

        # 基因列表 (只取公牛的基因列)
        gene_cols = ['HH1(公)', 'HH2(公)', 'HH3(公)', 'HH4(公)', 'HH5(公)', 'HH6(公)']

        # 检查是否有HMW/MW
        if 'HMW(公)' in df.columns:
            gene_cols.append('HMW(公)')
        elif 'MW(公)' in df.columns:
            gene_cols.append('MW(公)')

        # 为每头公牛提取基因信息
        bull_genes = []
        for _, bull_row in bulls.iterrows():
            naab_id = bull_row['备选公牛号']
            short_id = bull_row['原始备选公牛号']

            bull_data = df[df['备选公牛号'] == naab_id].iloc[0]
            # 使用短号作为bull_id，这样可以与ranking数据匹配
            gene_info = {'bull_id': short_id}

            for gene_col in gene_cols:
                if gene_col in df.columns:
                    # 去掉(公)后缀作为列名
                    gene_name = gene_col.replace('(公)', '')
                    # HMW用MW作为列名
                    if gene_name == 'HMW':
                        gene_name = 'MW'
                    gene_info[gene_name] = bull_data[gene_col]

            bull_genes.append(gene_info)

        df_genes = pd.DataFrame(bull_genes)

        # 统计携带情况
        carriers = {}
        for col in df_genes.columns:
            if col != 'bull_id':
                count = (df_genes[col] == 'C').sum()
                if count > 0:
                    carriers[col] = count

        if carriers:
            logger.info(f"基因携带统计: {carriers}")

        return df_genes

    except Exception as e:
        logger.error(f"提取基因信息失败: {e}", exc_info=True)
        return pd.DataFrame()


def _supplement_traits_from_db(df: pd.DataFrame, required_traits: list) -> pd.DataFrame:
    """
    从数据库中补充缺失的性状数据

    Args:
        df: 包含bull_id列的DataFrame
        required_traits: 需要的性状列表

    Returns:
        补充了缺失性状的DataFrame
    """
    try:
        # 检查哪些性状缺失
        missing_traits = [t for t in required_traits if t not in df.columns]

        if not missing_traits:
            logger.info("所有需要的性状都已存在")
            return df

        logger.info(f"需要从数据库补充的性状: {missing_traits}")

        # 获取所有bull_id
        bull_ids = df['bull_id'].unique().tolist()

        if not bull_ids:
            logger.warning("没有公牛ID，无法补充数据")
            return df

        # 连接数据库
        engine = create_engine(f'sqlite:///{LOCAL_DB_PATH}')

        # 构建查询（使用short_name匹配bull_id）
        placeholders = ','.join(['?' for _ in bull_ids])
        trait_cols_str = ','.join([f'"{t}"' for t in missing_traits])

        query = f"""
        SELECT short_name as bull_id, {trait_cols_str}
        FROM bull_data
        WHERE short_name IN ({placeholders})
        """

        # 执行查询
        df_db = pd.read_sql_query(query, engine, params=bull_ids)
        logger.info(f"从数据库获取到 {len(df_db)} 头公牛的数据")

        # 合并数据
        df_result = df.merge(df_db, on='bull_id', how='left')

        # 记录补充情况
        for trait in missing_traits:
            if trait in df_result.columns:
                non_null_count = df_result[trait].notna().sum()
                logger.info(f"  {trait}: 补充了 {non_null_count}/{len(df_result)} 个值")

        return df_result

    except Exception as e:
        logger.error(f"从数据库补充性状失败: {e}", exc_info=True)
        return df


def collect_bull_ranking_data(analysis_folder) -> dict:
    """
    收集备选公牛排名数据

    合并两个数据源：
    1. processed_index_bull_scores.xlsx - 提供ranking和测试_index
    2. processed_bull_data_key_traits.xlsx - 提供完整的性状数据

    Args:
        analysis_folder: 分析结果文件夹路径（字符串或Path对象）

    Returns:
        数据字典，包含:
        - bull_rankings: 合并后的公牛排名DataFrame（按ranking排序）
        - total_bulls: 公牛总数
        - sexed_bulls: 性控公牛数
        - regular_bulls: 常规公牛数
    """
    # 确保是Path对象
    analysis_path = Path(analysis_folder) if isinstance(analysis_folder, str) else analysis_folder

    # 查找两个数据文件
    ranking_file = analysis_path / "processed_index_bull_scores.xlsx"
    traits_file = analysis_path / "processed_bull_data_key_traits.xlsx"

    if not ranking_file.exists():
        logger.warning("备选公牛排名文件不存在，跳过Sheet 10")
        return {}

    if not traits_file.exists():
        logger.warning("备选公牛性状文件不存在，跳过Sheet 10")
        return {}

    try:
        logger.info("开始收集备选公牛排名数据...")

        # 1. 读取排名和指数数据
        df_ranking = pd.read_excel(ranking_file, sheet_name="Sheet1")
        logger.info(f"读取排名数据: {len(df_ranking)} 条记录")

        # 2. 读取性状数据
        df_traits = pd.read_excel(traits_file, sheet_name="Sheet1")
        logger.info(f"读取性状数据: {len(df_traits)} 条记录")

        # 3. 合并数据：以ranking数据为基础，补充traits数据
        # 关键字段：bull_id + semen_type
        df_merged = df_ranking.merge(
            df_traits,
            on=['bull_id', 'semen_type'],
            how='left',
            suffixes=('_ranking', '_traits')
        )

        # 4. 整理列顺序：ranking, bull_id, semen_type, 测试_index, 性状列, 支数
        # 保留traits数据的支数和所有性状列，只从ranking数据中取ranking和测试_index

        # 处理重复列：优先使用traits文件的数据
        # 首先删除ranking文件中的性状列（保留ranking和测试_index）
        cols_to_drop = []
        for col in df_merged.columns:
            if col.endswith('_ranking') and col != '测试_index_ranking':
                # 删除ranking文件的非关键列
                if col.replace('_ranking', '_traits') in df_merged.columns:
                    # 如果traits文件也有这个列，保留traits版本
                    cols_to_drop.append(col)
                elif col.replace('_ranking', '') not in ['ranking', '测试_index']:
                    # 如果只有ranking版本且不是关键列，也删除
                    cols_to_drop.append(col)

        if cols_to_drop:
            df_merged = df_merged.drop(cols_to_drop, axis=1)

        # 重命名traits列，去掉_traits后缀
        rename_map = {}
        for col in df_merged.columns:
            if col.endswith('_traits'):
                new_name = col.replace('_traits', '')
                rename_map[col] = new_name

        if rename_map:
            df_merged = df_merged.rename(columns=rename_map)

        # 5. 从数据库补充技术标准中需要的性状（如FE）
        from ..config.bull_quality_standards import US_PROGENY_STANDARDS
        required_traits = list(US_PROGENY_STANDARDS.keys())
        logger.info(f"技术标准要求的性状: {required_traits}")

        df_merged = _supplement_traits_from_db(df_merged, required_traits)

        # 6. 提取并合并基因信息
        df_genes = _extract_bull_genes(analysis_path)

        if not df_genes.empty:
            # 合并基因信息 (基于bull_id，不考虑semen_type因为基因对于同一公牛是相同的)
            df_merged = df_merged.merge(
                df_genes,
                on='bull_id',
                how='left'
            )
            logger.info(f"合并基因信息: {len(df_genes)} 头公牛")

        # 动态获取基因列
        from ..config.bull_quality_standards import DEFECT_GENES
        gene_cols = DEFECT_GENES

        # 动态构建最终列顺序
        # 1. 固定列（排名、ID、类型等）
        fixed_cols = ['ranking', 'bull_id', 'semen_type', '测试_index', '支数']

        # 2. 性状列（从DataFrame中动态获取，排除固定列和基因列）
        exclude_cols = set(fixed_cols + gene_cols)
        trait_cols = [col for col in df_merged.columns
                     if col not in exclude_cols and col not in ['Eval Date']]

        # 3. 添加Eval Date到最后（如果存在）
        if 'Eval Date' in df_merged.columns:
            trait_cols.append('Eval Date')

        # 4. 构建最终列顺序：固定列 + 性状列 + 基因列
        final_cols = fixed_cols.copy()
        final_cols.extend(trait_cols)

        # 添加存在的基因列
        for col in gene_cols:
            if col in df_merged.columns:
                final_cols.append(col)

        logger.info(f"动态识别到 {len(trait_cols)} 个性状列")
        logger.info(f"性状列: {trait_cols}")

        # 选择并排序列
        df_merged = df_merged[final_cols]

        # 按ranking排序
        df_merged = df_merged.sort_values('ranking').reset_index(drop=True)

        # 统计
        sexed_count = (df_merged['semen_type'] == '性控').sum()
        regular_count = (df_merged['semen_type'] == '常规').sum()

        result = {
            'bull_rankings': df_merged,
            'total_bulls': len(df_merged),
            'sexed_bulls': sexed_count,
            'regular_bulls': regular_count
        }

        logger.info(f"✓ 备选公牛排名数据收集完成: {len(df_merged)}头公牛 (性控: {sexed_count}, 常规: {regular_count})")
        logger.info(f"  数据列: {len(df_merged.columns)}列，包含完整性状数据")
        return result

    except Exception as e:
        logger.error(f"收集备选公牛排名数据失败: {e}", exc_info=True)
        return {}
