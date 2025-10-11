"""
隐性基因分析数据收集器 v1.2
收集Sheet 5所需的所有数据：配种记录-隐性基因纯合风险分析
"""

from pathlib import Path
import logging
from datetime import datetime, timedelta
import pandas as pd
import glob

logger = logging.getLogger(__name__)

# 基因中文翻译映射
GENE_TRANSLATIONS = {
    'HH1': '单倍体不育1',
    'HH2': '单倍体不育2',
    'HH3': '单倍体不育3',
    'HH4': '单倍体不育4',
    'HH5': '单倍体不育5',
    'HH6': '单倍体不育6',
    'BLAD': '白细胞黏附缺陷症',
    'Brachyspina': '短脊椎症',
    'CVM': '牛脊椎畸形综合征',
    'Cholesterol deficiency': '胆固醇缺乏症',
    'Chondrodysplasia': '软骨发育不良',
    'Citrullinemia': '瓜氨酸血症',
    'DUMPS': '尿苷单磷酸合成酶缺乏症',
    'Factor XI': '凝血因子XI缺乏症',
    'MW': '早发肌无力',
    'Mulefoot': '并趾症'
}


def collect_breeding_genes_data(analysis_folder: Path) -> dict:
    """
    收集配种记录中的隐性基因纯合分析数据 (Sheet 5 v1.2)

    Args:
        analysis_folder: 分析结果文件夹路径

    Returns:
        数据字典:
        {
            'all_years_summary': [  # 全部年份隐性基因纯合汇总
                {
                    'gene_name': 'HH1',
                    'homozygous_count': 5,          # 纯合配次
                    'homozygous_ratio': 0.012,      # 占总配种比例
                    'bull_only_count': 45,          # 仅公牛携带配次
                    'bull_only_ratio': 0.105,       # 占比
                    'dam_sire_only_count': 38,      # 仅母牛父亲携带配次
                    'dam_sire_only_ratio': 0.089,   # 占比
                    'missing_data_count': 12,       # 数据缺少配次
                    'missing_data_ratio': 0.028     # 占比
                },
                ...
            ],
            'all_years_total': 190,       # 全部年份总配次
            'recent_12m_summary': [...],  # 近12个月数据（格式同上）
            'recent_12m_total': 32,       # 近12个月总配次
            'date_range': {               # 近12个月的日期范围
                'start': '2023-10-10',
                'end': '2024-10-10'
            }
        }
    """
    try:
        # 1. 查找最新的已配公牛分析结果文件
        pattern = str(analysis_folder / "已配公牛_近交系数及隐性基因分析结果_*.xlsx")
        files = glob.glob(pattern)

        if not files:
            logger.warning(f"未找到已配公牛分析结果文件: {pattern}")
            return {}

        # 按文件名时间戳排序（文件名格式：已配公牛_近交系数及隐性基因分析结果_YYYYMMDD_HHMMSS.xlsx）
        # 时间戳格式天然可排序，直接按文件名排序即可
        latest_file = max(files, key=lambda x: Path(x).name)
        logger.info(f"读取文件: {latest_file}")

        # 2. 读取数据
        df = pd.read_excel(latest_file)

        # 确保有配种日期列
        if '配种日期' not in df.columns:
            logger.warning("文件中缺少'配种日期'列，无法进行时间筛选")
            return {}

        # 转换配种日期为datetime类型
        df['配种日期'] = pd.to_datetime(df['配种日期'], errors='coerce')

        # 3. 自动识别所有隐性基因列表
        # 排除非基因列
        exclude_cols = ['母牛号', '配种日期', '父号', '原始父号', '配种公牛号', '原始公牛号',
                       '近交系数', '后代近交系数', '后代近交详情']

        # 找出所有基因列（不带(母)和(公)后缀）
        all_genes = []
        for col in df.columns:
            if col not in exclude_cols and '(' not in str(col):
                # 确保有对应的(母)和(公)列
                if f'{col}(母)' in df.columns and f'{col}(公)' in df.columns:
                    all_genes.append(col)

        # 4. 基因排序：HH系列在前，其他在后
        hh_genes = sorted([g for g in all_genes if g.startswith('HH')])
        other_genes = sorted([g for g in all_genes if not g.startswith('HH')])
        sorted_genes = hh_genes + other_genes

        logger.info(f"识别到 {len(sorted_genes)} 个隐性基因: {sorted_genes}")

        # 5. 统计全部年份的数据
        all_years_summary = _analyze_gene_data(df, sorted_genes)
        all_years_total = len(df)

        # 6. 筛选近12个月的数据
        today = datetime.now()
        twelve_months_ago = today - timedelta(days=365)
        recent_df = df[df['配种日期'] >= twelve_months_ago].copy()

        # 7. 统计近12个月的数据
        recent_12m_summary = _analyze_gene_data(recent_df, sorted_genes)
        recent_12m_total = len(recent_df)

        # 8. 计算日期范围
        if len(recent_df) > 0 and recent_df['配种日期'].notna().any():
            min_date = recent_df['配种日期'].min()
            max_date = recent_df['配种日期'].max()
            date_range = {
                'start': min_date.strftime('%Y-%m-%d') if pd.notna(min_date) else '',
                'end': max_date.strftime('%Y-%m-%d') if pd.notna(max_date) else ''
            }
        else:
            date_range = {'start': '', 'end': ''}

        return {
            'all_years_summary': all_years_summary,
            'all_years_total': all_years_total,
            'recent_12m_summary': recent_12m_summary,
            'recent_12m_total': recent_12m_total,
            'date_range': date_range
        }

    except Exception as e:
        logger.error(f"收集隐性基因数据时发生错误: {e}", exc_info=True)
        return {}


def _analyze_gene_data(df: pd.DataFrame, gene_list: list) -> list:
    """
    分析隐性基因数据（基于基因列的状态值）

    Args:
        df: 配种记录DataFrame
        gene_list: 基因列表 ['HH1', 'HH2', 'BLAD', ...]

    Returns:
        基因汇总列表

    状态值映射：
        '高风险' → 纯合配次
        '仅公牛携带' → 仅公牛携带配次
        '仅母牛父亲携带' → 仅母牛父亲携带配次
        '缺少公牛信息' / '缺少母牛父亲信息' / '缺少双方信息' → 数据缺少配次
        '-' → 安全（不统计）
    """
    total_count = len(df)
    if total_count == 0:
        return []

    results = []

    for gene in gene_list:
        gene_col = gene

        # 检查列是否存在
        if gene_col not in df.columns:
            logger.warning(f"缺少基因列: {gene}")
            continue

        # 直接根据基因列的状态值统计
        # 纯合配次：状态为'高风险'
        homozygous_count = len(df[df[gene_col] == '高风险'])

        # 仅公牛携带配次：状态为'仅公牛携带'
        bull_only_count = len(df[df[gene_col] == '仅公牛携带'])

        # 仅母牛父亲携带配次：状态为'仅母牛父亲携带'
        dam_sire_only_count = len(df[df[gene_col] == '仅母牛父亲携带'])

        # 数据缺少配次：合并3种缺失情况
        missing_data_count = len(df[df[gene_col].isin([
            '缺少公牛信息', '缺少母牛父亲信息', '缺少双方信息'
        ])])

        # 计算占比
        homozygous_ratio = homozygous_count / total_count if total_count > 0 else 0
        bull_only_ratio = bull_only_count / total_count if total_count > 0 else 0
        dam_sire_only_ratio = dam_sire_only_count / total_count if total_count > 0 else 0
        missing_data_ratio = missing_data_count / total_count if total_count > 0 else 0

        results.append({
            'gene_name': gene,
            'gene_translation': GENE_TRANSLATIONS.get(gene, ''),  # 添加中文翻译
            'homozygous_count': homozygous_count,
            'homozygous_ratio': homozygous_ratio,
            'bull_only_count': bull_only_count,
            'bull_only_ratio': bull_only_ratio,
            'dam_sire_only_count': dam_sire_only_count,
            'dam_sire_only_ratio': dam_sire_only_ratio,
            'missing_data_count': missing_data_count,
            'missing_data_ratio': missing_data_ratio
        })

    return results


# 保留旧函数名以兼容（重定向到新函数）
def collect_gene_data(analysis_folder: Path) -> dict:
    """
    隐性基因分析数据收集（v1.1兼容接口）
    重定向到v1.2的collect_breeding_genes_data
    """
    return collect_breeding_genes_data(analysis_folder)
