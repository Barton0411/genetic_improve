"""
个体选配领域模型
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import date
from enum import Enum


class SemenType(Enum):
    """冻精类型"""
    REGULAR = "常规"
    SEXED = "性控"


class GeneStatus(Enum):
    """隐性基因状态"""
    SAFE = "Safe"
    RISK = "Risk"
    UNKNOWN = "Unknown"


@dataclass
class Cow:
    """母牛实体"""
    id: str
    group: str
    index_score: float
    breed: str = "荷斯坦"
    birth_date: Optional[date] = None
    sex: str = "母"
    is_present: bool = True
    
    def __post_init__(self):
        """确保ID是字符串"""
        self.id = str(self.id)


@dataclass
class Bull:
    """公牛实体"""
    id: str
    semen_type: SemenType
    index_score: float
    inventory: int
    tpi: Optional[float] = None
    nm_score: Optional[float] = None
    classification: Optional[str] = None
    
    def __post_init__(self):
        """确保ID是字符串，处理类型"""
        self.id = str(self.id)
        if isinstance(self.semen_type, str):
            self.semen_type = SemenType.REGULAR if self.semen_type == "常规" else SemenType.SEXED


@dataclass
class PairingScore:
    """配对得分"""
    cow_id: str
    bull_id: str
    offspring_score: float
    inbreeding_coeff: float
    gene_status: GeneStatus
    
    def meets_constraints(self, inbreeding_threshold: float = 6.25, 
                         control_defect_genes: bool = True) -> bool:
        """检查是否满足约束条件"""
        if self.inbreeding_coeff > inbreeding_threshold:
            return False
        if control_defect_genes and self.gene_status == GeneStatus.RISK:
            return False
        return True


@dataclass
class MatingConstraints:
    """选配约束条件"""
    inbreeding_threshold: float = 6.25  # 近交系数阈值(%)
    control_defect_genes: bool = True    # 是否控制隐性基因
    min_offspring_score: Optional[float] = None  # 最小后代得分


@dataclass
class AllocationResult:
    """分配结果"""
    cow_id: str
    bull_id: str
    choice_num: int  # 1选/2选/3选
    semen_type: SemenType
    offspring_score: float
    inbreeding_coeff: float
    gene_status: GeneStatus


@dataclass
class MatingRecommendation:
    """选配推荐"""
    cow_id: str
    recommendations: Dict[SemenType, List[PairingScore]]  # 按冻精类型分组的推荐列表
    
    def get_top_choices(self, semen_type: SemenType, n: int = 3) -> List[PairingScore]:
        """获取前N个推荐"""
        if semen_type in self.recommendations:
            return self.recommendations[semen_type][:n]
        return []


@dataclass
class GroupAllocationSummary:
    """分组分配汇总"""
    group_name: str
    total_cows: int
    allocated_cows: int
    unallocated_cows: int
    allocation_details: Dict[str, int]  # bull_id -> count
    
    @property
    def allocation_rate(self) -> float:
        """分配率"""
        return self.allocated_cows / self.total_cows if self.total_cows > 0 else 0.0


@dataclass
class BullUsageSummary:
    """公牛使用汇总"""
    bull_id: str
    semen_type: SemenType
    original_inventory: int
    used_count: int
    remaining_inventory: int
    
    @property
    def usage_rate(self) -> float:
        """使用率"""
        return self.used_count / self.original_inventory if self.original_inventory > 0 else 0.0


@dataclass
class MatingResult:
    """选配结果"""
    allocations: List[AllocationResult]
    group_summaries: List[GroupAllocationSummary]
    bull_summaries: List[BullUsageSummary]
    unallocated_cows: List[str]  # 未分配的母牛ID列表
    
    def to_dataframe(self):
        """转换为DataFrame格式（用于Excel导出）"""
        import pandas as pd
        
        # 创建分配结果表
        allocation_data = []
        for alloc in self.allocations:
            allocation_data.append({
                'cow_id': alloc.cow_id,
                'bull_id': alloc.bull_id,
                'choice_num': alloc.choice_num,
                'semen_type': alloc.semen_type.value,
                'offspring_score': alloc.offspring_score,
                'inbreeding_coeff': alloc.inbreeding_coeff,
                'gene_status': alloc.gene_status.value
            })
        
        return pd.DataFrame(allocation_data)