"""
分组管理模块
"""

import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import Dict, List, Tuple
import os

class GroupManager:
    def __init__(self, project_path: Path):
        """
        初始化分组管理器
        
        Args:
            project_path: 项目路径
        """
        if project_path is None:
            raise ValueError("项目路径不能为空")
            
        if not isinstance(project_path, Path):
            project_path = Path(project_path)
            
        if not project_path.exists():
            raise ValueError(f"项目路径不存在：{project_path}")
            
        self.project_path = project_path
        self.today = datetime.now()
        self.cow_data = None
        self.strategy = None
        
        # 设置指数文件路径
        self.index_file = project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
        
        # 获取项目根目录
        try:
            self.root_dir = self.get_root_dir()
        except Exception as e:
            print(f"警告：获取项目根目录失败：{str(e)}，使用当前工作目录")
            self.root_dir = Path.cwd()
        
    @staticmethod
    def get_root_dir() -> Path:
        """获取 GENETIC_IMPROVE 项目根目录"""
        try:
            # 从环境变量中获取项目根目录
            root_dir = os.getenv('GENETIC_IMPROVE_ROOT')
            if root_dir:
                return Path(root_dir)
                
            # 如果环境变量未设置，尝试从当前文件位置推断
            current_file = Path(__file__).resolve()  # 使用resolve()获取绝对路径
            
            # 检查当前文件是否存在且在正确的目录结构中
            if current_file.exists() and 'core' in current_file.parts and 'grouping' in current_file.parts:
                root_dir = current_file.parent.parent.parent
                if root_dir.exists():  # 确保根目录存在
                    return root_dir
            
            # 如果无法推断，使用当前工作目录
            cwd = Path.cwd()
            print(f"警告：无法确定项目根目录，使用当前工作目录：{cwd}")
            return cwd
            
        except Exception as e:
            print(f"获取根目录时发生错误: {str(e)}，使用当前工作目录作为替代")
            return Path.cwd()
        
    def load_data(self):
        """加载牛只数据"""
        if not self.index_file.exists():
            raise FileNotFoundError("请先进行牛只指数计算排名")
        self.cow_data = pd.read_excel(self.index_file)
        # 确保cow_id保持为字符串格式（修复pandas自动转换为数字的问题）
        if 'cow_id' in self.cow_data.columns:
            self.cow_data['cow_id'] = self.cow_data['cow_id'].astype(str)
        
    def load_strategy(self, strategy_name: str):
        """加载分组策略"""
        try:
            # 获取根目录
            root_dir = self.get_root_dir()
            if not root_dir:
                raise ValueError("无法获取项目根目录")
                
            # 构建策略文件路径
            strategy_file = root_dir / "config" / "group_strategies" / f"{strategy_name}.json"
            
            # 检查策略文件是否存在
            if not strategy_file.exists():
                raise FileNotFoundError(f"找不到分组策略文件：{strategy_name}")
                
            # 尝试读取和解析策略文件
            try:
                with open(strategy_file, 'r', encoding='utf-8') as f:
                    self.strategy = json.load(f)
                    
                # 验证策略数据结构
                if not isinstance(self.strategy, dict):
                    raise ValueError("策略文件格式错误：应为JSON对象")
                    
                if 'params' not in self.strategy:
                    raise ValueError("策略文件缺少params字段")
                    
                if 'strategy_table' not in self.strategy:
                    raise ValueError("策略文件缺少strategy_table字段")
                    
            except json.JSONDecodeError as e:
                raise ValueError(f"策略文件JSON格式错误：{str(e)}")
                
        except Exception as e:
            print(f"加载策略时发生错误: {str(e)}")
            raise

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
            return (self.today - calving_date).dt.days
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
        
        # 将产犊日期转换为datetime类型
        df['calving_date'] = pd.to_datetime(df['calving_date'])
        
        for i in range(1, 5):  # 处理4个周期
            cycle_end = self.today - timedelta(days=cycle_months*(i-1)*30)
            cycle_start = self.today - timedelta(days=cycle_months*i*30)
            
            mask = cow_mask & (df['calving_date'] >= cycle_start) & (df['calving_date'] < cycle_end)
            df.loc[mask, 'cycle'] = i
            
        return df

    def assign_breeding_methods(self, df: pd.DataFrame) -> pd.DataFrame:
        """分配配种方法（性控/非性控）"""
        if not self.strategy:
            raise ValueError("请先加载分组策略")
            
        # 获取策略表数据
        strategy_table = self.strategy['strategy_table']
        
        # 对每个分组策略进行处理
        for group_strategy in strategy_table:
            group_name = group_strategy['group']  # 例如：成母牛A
            ratio = group_strategy['ratio']  # 比例
            breeding_methods = group_strategy['breeding_methods']  # 配种方法列表
            
            # 获取该组的所有牛（通过cycle匹配）
            if '成母牛' in group_name:
                base_mask = (df['lac'] > 0) & df['group'].isna()
            else:  # 后备牛
                base_mask = (df['lac'] == 0) & df['group'].isna()
                
            # 根据ranking排序并选择指定比例的牛
            group_df = df[base_mask].sort_values('ranking')
            count = int(len(group_df) * ratio / 100)
            selected_indices = group_df.index[:count]
            
            # 根据配种次数分配配种方法
            for idx in selected_indices:
                services = df.loc[idx, 'services_time']
                if pd.isna(services):
                    services = 0
                    
                # 获取对应的配种方法（根据已配种次数确定下次使用什么）
                # services=0表示还没配过，下次是第1次，对应索引0
                # services=1表示已配1次，下次是第2次，对应索引1
                method_idx = min(int(services), len(breeding_methods)-1)
                method = breeding_methods[method_idx]
                
                # 更新分组信息
                cow_type = "成母牛" if df.loc[idx, 'lac'] > 0 else "后备牛"
                cycle = df.loc[idx, 'cycle']
                is_sexed = self.is_sexed_method(method)
                
                df.loc[idx, 'group'] = f"{cow_type}+第{cycle}周期+{'性控' if is_sexed else '非性控'}"
                
        # 处理未分配的牛（默认使用非性控）
        mask = df['group'].isna() & df['cycle'].notna()
        cow_type_mask = df['lac'] > 0
        df.loc[mask & cow_type_mask, 'group'] = df.loc[mask & cow_type_mask].apply(
            lambda x: f"成母牛+第{int(x['cycle'])}周期+非性控", axis=1
        )
        df.loc[mask & ~cow_type_mask, 'group'] = df.loc[mask & ~cow_type_mask].apply(
            lambda x: f"后备牛+第{int(x['cycle'])}周期+非性控", axis=1
        )
        
        return df

    def apply_temp_strategy(self, strategy: dict, progress_callback=None, grouping_mode: str = None) -> pd.DataFrame:
        """
        应用临时分组策略，返回分组结果

        Args:
            strategy: 分组策略
            progress_callback: 进度回调函数
            grouping_mode: 分组模式 ('manual' 或 'auto')

        Returns:
            分组结果DataFrame
        """
        self.strategy = strategy

        # 显示进度
        if progress_callback:
            progress_callback.set_task_info("正在读取指数计算结果...")
            progress_callback.update_info("开始应用分组策略...")
            progress_callback.update_progress(5)

        # 读取指数计算结果
        if not self.index_file.exists():
            raise FileNotFoundError("请先进行牛只指数计算排名")

        try:
            df = pd.read_excel(self.index_file)
            # 确保cow_id保持为字符串格式（修复pandas自动转换为数字的问题）
            if 'cow_id' in df.columns:
                df['cow_id'] = df['cow_id'].astype(str)
            if progress_callback:
                progress_callback.update_info(f"成功读取指数文件: {self.index_file.name}")
                progress_callback.update_info(f"原始数据: {len(df)} 条记录")
        except Exception as e:
            raise Exception(f"读取指数计算结果失败: {str(e)}")

        if progress_callback:
            progress_callback.set_task_info("正在筛选在场母牛...")
            progress_callback.update_progress(10)

        # 筛选在场的母牛
        original_count = len(df)
        df = df[(df['是否在场'] == '是') & (df['sex'] == '母')].copy()
        filtered_count = len(df)

        if progress_callback:
            progress_callback.update_info(f"筛选在场母牛: {original_count} -> {filtered_count} 头")

        # 检查是否存在手动分组
        has_manual_groups = False
        manual_grouped_count = 0
        empty_group_count = 0

        # 如果明确指定了分组模式，优先使用指定的模式
        if grouping_mode == 'manual':
            # 强制使用手动分组模式
            has_manual_groups = True
            if progress_callback:
                progress_callback.update_info("使用手动分组模式")
            # 处理手动分组模式下的group列
            if 'group' not in df.columns:
                df['group'] = '未分组'
                empty_group_count = len(df)
            else:
                # 检查并处理现有group列
                for idx in df.index:
                    if pd.notna(df.at[idx, 'group']):
                        group_val = str(df.at[idx, 'group']).strip()
                        if group_val == 'nan' or group_val == '':
                            df.at[idx, 'group'] = '未分组'
                            empty_group_count += 1
                        else:
                            manual_grouped_count += 1
                    else:
                        df.at[idx, 'group'] = '未分组'
                        empty_group_count += 1
        elif grouping_mode == 'auto':
            # 强制使用自动分组模式
            has_manual_groups = False
            if progress_callback:
                progress_callback.update_info("使用自动分组模式")
            # 清空现有的group列，以便重新分组
            df['group'] = None
            # 自动分组模式下，跳过所有后续检测，直接进入自动分组逻辑
        elif grouping_mode is None and 'group' in df.columns:
            # 只有在没有明确指定模式时，才自动检测分组
            # 检查是否有任何手动分组数据（非NaN的值）
            # 只要有任何一个单元格有值（包括空字符串），就认为是手动分组
            non_null_mask = df['group'].notna()
            has_any_value = non_null_mask.any()

            if has_any_value:
                has_manual_groups = True

                # 处理group列的值
                for idx in df.index:
                    if pd.notna(df.at[idx, 'group']):
                        group_val = str(df.at[idx, 'group']).strip()
                        if group_val == 'nan':  # pandas可能将NaN转为字符串'nan'
                            df.at[idx, 'group'] = '未分组'
                            empty_group_count += 1
                        elif group_val == '':  # 空字符串
                            df.at[idx, 'group'] = '未分组'  # 将空字符串标记为"未分组"
                            empty_group_count += 1
                        else:
                            manual_grouped_count += 1
                    else:
                        # NaN值，标记为未分组
                        df.at[idx, 'group'] = '未分组'
                        empty_group_count += 1

                print(f"检测到手动分组模式: {manual_grouped_count} 头牛已手动分组, {empty_group_count} 头牛未分组")
                print("将跳过所有自动分组，保留用户的手动分组设置")
                if progress_callback:
                    progress_callback.update_info(f"检测到手动分组: 已分组 {manual_grouped_count} 头, 未分组 {empty_group_count} 头")
                    progress_callback.update_info("使用手动分组模式，跳过自动分组")
            else:
                # group列存在但全是空的，进行自动分组
                df['group'] = None
                has_manual_groups = False
                print("group列存在但为空，将进行自动分组")
                if progress_callback:
                    progress_callback.update_info("未检测到分组数据，将进行自动分组")
        elif grouping_mode is None:
            # 只有在没有明确指定模式且group列不存在时，才创建并进行自动分组
            df['group'] = None
            print("未检测到group列，将进行自动分组")
            if progress_callback:
                progress_callback.update_info("未检测到手动分组，将进行自动分组")

        # 如果检测到手动分组，直接返回，不进行任何自动分组
        if has_manual_groups:
            print("\n===== 手动分组模式 =====")
            print(f"已手动分组: {manual_grouped_count} 头")
            print(f"未分组: {empty_group_count} 头")
            print("保持所有手动分组设置，不进行自动分组")

            if progress_callback:
                progress_callback.set_task_info("手动分组模式，跳过自动分组")
                progress_callback.update_progress(100)

            # 统计分组情况
            group_stats = df['group'].value_counts(dropna=False)
            print("\n===== 分组统计 =====")
            for group, count in group_stats.items():
                if pd.isna(group) or group is None:
                    print(f"未分组(空值): {count} 头")  # 这种情况应该不会出现，因为我们已经处理了
                else:
                    print(f"{group}: {count} 头")

            return df

        if progress_callback:
            progress_callback.set_task_info("正在计算日龄和DIM...")
            progress_callback.update_progress(15)

        # 计算日龄和DIM
        today = datetime.now()
        df['birth_date'] = pd.to_datetime(df['birth_date'], errors='coerce')
        df['calving_date'] = pd.to_datetime(df['calving_date'], errors='coerce')
        
        # 计算日龄 - 正确处理NaN值
        df['日龄'] = df['birth_date'].apply(
            lambda x: (today - x).days if pd.notna(x) else None
        )
        
        # 计算DIM - 正确处理NaN值
        df['DIM'] = df['calving_date'].apply(
            lambda x: (today - x).days if pd.notna(x) else None
        )
        
        # 检查日龄计算是否有异常值
        invalid_age_mask = df['日龄'].notna() & ((df['日龄'] < 0) | (df['日龄'] > 3650))  # 超过10年的日龄视为异常
        if invalid_age_mask.any():
            warning_msg = f"发现 {invalid_age_mask.sum()} 头牛的日龄异常"
            print(f"警告：{warning_msg}")
            if progress_callback:
                progress_callback.update_info(f"警告: {warning_msg}")
            print(df[invalid_age_mask][['cow_id', 'birth_date', '日龄']].head())
        
        print("日龄和DIM计算完成")
        if progress_callback:
            progress_callback.update_info("日龄和DIM计算完成")
        
        if progress_callback:
            progress_callback.set_task_info("正在区分后备牛和成母牛...")
            progress_callback.update_progress(20)
        
        # 区分后备牛和成母牛
        heifer_mask = df['lac'] == 0  # 后备牛
        mature_mask = df['lac'] > 0   # 成母牛
        
        heifer_count = heifer_mask.sum()
        mature_count = mature_mask.sum()
        
        total_cows = len(df)
        if progress_callback:
            progress_callback.update_info(f"牛只分类完成 ({total_cows}头): 后备牛 {heifer_count} 头, 成母牛 {mature_count} 头")
        
        if progress_callback:
            progress_callback.set_task_info("正在处理后备牛分组...")
            progress_callback.update_progress(30)
        
        # 处理后备牛
        heifer_df = df[heifer_mask].copy()

        # 标记已孕和难孕牛 - 先处理NaN值
        pregnant_mask = heifer_df['repro_status'].fillna('').isin(['初检孕', '复检孕'])
        # 日龄中的None/NaN值视为0，确保布尔表达式有效性
        valid_age_mask = heifer_df['日龄'].notna()
        difficult_mask = valid_age_mask & (heifer_df['日龄'] >= 18 * 30.8) & ~pregnant_mask

        # 分配特殊组
        heifer_df.loc[pregnant_mask, 'group'] = '后备牛已孕牛'
        heifer_df.loc[difficult_mask, 'group'] = '后备牛难孕牛'
        
        pregnant_count = pregnant_mask.sum()
        difficult_count = difficult_mask.sum()
        
        if progress_callback:
            processed_heifers = pregnant_count + difficult_count
            progress_callback.update_info(f"后备牛特殊分组 ({processed_heifers}/{heifer_count}头): 已孕 {pregnant_count} 头, 难孕 {difficult_count} 头")
        
        print(f"后备牛已孕牛数量：{pregnant_count}头")
        print(f"后备牛难孕牛数量：{difficult_count}头")
        
        # 处理普通后备牛（排除已孕和难孕）
        normal_mask = ~(pregnant_mask | difficult_mask)
        heifer_normal = heifer_df[normal_mask]
        normal_count = len(heifer_normal)
        
        if progress_callback:
            progress_callback.update_info(f"待分组后备牛: ({normal_count}/{heifer_count}头) 需要按周期分组")
        
        print(f"普通后备牛数量：{normal_count}头")
        print(f"后备牛总数量：{len(heifer_df)}头")
        
        if progress_callback:
            progress_callback.set_task_info("正在计算后备牛周期分组...")
            progress_callback.update_progress(40)
        
        # 获取策略参数
        reserve_age = strategy['params']['reserve_age']
        cycle_days = strategy['params']['cycle_days']
        
        if progress_callback:
            progress_callback.update_info(f"分组参数: 后备牛开配日龄 {reserve_age} 天, 选配周期 {cycle_days} 天")
        
        print(f"\n使用分组参数：后备牛开配日龄={reserve_age}天，选配周期={cycle_days}天")
        
        # 计算需要的周期数（最多处理4个周期）
        max_age = 18 * 30.8  # 18个月
        cycle_count = min(4, int((max_age - (reserve_age - 4 * cycle_days)) / cycle_days) + 1)
        
        if progress_callback:
            progress_callback.update_info(f"计算周期数: 共 {cycle_count} 个周期")
        
        print(f"计算需要的周期数: {cycle_count}")
        
        # 统计各周期牛只数量
        heifer_cycles_count = {}
        
        # 重新实现周期分配逻辑
        for i in range(1, cycle_count + 1):
            cycle_start = reserve_age - cycle_days * i
            cycle_end = reserve_age - cycle_days * (i-1) if i > 1 else 18 * 30.8
            
            # 确保有效的布尔掩码
            valid_age_data = heifer_normal['日龄'].notna()
            cycle_mask = valid_age_data & (heifer_normal['日龄'] >= cycle_start) & (heifer_normal['日龄'] < cycle_end)
            heifer_df.loc[heifer_normal[cycle_mask].index, 'group'] = f'后备牛第{i}周期'
            heifer_cycles_count[i] = cycle_mask.sum()
            
            cycle_info = f"后备牛第{i}周期 (日龄 {cycle_start}-{cycle_end}): {cycle_mask.sum()} 头"
            print(cycle_info)
            if progress_callback:
                progress_callback.update_info(cycle_info)
        
        if progress_callback:
            progress_callback.set_task_info("正在处理成母牛分组...")
            progress_callback.update_progress(60)
            print("\n开始处理成母牛分组...")
        
        # 处理成母牛
        mature_df = df[mature_mask].copy()
        # 标记已孕和难孕牛 - 先处理NaN值
        pregnant_mask = mature_df['repro_status'].fillna('').isin(['初检孕', '复检孕'])
        # 难孕牛：有DIM数据且DIM >= 600天且未孕（根据实际数据调整阈值）
        # DIM为空的牛不算难孕牛，应该归为未孕牛
        difficult_mask = mature_df['DIM'].notna() & (mature_df['DIM'] >= 600) & ~pregnant_mask

        # 分配周期
        mature_df.loc[pregnant_mask, 'group'] = '成母牛已孕牛'
        mature_df.loc[difficult_mask, 'group'] = '成母牛难孕牛'

        # 标记正常成母牛为未孕牛（而不是按周期分）
        normal_mask = ~(pregnant_mask | difficult_mask)
        mature_df.loc[normal_mask, 'group'] = '成母牛未孕牛'
        
        pregnant_count = pregnant_mask.sum()
        difficult_count = difficult_mask.sum()
        normal_count = normal_mask.sum()
        
        # 计算基础未孕牛（所有非已孕的牛）
        base_unpregnant_mask = ~pregnant_mask
        base_unpregnant_count = base_unpregnant_mask.sum()
        
        # 调试：分析DIM分布
        print(f"\n=== 成母牛分组逻辑分析 ===")
        print(f"总成母牛: {len(mature_df)} 头")
        print(f"已孕牛(初检孕+复检孕): {pregnant_count} 头")
        print(f"基础未孕牛(除已孕牛外的所有牛): {base_unpregnant_count} 头")
        
        if base_unpregnant_count > 0:
            base_unpregnant_df = mature_df[base_unpregnant_mask]
            valid_dim_in_unpregnant = base_unpregnant_df['DIM'].notna()
            invalid_dim_in_unpregnant = base_unpregnant_df['DIM'].isna()
            
            print(f"\n=== 基础未孕牛DIM分析 ===")
            print(f"有DIM数据的基础未孕牛: {valid_dim_in_unpregnant.sum()} 头")
            print(f"DIM为空的基础未孕牛: {invalid_dim_in_unpregnant.sum()} 头 -> 这些将成为未孕牛")
            
            if valid_dim_in_unpregnant.sum() > 0:
                dim_data = base_unpregnant_df[valid_dim_in_unpregnant]['DIM']
                print(f"基础未孕牛DIM范围: {dim_data.min():.1f} - {dim_data.max():.1f} 天")
                dim_ge_150 = (dim_data >= 150).sum()
                dim_lt_150 = (dim_data < 150).sum()
                dim_ge_600 = (dim_data >= 600).sum()
                dim_lt_600 = (dim_data < 600).sum()
                print(f"基础未孕牛中DIM >= 600的: {dim_ge_600} 头 -> 这些将成为难孕牛")
                print(f"基础未孕牛中DIM < 600的: {dim_lt_600} 头 -> 这些将成为未孕牛")
                
                total_unpregnant_will_be = dim_lt_600 + invalid_dim_in_unpregnant.sum()
                print(f"预计未孕牛总数: {total_unpregnant_will_be} 头 (DIM<600的 + DIM为空的)")
                
                # 显示DIM分布区间
                if dim_ge_150 > 0:
                    dim_150_200 = ((dim_data >= 150) & (dim_data < 200)).sum()
                    dim_200_300 = ((dim_data >= 200) & (dim_data < 300)).sum()
                    dim_300_400 = ((dim_data >= 300) & (dim_data < 400)).sum()
                    dim_400_plus = (dim_data >= 400).sum()
                    
                    print(f"难孕牛DIM分布详情:")
                    print(f"  150-200天: {dim_150_200} 头")
                    print(f"  200-300天: {dim_200_300} 头") 
                    print(f"  300-400天: {dim_300_400} 头")
                    print(f"  400天以上: {dim_400_plus} 头")
        
        # 详细分析repro_status分布
        print(f"\n=== 成母牛繁育状态分析 ===")
        repro_status_counts = mature_df['repro_status'].fillna('空值').value_counts()
        print("繁育状态分布:")
        for status, count in repro_status_counts.items():
            print(f"  {status}: {count} 头")
        
        # 分析难孕牛的具体情况
        difficult_cows = mature_df[difficult_mask]
        if len(difficult_cows) > 0:
            print(f"\n=== 难孕牛详细分析 (共{len(difficult_cows)}头) ===")
            difficult_repro_counts = difficult_cows['repro_status'].fillna('空值').value_counts()
            print("难孕牛的繁育状态分布:")
            for status, count in difficult_repro_counts.items():
                print(f"  {status}: {count} 头")
            print(f"难孕牛DIM范围: {difficult_cows['DIM'].min():.1f} - {difficult_cows['DIM'].max():.1f} 天")
        
        mature_info = f"成母牛分组完成 ({len(mature_df)}头): 已孕 {pregnant_count} 头, 难孕 {difficult_count} 头, 未孕 {normal_count} 头"

        print(f"成母牛已孕牛数量：{pregnant_count}头")
        print(f"成母牛难孕牛数量：{difficult_count}头")
        print(f"成母牛未孕牛数量：{normal_count}头")
        print(f"成母牛总数量：{len(mature_df)}头")

        if progress_callback:
            progress_callback.update_info(mature_info)
        
        if progress_callback:
            progress_callback.set_task_info("正在处理遗传物质分配...")
            progress_callback.update_progress(80)
            print("\n开始处理遗传物质分配...")
        
        # 合并结果
        result_df = pd.concat([heifer_df, mature_df])
        
        # 先整理策略表
        heifer_strategies = []
        mature_strategies = []
        for strategy_row in strategy['strategy_table']:
            group = strategy_row['group']
            if group.startswith('后备牛'):
                heifer_strategies.append(strategy_row)
            elif group.startswith('成母牛'):
                mature_strategies.append(strategy_row)
        
        # 为策略排序，确保按A->B->C顺序处理
        heifer_strategies.sort(key=lambda x: x['group'])
        mature_strategies.sort(key=lambda x: x['group'])
        
        if progress_callback:
            progress_callback.update_info(f"分组策略: 后备牛 {len(heifer_strategies)} 个策略组, 成母牛 {len(mature_strategies)} 个策略组")
        
        # 调试：打印成母牛策略详情
        print(f"\n成母牛策略详情:")
        for i, strategy_row in enumerate(mature_strategies):
            print(f"  策略{i+1}: {strategy_row['group']}, 比例: {strategy_row['ratio']}%, 配种方法: {strategy_row['breeding_methods']}")
        
        # 调试：检查成母牛未孕牛数量
        mature_unpregnant_count = len(result_df[result_df['group'] == '成母牛未孕牛'])
        print(f"\n成母牛未孕牛总数: {mature_unpregnant_count} 头")
        if mature_unpregnant_count > 0:
            # 检查是否有ranking数据
            mature_unpregnant_df = result_df[result_df['group'] == '成母牛未孕牛']
            has_ranking = 'ranking' in mature_unpregnant_df.columns and not mature_unpregnant_df['ranking'].isna().all()
            print(f"成母牛未孕牛是否有ranking数据: {has_ranking}")
            if has_ranking:
                print(f"ranking范围: {mature_unpregnant_df['ranking'].min()} - {mature_unpregnant_df['ranking'].max()}")
        else:
            print("警告：没有成母牛未孕牛！")
        
        # 验证策略比例总和是否合理
        heifer_total = sum(s['ratio'] for s in heifer_strategies)
        mature_total = sum(s['ratio'] for s in mature_strategies)
        if heifer_total > 100:
            warning = f"后备牛策略总比例超过100%: {heifer_total}%"
            print(f"警告：{warning}")
            if progress_callback:
                progress_callback.update_info(f"警告: {warning}")
        if mature_total > 100:
            warning = f"成母牛策略总比例超过100%: {mature_total}%"
            print(f"警告：{warning}")
            if progress_callback:
                progress_callback.update_info(f"警告: {warning}")
        
        # 跟踪已处理牛只，避免重复处理
        processed_cows = set()
        
        # 1. 处理后备牛各周期
        print("\n开始处理后备牛分组...")
        if progress_callback:
            progress_callback.update_info("开始处理后备牛各周期分组...")
        
        # 找出所有后备牛周期组
        heifer_cycle_groups = set()
        for group in result_df['group']:
            if pd.isna(group):
                continue
            if group.startswith('后备牛第') and not ('+性控' in group or '+非性控' in group):
                heifer_cycle_groups.add(group)
        
        if progress_callback:
            progress_callback.update_info(f"发现后备牛周期组: {sorted(heifer_cycle_groups)}")
        
        print(f"后备牛周期组: {sorted(heifer_cycle_groups)}")
        
        # 对每个周期组应用策略
        for cycle_group in sorted(heifer_cycle_groups):
            cycle_df = result_df[result_df['group'] == cycle_group]
            
            # 确保该组有ranking列且可以排序
            if 'ranking' in cycle_df.columns and not cycle_df['ranking'].isna().all():
                cycle_df = cycle_df.sort_values('ranking')
                total_cows = len(cycle_df)
                
                if progress_callback:
                    progress_callback.update_info(f"处理 {cycle_group}: {total_cows} 头牛")
                
                print(f"\n处理{cycle_group}，共{total_cows}头牛:")
                
                cumulative_ratio = 0
                
                # 遍历每个策略组（A/B/C）
                for strategy_row in heifer_strategies:
                    group = strategy_row['group']
                    ratio = strategy_row['ratio']
                    breeding_methods = strategy_row['breeding_methods']
                    
                    # 计算该组应该包含的牛的数量和范围
                    start_idx = int(total_cows * cumulative_ratio / 100)
                    end_idx = int(total_cows * (cumulative_ratio + ratio) / 100)
                    count = end_idx - start_idx
                    
                    if count <= 0:
                        info = f"  {group} 比例{ratio}% 计算结果为0头牛，跳过"
                        print(info)
                        if progress_callback:
                            progress_callback.update_info(info)
                        cumulative_ratio += ratio
                        continue
                    
                    info = f"  {group}: 比例{ratio}%, 第{start_idx+1}-{end_idx}头, 共{count}头"
                    print(info)
                    if progress_callback:
                        progress_callback.update_info(info)
                    
                    # 获取该组的牛
                    group_df = cycle_df.iloc[start_idx:end_idx]
                    
                    # 对每头牛应用配种策略
                    sexed_count = 0
                    non_sexed_count = 0
                    beef_count = 0
                    
                    for idx, row in group_df.iterrows():
                        # 获取该牛的配种次数，如果为空则默认为0（未配种）
                        services = row.get('services_time', 0)
                        if pd.isna(services):
                            services = 0
                        services = int(services)
                        
                        # 获取对应的配种方法（根据已配种次数确定下次使用什么）
                        # services=0表示还没配过，下次是第1次，对应索引0
                        # services=1表示已配1次，下次是第2次，对应索引1
                        method_idx = min(services, len(breeding_methods) - 1)
                        method = breeding_methods[method_idx]
                        
                        # 判断配种类型
                        if method in ["普通性控", "超级性控"]:
                            breeding_type = "性控"
                        else:
                            breeding_type = "非性控"
                        
                        # 检查该牛的所有配种方法中是否有肉牛冻精
                        has_beef = "肉牛冻精" in breeding_methods
                        
                        # 如果有肉牛冻精，添加肉牛标记
                        if has_beef:
                            breeding_type += "（肉牛）"
                        
                        # 更新分组信息
                        new_group = f"{cycle_group}+{breeding_type}"
                        result_df.loc[idx, 'group'] = new_group
                        processed_cows.add(idx)
                        
                        if "性控（肉牛）" in breeding_type:
                            sexed_count += 1
                            beef_count += 1
                        elif "性控" in breeding_type:
                            sexed_count += 1
                        elif "非性控（肉牛）" in breeding_type:
                            beef_count += 1
                            non_sexed_count += 1
                        else:
                            non_sexed_count += 1
                    
                    summary = f"    {group} 完成: 性控 {sexed_count} 头, 非性控 {non_sexed_count} 头, 肉牛 {beef_count} 头"
                    print(summary)
                    if progress_callback:
                        progress_callback.update_info(summary)
                    
                    cumulative_ratio += ratio
            else:
                warning = f"警告: {cycle_group} 没有有效的ranking数据，跳过"
                print(warning)
                if progress_callback:
                    progress_callback.update_info(warning)
        
        # 2. 处理成母牛未孕牛
        if progress_callback:
            progress_callback.update_info("开始处理成母牛未孕牛分组...")
        
        print("\n处理成母牛未孕牛...")
        mature_mask = result_df['group'] == '成母牛未孕牛'
        mature_df = result_df[mature_mask]
        
        if not mature_df.empty:
            if 'ranking' in mature_df.columns and not mature_df['ranking'].isna().all():
                mature_df = mature_df.sort_values('ranking')
                total_cows = len(mature_df)
                
                if progress_callback:
                    progress_callback.update_info(f"处理成母牛未孕牛: {total_cows} 头")
                
                print(f"成母牛未孕牛共{total_cows}头")
                
                cumulative_ratio = 0
                
                # 遍历每个策略组（A/B/C）
                print(f"  开始应用 {len(mature_strategies)} 个成母牛策略...")
                for strategy_row in mature_strategies:
                    group = strategy_row['group']
                    ratio = strategy_row['ratio']
                    breeding_methods = strategy_row['breeding_methods']
                    
                    print(f"    策略组 {group}: 比例 {ratio}%, 配种方法: {breeding_methods}")
                    
                    # 计算该组应该包含的牛的数量和范围
                    start_idx = int(total_cows * cumulative_ratio / 100)
                    end_idx = int(total_cows * (cumulative_ratio + ratio) / 100)
                    count = end_idx - start_idx
                    
                    if count <= 0:
                        info = f"{group} 比例{ratio}% 计算结果为0头牛，跳过"
                        print(info)
                        if progress_callback:
                            progress_callback.update_info(info)
                        cumulative_ratio += ratio
                        continue
                    
                    info = f"处理 {group}: 比例{ratio}%, 第{start_idx+1}-{end_idx}头, 共{count}头"
                    print(info)
                    if progress_callback:
                        progress_callback.update_info(info)
                    
                    # 获取该组的牛
                    group_df = mature_df.iloc[start_idx:end_idx]
                    
                    # 对每头牛应用配种策略
                    sexed_count = 0
                    non_sexed_count = 0
                    beef_count = 0
                    
                    for idx, row in group_df.iterrows():
                        # 获取该牛的配种次数，如果为空则默认为0（未配种）
                        services = row.get('services_time', 0)
                        if pd.isna(services):
                            services = 0
                        services = int(services)
                        
                        # 获取对应的配种方法（根据已配种次数确定下次使用什么）
                        # services=0表示还没配过，下次是第1次，对应索引0
                        # services=1表示已配1次，下次是第2次，对应索引1
                        method_idx = min(services, len(breeding_methods) - 1)
                        method = breeding_methods[method_idx]
                        
                        # 判断配种类型
                        if method in ["普通性控", "超级性控"]:
                            breeding_type = "性控"
                        else:
                            breeding_type = "非性控"
                        
                        # 检查该牛的所有配种方法中是否有肉牛冻精
                        has_beef = "肉牛冻精" in breeding_methods
                        
                        # 如果有肉牛冻精，添加肉牛标记
                        if has_beef:
                            breeding_type += "（肉牛）"
                        
                        # 更新分组信息
                        new_group = f"成母牛未孕牛+{breeding_type}"
                        result_df.loc[idx, 'group'] = new_group
                        processed_cows.add(idx)
                        
                        if "性控（肉牛）" in breeding_type:
                            sexed_count += 1
                            beef_count += 1
                        elif "性控" in breeding_type:
                            sexed_count += 1
                        elif "非性控（肉牛）" in breeding_type:
                            beef_count += 1
                            non_sexed_count += 1
                        else:
                            non_sexed_count += 1
                    
                    summary = f"  {group} 完成: 性控 {sexed_count} 头, 非性控 {non_sexed_count} 头, 肉牛 {beef_count} 头"
                    print(summary)
                    if progress_callback:
                        progress_callback.update_info(summary)
                    
                    cumulative_ratio += ratio
            else:
                warning = "警告：成母牛未孕牛没有ranking列，跳过"
                print(warning)
                if progress_callback:
                    progress_callback.update_info(warning)
        else:
            info = "没有找到成母牛未孕牛"
            print(info)
            if progress_callback:
                progress_callback.update_info(info)
        
        # 3. 处理已孕牛和难孕牛 - 根据配种策略决定是否使用肉牛冻精
        if progress_callback:
            progress_callback.update_info("处理已孕牛和难孕牛...")
        
        print("\n处理已孕牛和难孕牛...")
        # 确保group列存在且处理NaN值
        if 'group' in result_df.columns:
            special_mask = result_df['group'].fillna('').str.contains('已孕牛|难孕牛', na=False)
            special_mask = special_mask & ~result_df.index.isin(processed_cows)
            special_df = result_df[special_mask]
            special_count = len(special_df)
            
            if progress_callback:
                progress_callback.update_info(f"处理特殊牛只: {special_count} 头 (已孕牛和难孕牛)")
            
            # 统计各类型数量
            beef_count = 0
            regular_count = 0
            
            for idx, row in special_df.iterrows():
                current_group = row['group']
                if pd.notna(current_group) and not ('+性控' in current_group or '+非性控' in current_group):
                    # 获取该牛的配种次数
                    services = row.get('services_time', 0)
                    if pd.isna(services):
                        services = 0
                    services = int(services)

                    # 从策略表中查找对应的配种方法
                    # 已孕牛和难孕牛通常使用最后一个配种方法（第4次+）
                    breeding_method = None

                    # 判断是后备牛还是成母牛
                    if '后备牛' in current_group:
                        # 查找后备牛策略（使用任意一个后备牛策略组，因为难孕牛和已孕牛的处理相同）
                        for strategy_row in heifer_strategies:
                            if strategy_row['breeding_methods']:
                                # 使用最后一个配种方法（第4次+）
                                breeding_method = strategy_row['breeding_methods'][-1]
                                break
                    else:  # 成母牛
                        # 查找成母牛策略
                        for strategy_row in mature_strategies:
                            if strategy_row['breeding_methods']:
                                # 使用最后一个配种方法（第4次+）
                                breeding_method = strategy_row['breeding_methods'][-1]
                                break

                    # 根据配种方法决定分组
                    if breeding_method == "肉牛冻精":
                        result_df.loc[idx, 'group'] = f"{current_group}+非性控（肉牛）"
                        beef_count += 1
                    else:
                        result_df.loc[idx, 'group'] = f"{current_group}+非性控"
                        regular_count += 1

                    processed_cows.add(idx)
            
            if special_count > 0:
                summary = f"  已孕牛和难孕牛处理完成: 常规非性控 {regular_count} 头, 肉牛 {beef_count} 头"
                print(summary)
                if progress_callback:
                    progress_callback.update_info(summary)
        else:
            warning = "警告：结果数据中没有group列"
            print(warning)
            if progress_callback:
                progress_callback.update_info(warning)
        
        # 处理任何剩余未添加性控/非性控/肉牛标记的牛 - 默认使用非性控
        if 'group' in result_df.columns:
            # 确保安全地处理可能的NaN值
            has_group_mask = result_df['group'].notna()
            not_processed_mask = ~result_df.index.isin(processed_cows)
            no_breeding_mark_mask = ~result_df['group'].fillna('').str.contains('[+]性控|[+]非性控', na=False)

            remaining_mask = has_group_mask & not_processed_mask & no_breeding_mark_mask
            remaining_count = remaining_mask.sum()

            if remaining_count > 0:
                if progress_callback:
                    progress_callback.update_info(f"处理剩余牛只: {remaining_count} 头 (默认非性控)")

                for idx in result_df[remaining_mask].index:
                    current_group = result_df.loc[idx, 'group']
                    if pd.notna(current_group):
                        result_df.loc[idx, 'group'] = f"{current_group}+非性控"
                        processed_cows.add(idx)
        
        final_info = f"分组完成，共处理 {len(processed_cows)} 头牛"
        print(final_info)
        if progress_callback:
            progress_callback.update_info(final_info)
        
        # 输出最终分组统计
        print("\n===== 最终分组统计 =====")
        group_stats = result_df['group'].value_counts()
        for group, count in group_stats.items():
            print(f"{group}: {count}头")

        # 统计肉牛组数量
        beef_groups = group_stats[group_stats.index.str.contains('（肉牛）')]
        if not beef_groups.empty:
            print(f"\n肉牛标记组总计: {beef_groups.sum()}头")
            for group, count in beef_groups.items():
                print(f"  {group}: {count}头")
        
        if progress_callback:
            progress_callback.set_task_info("分组完成")
            progress_callback.update_progress(100)
        
        return result_df

    def apply_grouping(self, strategy_name: str) -> pd.DataFrame:
        """应用指定的分组策略"""
        # 加载策略
        self.load_strategy(strategy_name)
        
        # 加载数据
        self.load_data()
        
        # 对特殊牛只进行分组（已孕牛和难孕牛）
        df = self.group_special_cows()
        
        # 按周期分组
        df = self.group_by_cycle(df)
        
        # 分配配种方法
        df = self.assign_breeding_methods(df)
        
        return df

    def get_group_summary(self) -> pd.DataFrame:
        """获取分组统计结果"""
        # 统计各分组的数量
        summary = pd.DataFrame(self.cow_data['group'].value_counts())
        summary.columns = ['数量']
        summary.index.name = '分组'
        return summary.reset_index() 