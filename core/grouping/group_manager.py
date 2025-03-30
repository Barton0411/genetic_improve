import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import Dict, List, Tuple
import os

class GroupManager:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        # 获取 GENETIC_IMPROVE 项目根目录
        self.root_dir = self.get_root_dir()
        self.today = datetime.now()
        self.cow_data = None
        self.strategy = None
        
    @staticmethod
    def get_root_dir() -> Path:
        """获取 GENETIC_IMPROVE 项目根目录"""
        # 从环境变量中获取项目根目录
        root_dir = os.getenv('GENETIC_IMPROVE_ROOT')
        if root_dir:
            return Path(root_dir)
            
        # 如果环境变量未设置，尝试从当前文件位置推断
        current_file = Path(__file__)
        # 假设当前文件在 GENETIC_IMPROVE/core/grouping/ 目录下
        if 'core' in current_file.parts and 'grouping' in current_file.parts:
            return current_file.parent.parent.parent
        else:
            # 如果无法推断，使用当前工作目录
            return Path.cwd()
        
    def load_data(self):
        """加载牛只数据"""
        index_file = self.project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
        if not index_file.exists():
            raise FileNotFoundError("请先进行牛只指数计算排名")
        self.cow_data = pd.read_excel(index_file)
        
    def load_strategy(self, strategy_name: str):
        """加载分组策略"""
        strategy_file = self.root_dir / "config" / "group_strategies" / f"{strategy_name}.json"
        if not strategy_file.exists():
            raise FileNotFoundError(f"找不到分组策略文件：{strategy_name}")
            
        with open(strategy_file, 'r', encoding='utf-8') as f:
            self.strategy = json.load(f)

    @classmethod
    def save_strategy(cls, strategy_name: str, strategy_data: dict):
        """保存分组策略到GENETIC_IMPROVE项目的全局配置目录"""
        root_dir = cls.get_root_dir()
        strategies_dir = root_dir / "config" / "group_strategies"
        strategies_dir.mkdir(parents=True, exist_ok=True)
        
        strategy_file = strategies_dir / f"{strategy_name}.json"
        with open(strategy_file, 'w', encoding='utf-8') as f:
            json.dump(strategy_data, f, ensure_ascii=False, indent=2)
            
    @classmethod
    def list_strategies(cls) -> List[str]:
        """列出所有可用的分组策略"""
        root_dir = cls.get_root_dir()
        strategies_dir = root_dir / "config" / "group_strategies"
        if not strategies_dir.exists():
            return []
            
        return [f.stem for f in strategies_dir.glob("*.json")]
            
    @classmethod
    def delete_strategy(cls, strategy_name: str):
        """删除指定的分组策略"""
        root_dir = cls.get_root_dir()
        strategy_file = root_dir / "config" / "group_strategies" / f"{strategy_name}.json"
        if strategy_file.exists():
            strategy_file.unlink()
            
    def calculate_age_days(self, birth_date) -> int:
        """计算日龄"""
        try:
            if pd.isna(birth_date):
                return 0
            birth_date = pd.to_datetime(birth_date)
            return (self.today - birth_date).days
        except:
            return 0
            
    def calculate_dim(self, calving_date) -> int:
        """计算泌乳天数"""
        try:
            if pd.isna(calving_date):
                return 0
            calving_date = pd.to_datetime(calving_date)
            return (self.today - calving_date).days
        except:
            return 0

    def is_pregnant(self, status: str) -> bool:
        """判断是否已孕"""
        return status in ["初检孕", "复检孕"]

    def is_sexed_method(self, method: str) -> bool:
        """判断是否为性控方法"""
        return method in ["性控冻精", "超级性控"]

    def group_special_cows(self) -> pd.DataFrame:
        """对已孕牛和难孕牛进行分组"""
        # 筛选在场的母牛
        df = self.cow_data[
            (self.cow_data['是否在场'] == '是') & 
            (self.cow_data['sex'] == '母')
        ].copy()
        
        # 计算日龄和泌乳天数
        df['age_days'] = df['birth_date'].apply(self.calculate_age_days)
        df['dim'] = df['calving_date'].apply(self.calculate_dim)
        
        # 标记已孕和难孕
        df['is_pregnant'] = df['repro_status'].apply(self.is_pregnant)
        
        # 确保 group 列是字符串类型
        if 'group' not in df.columns:
            df['group'] = None
        df['group'] = df['group'].astype('object')
        
        # 分别处理后备牛和成母牛
        heifer_mask = df['lac'] == 0
        cow_mask = df['lac'] > 0
        
        # 后备牛难孕条件：日龄 >= 18*30.8 且未孕
        mask = heifer_mask & (df['age_days'] >= 18*30.8) & ~df['is_pregnant']
        df.loc[mask, 'group'] = '后备牛+难孕牛+非性控'
        
        # 后备牛已孕
        mask = heifer_mask & df['is_pregnant']
        df.loc[mask, 'group'] = '后备牛+已孕牛+非性控'
        
        # 成母牛难孕条件：DIM >= 150 且未孕
        mask = cow_mask & (df['dim'] >= 150) & ~df['is_pregnant']
        df.loc[mask, 'group'] = '成母牛+难孕牛+非性控'
        
        # 成母牛已孕
        mask = cow_mask & df['is_pregnant']
        df.loc[mask, 'group'] = '成母牛+已孕牛+非性控'
        
        return df

    def group_by_cycle(self, df: pd.DataFrame) -> pd.DataFrame:
        """按周期分组"""
        if not self.strategy:
            raise ValueError("请先加载分组策略")
            
        cycle_months = self.strategy['params']['cycle_months']
        reserve_age = self.strategy['params']['reserve_age']
        
        # 确保 cycle 列存在
        if 'cycle' not in df.columns:
            df['cycle'] = None
        
        # 处理后备牛周期
        heifer_mask = (df['lac'] == 0) & df['group'].isna()
        for i in range(1, 5):  # 处理4个周期
            cycle_start = reserve_age - cycle_months * i
            cycle_end = reserve_age - cycle_months * (i-1) if i > 1 else 18*30.8
            
            mask = heifer_mask & (df['age_days'] >= cycle_start) & (df['age_days'] < cycle_end)
            df.loc[mask, 'cycle'] = i
            
        # 处理成母牛周期
        cow_mask = (df['lac'] > 0) & df['group'].isna()
        for i in range(1, 5):  # 处理4个周期
            cycle_date = self.today - timedelta(days=cycle_months*i*30)
            mask = cow_mask & (pd.to_datetime(df['calving_date']) >= cycle_date)
            df.loc[mask, 'cycle'] = i
            
        return df

    def assign_breeding_methods(self, df: pd.DataFrame) -> pd.DataFrame:
        """分配配种方法（性控/非性控）"""
        if not self.strategy:
            raise ValueError("请先加载分组策略")
            
        # 获取策略表数据
        strategy_table = pd.DataFrame(self.strategy['strategy_table'])
        
        # 分别处理后备牛和成母牛
        for cow_type in ['后备牛', '成母牛']:
            type_strategies = strategy_table[strategy_table['group'].str.startswith(cow_type)]
            
            # 对每个周期进行处理
            for cycle in range(1, 5):
                cycle_mask = (df['cycle'] == cycle) & df['group'].isna()
                if cow_type == '后备牛':
                    cow_mask = (df['lac'] == 0)
                else:
                    cow_mask = (df['lac'] > 0)
                    
                combined_mask = cycle_mask & cow_mask
                if not combined_mask.any():
                    continue
                    
                # 计算该周期牛只的排名百分比
                cycle_cows = df[combined_mask].copy()
                if len(cycle_cows) > 0:  # 只在有牛只的情况下计算排名
                    cycle_cows['rank_pct'] = cycle_cows['ranking'].rank(pct=True) * 100
                    
                    # 累计比例用于分组
                    cum_ratio = 0
                    for _, strategy_row in type_strategies.iterrows():
                        ratio = strategy_row['ratio']
                        if ratio == 0:
                            continue
                            
                        # 确定该组使用性控的配种次数
                        sexed_services = [
                            i+1 for i, method in enumerate(strategy_row['breeding_methods'])
                            if self.is_sexed_method(method)
                        ]
                        
                        # 在排名范围内的牛只
                        rank_mask = (
                            (cycle_cows['rank_pct'] > cum_ratio) & 
                            (cycle_cows['rank_pct'] <= cum_ratio + ratio)
                        )
                        
                        # 根据配种次数决定使用性控还是非性控
                        services_mask = cycle_cows['services_time'].isin(
                            [s-1 for s in sexed_services]  # services_time从0开始计数
                        )
                        
                        # 更新分组
                        use_sexed_mask = rank_mask & services_mask
                        df.loc[cycle_cows[use_sexed_mask].index, 'group'] = f'{cow_type}+第{cycle}周期+性控'
                        df.loc[cycle_cows[~use_sexed_mask].index, 'group'] = f'{cow_type}+第{cycle}周期+非性控'
                        
                        cum_ratio += ratio
                    
                    # 剩余未分组的牛只使用非性控
                    df.loc[cycle_cows[df.loc[cycle_cows.index, 'group'].isna()].index, 'group'] = f'{cow_type}+第{cycle}周期+非性控'
        
        return df

    def apply_grouping(self, strategy_name: str) -> pd.DataFrame:
        """应用分组策略"""
        # 1. 加载数据
        self.load_data()
        self.load_strategy(strategy_name)
        
        # 2. 特殊组分组（已孕牛和难孕牛）
        df = self.group_special_cows()
        
        # 3. 周期分组
        df = self.group_by_cycle(df)
        
        # 4. 分配配种方法
        df = self.assign_breeding_methods(df)
        
        # 5. 将分组结果更新到原始文件
        index_file = self.project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
        
        # 读取原始文件
        original_df = pd.read_excel(index_file)
        
        # 更新分组列
        original_df['group'] = None  # 先清空原有的分组
        for idx, row in df.iterrows():
            if not pd.isna(row['group']):
                original_df.loc[original_df.index == idx, 'group'] = row['group']
        
        # 保存回原文件
        original_df.to_excel(index_file, index=False)
        
        return df

    def get_group_summary(self) -> pd.DataFrame:
        """获取分组统计信息"""
        if self.cow_data is None:
            raise ValueError("请先应用分组策略")
            
        # 直接从原始文件读取最新的分组信息
        index_file = self.project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
        df = pd.read_excel(index_file)
        
        summary = df.groupby('group').agg({
            'cow_id': 'count'  # 统计每组牛只数量
        }).reset_index()
        
        summary.columns = ['分组', '数量']
        # 删除空分组
        summary = summary.dropna(subset=['分组'])
        return summary 