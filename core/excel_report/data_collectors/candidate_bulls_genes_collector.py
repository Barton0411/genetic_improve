"""
备选公牛隐性基因分析数据收集器
收集Sheet 12所需的所有数据：备选公牛-隐性基因分析
"""

from pathlib import Path
import logging
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
    'Factor XI': '凝血因子XI缺陷症',
    'MW': '早发肌无力',
    'Mulefoot': '并趾症'
}


def collect_candidate_bulls_genes_data(analysis_folder: Path, project_folder: Path, cache=None) -> dict:
    """
    收集备选公牛隐性基因分析数据 (Sheet 12)

    Args:
        analysis_folder: 分析结果文件夹路径
        project_folder: 项目文件夹路径（用于读取processed_cow_data）
        cache: DataCache实例（可选）

    Returns:
        数据字典:
        {
            'bulls': [  # 按总风险从高到低排序的公牛列表
                {
                    'bull_id': '001HO09154',
                    'original_bull_id': '151HO04449',
                    'mature_cow_count': 218,  # 成母牛总数
                    'heifer_count': 65,       # 后备牛总数
                    'total_cow_count': 283,   # 全群总数
                    'gene_summary': [  # 各基因统计
                        {
                            'gene_name': 'HH1',
                            'gene_translation': '单倍体不育1',
                            'mature_homozygous': 5,      # 成母牛纯合头数
                            'mature_ratio': 0.023,       # 成母牛纯合占比
                            'heifer_homozygous': 2,      # 后备牛纯合头数
                            'heifer_ratio': 0.031,       # 后备牛纯合占比
                            'total_homozygous': 7,       # 全群纯合头数
                            'total_ratio': 0.025         # 全群纯合占比
                        },
                        ...
                    ],
                    'total_risk': {  # 任意基因纯合小计
                        'mature_homozygous': 8,
                        'mature_ratio': 0.037,
                        'heifer_homozygous': 3,
                        'heifer_ratio': 0.046,
                        'total_homozygous': 11,
                        'total_ratio': 0.039
                    }
                },
                ...
            ]
        }
    """
    try:
        # 1. 查找最新的备选公牛分析结果文件
        pattern = str(analysis_folder / "备选公牛_近交系数及隐性基因分析结果_*.xlsx")
        files = glob.glob(pattern)

        if not files:
            logger.warning(f"未找到备选公牛分析结果文件: {pattern}")
            return {}

        latest_file = max(files, key=lambda x: Path(x).name)
        logger.info(f"读取文件: {latest_file}")

        # 2. 读取数据（使用缓存）
        if cache:
            df = cache.get_excel(latest_file)
        else:
            df = pd.read_excel(latest_file)

        # 3. 读取processed_cow_data获取胎次和在场信息
        cow_data_file = project_folder / "standardized_data" / "processed_cow_data.xlsx"
        if not cow_data_file.exists():
            logger.warning(f"未找到文件: {cow_data_file}")
            return {}

        if cache:
            cow_data = cache.get_excel(str(cow_data_file))
        else:
            cow_data = pd.read_excel(cow_data_file)

        # 提取需要的列（processed_cow_data使用cow_id作为列名）
        cow_info = cow_data[['cow_id', '是否在场', 'sex', 'lac']].copy()
        cow_info['cow_id'] = cow_info['cow_id'].astype(str)
        # 确保sex列正确填充（处理全NaN的情况，母牛数据默认为'母'）
        if cow_info['sex'].isna().all():
            cow_info['sex'] = '母'
        else:
            cow_info['sex'] = cow_info['sex'].fillna('母')

        # 4. 合并数据（备选公牛文件使用母牛号，processed_cow_data使用cow_id）
        df['母牛号'] = df['母牛号'].astype(str)
        merged = df.merge(cow_info, left_on='母牛号', right_on='cow_id', how='left')

        # 5. 筛选在群母牛
        in_herd = merged[(merged['是否在场'] == '是') & (merged['sex'] == '母')].copy()

        if len(in_herd) == 0:
            logger.warning("没有在群母牛数据")
            return {}

        # 6. 识别所有隐性基因列
        exclude_cols = ['母牛号', '父号', '原始父号', '备选公牛号', '原始备选公牛号',
                       '近交系数', '后代近交系数', '后代近交详情', '是否在场', 'sex', 'lac']

        all_genes = []
        for col in df.columns:
            if col not in exclude_cols and '(' not in str(col):
                if f'{col}(母)' in df.columns and f'{col}(公)' in df.columns:
                    all_genes.append(col)

        # 基因排序：HH系列在前
        hh_genes = sorted([g for g in all_genes if g.startswith('HH')])
        other_genes = sorted([g for g in all_genes if not g.startswith('HH')])
        sorted_genes = hh_genes + other_genes

        logger.info(f"识别到 {len(sorted_genes)} 个隐性基因: {sorted_genes}")

        # 7. 获取所有备选公牛
        bulls = in_herd['备选公牛号'].unique()
        logger.info(f"识别到 {len(bulls)} 个备选公牛")

        # 8. 按公牛统计
        bulls_data = []
        for bull_id in bulls:
            bull_data = in_herd[in_herd['备选公牛号'] == bull_id].copy()

            # 获取公牛的原始号（取第一个）
            original_bull_id = bull_data['原始备选公牛号'].iloc[0] if len(bull_data) > 0 else ''

            # 分组统计
            mature_cows = bull_data[bull_data['lac'] > 0]
            heifers = bull_data[bull_data['lac'] == 0]

            mature_count = len(mature_cows)
            heifer_count = len(heifers)
            total_count = len(bull_data)

            # 统计各基因
            gene_summary = []
            total_mature_homozygous = 0
            total_heifer_homozygous = 0

            for gene in sorted_genes:
                if gene not in bull_data.columns:
                    continue

                # 成母牛纯合头数
                mature_homozygous = len(mature_cows[mature_cows[gene] == '高风险'])
                mature_ratio = mature_homozygous / mature_count if mature_count > 0 else 0

                # 后备牛纯合头数
                heifer_homozygous = len(heifers[heifers[gene] == '高风险'])
                heifer_ratio = heifer_homozygous / heifer_count if heifer_count > 0 else 0

                # 全群纯合头数
                total_homozygous = len(bull_data[bull_data[gene] == '高风险'])
                total_ratio = total_homozygous / total_count if total_count > 0 else 0

                gene_summary.append({
                    'gene_name': gene,
                    'gene_translation': GENE_TRANSLATIONS.get(gene, ''),
                    'mature_homozygous': mature_homozygous,
                    'mature_ratio': mature_ratio,
                    'heifer_homozygous': heifer_homozygous,
                    'heifer_ratio': heifer_ratio,
                    'total_homozygous': total_homozygous,
                    'total_ratio': total_ratio
                })

                # 累计任意基因纯合（去重：一头牛可能多个基因都纯合，只计一次）
                # 这里暂时简单相加，后续优化
                total_mature_homozygous += mature_homozygous
                total_heifer_homozygous += heifer_homozygous

            # 计算任意基因纯合的真实头数（去重）
            mature_any_homozygous = len(mature_cows[
                mature_cows[sorted_genes].apply(lambda row: (row == '高风险').any(), axis=1)
            ]) if len(sorted_genes) > 0 and len(mature_cows) > 0 else 0

            heifer_any_homozygous = len(heifers[
                heifers[sorted_genes].apply(lambda row: (row == '高风险').any(), axis=1)
            ]) if len(sorted_genes) > 0 and len(heifers) > 0 else 0

            total_any_homozygous = len(bull_data[
                bull_data[sorted_genes].apply(lambda row: (row == '高风险').any(), axis=1)
            ]) if len(sorted_genes) > 0 and len(bull_data) > 0 else 0

            bulls_data.append({
                'bull_id': str(bull_id),
                'original_bull_id': str(original_bull_id),
                'mature_cow_count': mature_count,
                'heifer_count': heifer_count,
                'total_cow_count': total_count,
                'gene_summary': gene_summary,
                'total_risk': {
                    'mature_homozygous': mature_any_homozygous,
                    'mature_ratio': mature_any_homozygous / mature_count if mature_count > 0 else 0,
                    'heifer_homozygous': heifer_any_homozygous,
                    'heifer_ratio': heifer_any_homozygous / heifer_count if heifer_count > 0 else 0,
                    'total_homozygous': total_any_homozygous,
                    'total_ratio': total_any_homozygous / total_count if total_count > 0 else 0
                }
            })

        # 9. 按总风险从高到低排序
        bulls_data.sort(key=lambda x: x['total_risk']['total_ratio'], reverse=True)

        return {'bulls': bulls_data}

    except Exception as e:
        logger.error(f"收集备选公牛隐性基因数据时发生错误: {e}", exc_info=True)
        return {}
