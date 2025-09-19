"""
体型外貌鉴定数据处理器
处理牛群的体型线性评分数据
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ConformationDataProcessor:
    """体型外貌鉴定数据处理器"""

    # 线性评分项目定义
    CONFORMATION_TRAITS = {
        # 体躯容量
        'stature': {'name': '身高', 'category': '体躯容量', 'ideal_score': 7},
        'chest_width': {'name': '胸宽', 'category': '体躯容量', 'ideal_score': 8},
        'body_depth': {'name': '体深', 'category': '体躯容量', 'ideal_score': 8},
        'angularity': {'name': '棱角性', 'category': '体躯容量', 'ideal_score': 7},
        'body_condition': {'name': '体况', 'category': '体躯容量', 'ideal_score': 5},

        # 后肢
        'rump_angle': {'name': '尻角度', 'category': '后肢', 'ideal_score': 5},
        'rump_width': {'name': '尻宽', 'category': '后肢', 'ideal_score': 8},
        'rear_legs_side': {'name': '后肢侧视', 'category': '后肢', 'ideal_score': 5},
        'rear_legs_rear': {'name': '后肢后视', 'category': '后肢', 'ideal_score': 7},
        'foot_angle': {'name': '蹄角度', 'category': '后肢', 'ideal_score': 7},
        'locomotion': {'name': '移动性', 'category': '后肢', 'ideal_score': 7},

        # 乳房系统
        'fore_udder': {'name': '前乳房附着', 'category': '乳房系统', 'ideal_score': 8},
        'rear_udder_height': {'name': '后乳房高度', 'category': '乳房系统', 'ideal_score': 9},
        'rear_udder_width': {'name': '后乳房宽度', 'category': '乳房系统', 'ideal_score': 8},
        'udder_cleft': {'name': '乳房中沟', 'category': '乳房系统', 'ideal_score': 7},
        'udder_depth': {'name': '乳房深度', 'category': '乳房系统', 'ideal_score': 5},
        'front_teat_placement': {'name': '前乳头位置', 'category': '乳房系统', 'ideal_score': 5},
        'rear_teat_placement': {'name': '后乳头位置', 'category': '乳房系统', 'ideal_score': 5},
        'teat_length': {'name': '乳头长度', 'category': '乳房系统', 'ideal_score': 5}
    }

    # 缺陷性状定义
    DEFECT_TRAITS = {
        # 体躯缺陷
        'hunchback': '弓背',
        'weak_loin': '腰弱',
        'narrow_chest': '胸狭窄',

        # 肢蹄缺陷
        'splay_toe': '蹄叉开',
        'sickle_hock': '刀状腿',
        'bow_legged': '弓形腿',
        'swollen_hock': '飞节肿大',
        'lameness': '跛行',

        # 乳房缺陷
        'pendulous_udder': '下垂乳房',
        'unbalanced_udder': '乳区不平衡',
        'supernumerary_teats': '副乳头',
        'blind_quarter': '盲乳区'
    }

    def __init__(self):
        """初始化处理器"""
        self.data = None
        self.farm_info = {}

    def load_data(self, file_path: Path) -> bool:
        """
        加载体型鉴定数据

        Args:
            file_path: 数据文件路径

        Returns:
            是否成功加载
        """
        try:
            if file_path.suffix in ['.xlsx', '.xls']:
                self.data = pd.read_excel(file_path)
            elif file_path.suffix == '.csv':
                self.data = pd.read_csv(file_path)
            else:
                logger.error(f"不支持的文件格式: {file_path.suffix}")
                return False

            logger.info(f"成功加载{len(self.data)}条体型鉴定记录")
            return True

        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            return False

    def process_linear_scores(self) -> pd.DataFrame:
        """
        处理线性评分数据

        Returns:
            处理后的评分数据
        """
        if self.data is None or self.data.empty:
            logger.warning("没有数据可处理")
            return pd.DataFrame()

        try:
            # 计算各项目的平均分
            score_summary = {}

            for trait_key, trait_info in self.CONFORMATION_TRAITS.items():
                if trait_key in self.data.columns:
                    scores = pd.to_numeric(self.data[trait_key], errors='coerce')
                    score_summary[trait_info['name']] = {
                        'mean': scores.mean(),
                        'std': scores.std(),
                        'min': scores.min(),
                        'max': scores.max(),
                        'ideal': trait_info['ideal_score'],
                        'category': trait_info['category'],
                        'deviation': abs(scores.mean() - trait_info['ideal_score'])
                    }

            return pd.DataFrame(score_summary).T

        except Exception as e:
            logger.error(f"处理线性评分数据失败: {e}")
            return pd.DataFrame()

    def analyze_defects(self) -> Dict[str, float]:
        """
        分析缺陷性状

        Returns:
            缺陷性状占比
        """
        if self.data is None or self.data.empty:
            return {}

        defect_stats = {}
        total_count = len(self.data)

        for defect_key, defect_name in self.DEFECT_TRAITS.items():
            if defect_key in self.data.columns:
                # 计算有该缺陷的牛只数量
                defect_count = self.data[defect_key].notna().sum()
                defect_stats[defect_name] = {
                    'count': defect_count,
                    'percentage': (defect_count / total_count * 100) if total_count > 0 else 0
                }

        return defect_stats

    def calculate_composite_scores(self) -> pd.DataFrame:
        """
        计算综合评分

        Returns:
            综合评分数据
        """
        if self.data is None or self.data.empty:
            return pd.DataFrame()

        try:
            composite_scores = {}

            # 按类别计算综合分
            for category in ['体躯容量', '后肢', '乳房系统']:
                traits_in_category = [
                    key for key, info in self.CONFORMATION_TRAITS.items()
                    if info['category'] == category and key in self.data.columns
                ]

                if traits_in_category:
                    category_scores = self.data[traits_in_category].apply(pd.to_numeric, errors='coerce')
                    composite_scores[category] = {
                        'mean': category_scores.mean(axis=1).mean(),
                        'std': category_scores.mean(axis=1).std(),
                        'median': category_scores.mean(axis=1).median()
                    }

            return pd.DataFrame(composite_scores).T

        except Exception as e:
            logger.error(f"计算综合评分失败: {e}")
            return pd.DataFrame()

    def identify_improvement_areas(self) -> List[Dict[str, Any]]:
        """
        识别需要改进的区域

        Returns:
            需要改进的项目列表
        """
        improvement_areas = []

        if self.data is None or self.data.empty:
            return improvement_areas

        try:
            # 分析线性评分偏离理想值较大的项目
            for trait_key, trait_info in self.CONFORMATION_TRAITS.items():
                if trait_key in self.data.columns:
                    scores = pd.to_numeric(self.data[trait_key], errors='coerce')
                    mean_score = scores.mean()
                    ideal_score = trait_info['ideal_score']
                    deviation = abs(mean_score - ideal_score)

                    if deviation > 1.5:  # 偏离理想值超过1.5分
                        improvement_areas.append({
                            'trait': trait_info['name'],
                            'category': trait_info['category'],
                            'current_score': round(mean_score, 2),
                            'ideal_score': ideal_score,
                            'deviation': round(deviation, 2),
                            'priority': 'high' if deviation > 2.5 else 'medium'
                        })

            # 按偏离程度排序
            improvement_areas.sort(key=lambda x: x['deviation'], reverse=True)

            return improvement_areas

        except Exception as e:
            logger.error(f"识别改进区域失败: {e}")
            return []

    def generate_trend_analysis(self, historical_data: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        生成趋势分析

        Args:
            historical_data: 历史数据

        Returns:
            趋势分析结果
        """
        if self.data is None or self.data.empty:
            return pd.DataFrame()

        try:
            current_scores = self.process_linear_scores()

            if historical_data is not None and not historical_data.empty:
                # 计算变化趋势
                trend_analysis = {}
                for trait in current_scores.index:
                    if trait in historical_data.columns:
                        current = current_scores.loc[trait, 'mean']
                        historical = historical_data[trait].mean()
                        change = current - historical
                        change_pct = (change / historical * 100) if historical != 0 else 0

                        trend_analysis[trait] = {
                            'current': round(current, 2),
                            'historical': round(historical, 2),
                            'change': round(change, 2),
                            'change_pct': round(change_pct, 2),
                            'trend': 'improving' if change > 0 else 'declining' if change < 0 else 'stable'
                        }

                return pd.DataFrame(trend_analysis).T
            else:
                # 没有历史数据，只返回当前数据
                return current_scores

        except Exception as e:
            logger.error(f"生成趋势分析失败: {e}")
            return pd.DataFrame()

    def export_results(self, output_path: Path) -> bool:
        """
        导出处理结果

        Args:
            output_path: 输出路径

        Returns:
            是否成功导出
        """
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # 导出线性评分汇总
                linear_scores = self.process_linear_scores()
                if not linear_scores.empty:
                    linear_scores.to_excel(writer, sheet_name='线性评分汇总')

                # 导出缺陷性状分析
                defects = self.analyze_defects()
                if defects:
                    pd.DataFrame(defects).T.to_excel(writer, sheet_name='缺陷性状分析')

                # 导出综合评分
                composite = self.calculate_composite_scores()
                if not composite.empty:
                    composite.to_excel(writer, sheet_name='综合评分')

                # 导出改进建议
                improvements = self.identify_improvement_areas()
                if improvements:
                    pd.DataFrame(improvements).to_excel(writer, sheet_name='改进建议', index=False)

            logger.info(f"结果已导出到: {output_path}")
            return True

        except Exception as e:
            logger.error(f"导出结果失败: {e}")
            return False