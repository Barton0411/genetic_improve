"""
幻灯片构建器模块
"""

from .part1_cover import Part1CoverBuilder
from .part2_farm_overview import Part2FarmOverviewBuilder
from .part3_breeding_traits import Part3BreedingTraitsBuilder
from .part4_index_distribution import Part4IndexDistributionBuilder
from .part5_cow_ranking import Part5CowRankingBuilder
from .part6_breeding_genes import Part6BreedingGenesBuilder
from .part7_bull_mating import Part7BullMatingBuilder

__all__ = [
    'Part1CoverBuilder',
    'Part2FarmOverviewBuilder',
    'Part3BreedingTraitsBuilder',
    'Part4IndexDistributionBuilder',
    'Part5CowRankingBuilder',
    'Part6BreedingGenesBuilder',
    'Part7BullMatingBuilder',
]
