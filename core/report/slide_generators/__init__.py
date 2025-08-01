"""
幻灯片生成器模块

包含各部分PPT页面的生成器
"""

from .base import BaseSlideGenerator
from .title_toc import TitleSlideGenerator, TOCSlideGenerator
from .pedigree_analysis import PedigreeAnalysisGenerator
from .genetic_evaluation import GeneticEvaluationGenerator
from .linear_score import LinearScoreGenerator
from .bull_usage import BullUsageGenerator

__all__ = [
    'BaseSlideGenerator',
    'TitleSlideGenerator',
    'TOCSlideGenerator', 
    'PedigreeAnalysisGenerator',
    'GeneticEvaluationGenerator',
    'LinearScoreGenerator',
    'BullUsageGenerator'
]