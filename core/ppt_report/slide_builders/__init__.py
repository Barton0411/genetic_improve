"""
幻灯片构建器模块
"""

from .part1_cover import Part1CoverBuilder
from .part2_farm_overview import Part2FarmOverviewBuilder
from .part3_breeding_traits import Part3BreedingTraitsBuilder
from .part4_index_distribution import Part4IndexDistributionBuilder
from .part5_cow_ranking import Part5CowRankingBuilder
from .part6_breeding_genes import Part6BreedingGenesBuilder
from .part6_bulls_usage import Part6BullsUsageBuilder
from .part6_bulls_detail import Part6BullsDetailBuilder
from .part6_traits_trends import Part6TraitsTrendsBuilder
from .part6_timeline import Part6TimelineBuilder
from .part7_candidate_bulls_ranking import Part7CandidateBullsRankingBuilder
from .part7_candidate_bulls_genes import Part7CandidateBullsGenesBuilder
from .part7_candidate_bulls_inbreeding import Part7CandidateBullsInbreedingBuilder
from .part7_bull_mating import Part7BullMatingBuilder

__all__ = [
    'Part1CoverBuilder',
    'Part2FarmOverviewBuilder',
    'Part3BreedingTraitsBuilder',
    'Part4IndexDistributionBuilder',
    'Part5CowRankingBuilder',
    'Part6BreedingGenesBuilder',
    'Part6BullsUsageBuilder',
    'Part6BullsDetailBuilder',
    'Part6TraitsTrendsBuilder',
    'Part6TimelineBuilder',
    'Part7CandidateBullsRankingBuilder',
    'Part7CandidateBullsGenesBuilder',
    'Part7CandidateBullsInbreedingBuilder',
    'Part7BullMatingBuilder',
]
