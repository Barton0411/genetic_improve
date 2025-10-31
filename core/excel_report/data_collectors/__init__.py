"""数据收集模块 v1.2"""

# v1.1 collectors (已完成的Sheet 1-4)
from .farm_info_collector import collect_farm_info
from .pedigree_collector import collect_pedigree_data
from .traits_collector import collect_traits_data
from .cow_index_collector import collect_cow_index_data
from .bull_ranking_collector import collect_bull_ranking_data
from .mating_collector import collect_mating_data

# v1.2 collectors (Sheet 5-11)
from .gene_collector import collect_gene_data, collect_breeding_genes_data
from .breeding_inbreeding_collector import collect_breeding_inbreeding_data
from .breeding_detail_collector import collect_breeding_detail_data
from .bull_usage_collector import collect_bull_usage_data, collect_bull_usage_summary_data  # Sheet 8 (旧版)
from .used_bulls_summary_collector_wrapper import collect_used_bulls_summary_data  # Sheet 8 (v1.2.2新版)
from .used_bulls_detail_collector_wrapper import collect_used_bulls_detail_data  # Sheet 9 (v1.2.2新版)

# v1.1兼容（保留旧函数）
from .inbreeding_collector import collect_inbreeding_data
from .bull_prediction_collector import collect_bull_prediction_data

__all__ = [
    # v1.1 collectors
    'collect_farm_info',
    'collect_pedigree_data',
    'collect_traits_data',
    'collect_cow_index_data',
    'collect_bull_ranking_data',
    'collect_mating_data',

    # v1.2 collectors
    'collect_breeding_genes_data',  # Sheet 5 v1.2
    'collect_breeding_inbreeding_data',  # Sheet 6 v1.2
    'collect_breeding_detail_data',  # Sheet 7 v1.2
    'collect_bull_usage_summary_data',  # Sheet 8 v1.2 (旧版)
    'collect_used_bulls_summary_data',  # Sheet 8 v1.2.2 (新版)
    'collect_used_bulls_detail_data',  # Sheet 9 v1.2.2 (新版)

    # v1.1兼容
    'collect_gene_data',
    'collect_bull_usage_data',
    'collect_inbreeding_data',
    'collect_bull_prediction_data',
]
