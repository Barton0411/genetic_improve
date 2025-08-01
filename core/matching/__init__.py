# -*- coding: utf-8 -*-
"""
匹配模块
提供选配相关的核心功能
"""

from .cycle_based_matcher import CycleBasedMatcher
from .matrix_recommendation_generator import MatrixRecommendationGenerator
from .allocation_utils import calculate_proportional_allocation, calculate_equal_allocation

# 废弃的模块，保留用于向后兼容
# from .individual_matcher import IndividualMatcher  # DEPRECATED

__all__ = [
    'CycleBasedMatcher',
    'MatrixRecommendationGenerator',
    'calculate_proportional_allocation',
    'calculate_equal_allocation'
]