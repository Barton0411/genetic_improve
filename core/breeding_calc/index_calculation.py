# core/breeding_calc/index_calculation.py

from pathlib import Path
import json
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from sqlalchemy import create_engine, text
from core.breeding_calc.traits_calculation import TraitsCalculation
from utils.large_excel_writer import (
    normalize_identifier_key,
    read_excel_identifier_safe,
    write_dataframe_atomic,
)

from .base_calculation import BaseCowCalculation
from .cow_traits_calc import TRAITS_TRANSLATION
import os
from pathlib import Path

# 标准差数据
TRAIT_SD = {
    'MILK': 567, 'NM$': 100, 'FS': 56, 'FE': 50, 'RFI': 46.2,
    'FAT': 25, 'PROT': 15, 'MAST': 2.6, 'EFC': 2.05, 'PL': 1.7,
    'CCR': 1.6, 'LIV': 1.6, 'DPR': 1.4, 'MET': 1.4, 'HCR': 1.3,
    'TPI': 100, 'CM$': 100, 'FM$': 100, 'ST': 1, 'SG': 1,
    'BD': 1, 'DF': 1, 'RA': 1, 'RW': 1, 'LS': 1,
    'LR': 1, 'FA': 1, 'FLS': 1, 'FU': 1, 'UH': 1,
    'UW': 1, 'UC': 1, 'UD': 1, 'FT': 1, 'RT': 1,
    'TL': 1, 'GM$': 100, 'KET': 1, 'PTAT': 1, 'RP': 0.9,
    'BDC': 0.76, 'DA': 0.7, 'UDC': 0.65, 'FLC': 0.53,
    'HLiv': 0.4, 'MFV': 0.4, 'SCS': 0.14, 'FAT %': 0.1, 'PROT%': 0.04
}

# 系统预设权重
DEFAULT_WEIGHTS = {
    'NM$权重': {'NM$': 100},
    'TPI权重': {'TPI': 100}
}

class IndexCalculation(BaseCowCalculation):
    def __init__(self):
        super().__init__()
        self.output_prefix = "processed_index"
        self.required_columns = ['cow_id']  # 基本必需列
        self.traits_calculator = TraitsCalculation()  # 初始化 TraitsCalculation 实例
        self.db_engine = None  # 初始化为 None，不在构造函数中连接

    @staticmethod
    def validate_cow_identifiers(
        frame: pd.DataFrame,
    ) -> Tuple[Optional[pd.Series], str]:
        """在排名前拒绝空牛号或重复牛号，避免重复计算或串行。"""
        if "cow_id" not in frame.columns:
            return None, "母牛评估结果缺少牛号列"
        identifiers = frame["cow_id"].map(normalize_identifier_key)
        blank_rows = int(identifiers.eq("").sum())
        duplicate_mask = identifiers.ne("") & identifiers.duplicated(
            keep=False
        )
        duplicate_rows = int(duplicate_mask.sum())
        duplicate_groups = int(
            identifiers.loc[duplicate_mask].nunique()
        )
        if blank_rows or duplicate_rows:
            return (
                None,
                "母牛评估结果牛号异常："
                f"空牛号 {blank_rows} 行，"
                f"重复牛号 {duplicate_groups} 组/{duplicate_rows} 行；"
                "已停止排名以避免重复计算或错配",
            )
        return identifiers, ""


    @staticmethod
    def get_global_weights_path() -> Path:
        """获取全局权重配置文件路径"""
        import sys
        import os
        
        # 在打包的应用中，使用用户数据目录
        if hasattr(sys, '_MEIPASS'):
            # Windows: C:\Users\<username>\AppData\Local\genetic_improve
            # Mac: ~/Library/Application Support/genetic_improve
            if sys.platform == 'win32':
                app_data = Path(os.environ['LOCALAPPDATA']) / 'genetic_improve'
            else:
                app_data = Path.home() / 'Library' / 'Application Support' / 'genetic_improve'
            weights_path = app_data / "index_weights"
        else:
            # 开发环境不能依赖仓库目录必须命名为 genetic_improve；
            # Git worktree 或目录改名后，按固定层级定位项目根目录。
            project_root = Path(__file__).resolve().parents[2]
            if project_root.parent.name == ".worktrees":
                workspace_root = project_root.parent.parent
            else:
                workspace_root = project_root.parent

            # genetic_projects 是维护仓库所在工作区的同级数据目录。
            weights_path = (
                workspace_root / "genetic_projects" / "index_weights"
            )
        
        try:
            weights_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            import logging
            logging.warning(f"Failed to create weights directory: {e}")
            # 返回临时目录作为备选
            import tempfile
            weights_path = Path(tempfile.gettempdir()) / "genetic_improve_weights"
            weights_path.mkdir(parents=True, exist_ok=True)
            
        return weights_path
        
    def load_weights(self) -> Dict[str, Dict[str, float]]:
        """加载所有权重配置（包括系统预设和用户自定义）"""
        weights = DEFAULT_WEIGHTS.copy()
        
        try:
            # 使用全局路径
            weights_file = self.get_global_weights_path() / "custom_weights.json"
            if weights_file.exists():
                with open(weights_file, 'r', encoding='utf-8') as f:
                    custom_weights = json.load(f)
                weights.update(custom_weights)
        except Exception as e:
            print(f"加载用户自定义权重失败: {e}")
                
        return weights
        
    def save_custom_weight(self, weight_name: str, weight_values: Dict[str, float]) -> bool:
        """保存用户自定义权重"""
        try:
            # 使用全局路径
            weights_file = self.get_global_weights_path() / "custom_weights.json"
            
            # 读取现有权重
            existing_weights = {}
            if weights_file.exists():
                with open(weights_file, 'r', encoding='utf-8') as f:
                    existing_weights = json.load(f)
            
            # 更新权重
            existing_weights[weight_name] = weight_values
            
            # 保存
            with open(weights_file, 'w', encoding='utf-8') as f:
                json.dump(existing_weights, f, ensure_ascii=False, indent=4)
                
            return True
            
        except Exception as e:
            print(f"保存自定义权重失败: {e}")
            return False
            
    def delete_custom_weight(self, weight_name: str) -> bool:
        """删除用户自定义权重"""
        try:
            weights_file = self.get_global_weights_path() / "custom_weights.json"
            
            if not weights_file.exists():
                return False
                
            with open(weights_file, 'r', encoding='utf-8') as f:
                weights = json.load(f)
                
            if weight_name in weights:
                del weights[weight_name]
                
                with open(weights_file, 'w', encoding='utf-8') as f:
                    json.dump(weights, f, ensure_ascii=False, indent=4)
                    
                return True
            return False
            
        except Exception as e:
            print(f"删除自定义权重失败: {e}")
            return False
            
    def validate_weight_values(self, weight_values: Dict[str, float]) -> bool:
        """验证权重值是否有效"""
        total = sum(abs(v) for v in weight_values.values())
        return abs(total - 100) < 0.0001  # 允许一点点浮点数误差
        
    def calculate_index_score(self, trait_values: dict, weight_values: dict) -> float:
        """计算指数得分"""
        score = 0
        for trait, weight in weight_values.items():
            if trait in trait_values and trait in TRAIT_SD:
                # 每个性状的得分 = 性状值/性状标准差 × 权重值
                score += (trait_values[trait] / TRAIT_SD[trait]) * weight
        return score
        
    def process_cow_index(
        self,
        main_window,
        weight_name: str,
        progress_callback=None,
        task_info_callback=None,
        *,
        weight_values: Optional[Dict[str, float]] = None,
    ) -> Tuple[bool, str]:
        """处理母牛群指数计算

        Args:
            main_window: 主窗口实例
            weight_name: 权重配置名称
            progress_callback: 进度回调函数 (progress_value, message)
            task_info_callback: 任务信息回调函数 (task_info)
        """
        try:
            project_path = main_window.selected_project_path

            # 更新进度
            if task_info_callback:
                task_info_callback("检查数据文件...")
            if progress_callback:
                progress_callback(5, "检查母牛数据文件...")

            # 1. 首先检查是否有 processed_cow_data.xlsx
            cow_data_path = project_path / "standardized_data" / "processed_cow_data.xlsx"
            if not cow_data_path.exists():
                return False, "请先上传母牛数据"

            # 2. 加载权重配置并获取性状列表
            if progress_callback:
                progress_callback(10, "加载权重配置...")
            if weight_values is None:
                weights = self.load_weights()
                if weight_name not in weights:
                    return False, f"未找到权重配置：{weight_name}"
                weight_values = weights[weight_name]
            else:
                weight_values = {
                    str(trait): float(value)
                    for trait, value in weight_values.items()
                    if float(value) != 0
                }
                if not weight_values or not self.validate_weight_values(
                    weight_values
                ):
                    return False, "批量任务中的权重快照无效"
            selected_traits = list(weight_values.keys())

            # 3. 检查是否存在基因组评估结果文件
            if task_info_callback:
                task_info_callback("检查评估结果...")
            if progress_callback:
                progress_callback(15, "检查现有评估结果...")

            genomic_scores_path = project_path / "analysis_results" / "processed_cow_data_key_traits_scores_genomic.xlsx"
            if genomic_scores_path.exists():
                # 3.1 基因组评估结果存在，检查是否完整
                genomic_df = read_excel_identifier_safe(genomic_scores_path)
                existing_traits = [col[:-6] for col in genomic_df.columns if col.endswith('_score')]
                missing_traits = [trait for trait in selected_traits if trait not in existing_traits]

                if not missing_traits:
                    # 所有性状都存在，直接使用现有基因组评估结果
                    print("使用现有完整的基因组评估结果")
                    if progress_callback:
                        progress_callback(80, "使用现有基因组评估结果...")
                    df = genomic_df
                else:
                    # 缺少部分性状，需要重新计算
                    print(f"基因组评估结果缺少性状: {missing_traits}")
                    if task_info_callback:
                        task_info_callback("计算缺失性状...")

                    # 重要：合并原有性状和需要的性状，避免覆盖原有数据
                    all_traits_to_calc = list(set(existing_traits) | set(selected_traits))
                    print(f"将计算所有性状（保留原有 + 新增）: {len(all_traits_to_calc)} 个")

                    # 检查是否有基因组数据
                    genomic_data_path = project_path / "standardized_data" / "processed_genomic_data.xlsx"
                    if genomic_data_path.exists():
                        # 有基因组数据，重新计算包含基因组数据
                        success, message = self.traits_calculator.process_data(
                            main_window, all_traits_to_calc,
                            progress_callback=progress_callback,
                            task_info_callback=task_info_callback
                        )
                        if not success:
                            return False, message
                        df = read_excel_identifier_safe(
                            project_path
                            / "analysis_results"
                            / "processed_cow_data_key_traits_scores_genomic.xlsx"
                        )
                    else:
                        # 没有基因组数据，使用系谱计算后更新基因组评估文件
                        success, message = self.traits_calculator.process_data(
                            main_window, all_traits_to_calc,
                            progress_callback=progress_callback,
                            task_info_callback=task_info_callback
                        )
                        if not success:
                            return False, message

                        # 读取新计算的系谱结果
                        pedigree_df = read_excel_identifier_safe(
                            project_path
                            / "analysis_results"
                            / "processed_cow_data_key_traits_scores_pedigree.xlsx"
                        )

                        # 更新基因组评估文件中的缺失性状
                        for trait in missing_traits:
                            score_col = f'{trait}_score'
                            source_col = f'{trait}_score_source'
                            genomic_df[score_col] = pedigree_df[score_col]
                            genomic_df[source_col] = 'P'  # 标记为系谱来源

                        # 保存更新后的基因组评估文件
                        if not self.save_results_with_retry(
                            genomic_df,
                            genomic_scores_path,
                        ):
                            return False, "更新基因组评估文件失败"
                        df = genomic_df
            else:
                # 3.2 基因组评估结果不存在，检查是否有基因组数据
                genomic_data_path = project_path / "standardized_data" / "processed_genomic_data.xlsx"
                if genomic_data_path.exists():
                    # 有基因组数据，计算包含基因组数据的结果
                    if task_info_callback:
                        task_info_callback("计算性状得分（含基因组数据）...")
                    success, message = self.traits_calculator.process_data(
                        main_window, selected_traits,
                        progress_callback=progress_callback,
                        task_info_callback=task_info_callback
                    )
                    if not success:
                        return False, message
                    df = read_excel_identifier_safe(
                        project_path
                        / "analysis_results"
                        / "processed_cow_data_key_traits_scores_genomic.xlsx"
                    )
                else:
                    # 没有基因组数据，检查系谱评估结果
                    pedigree_scores_path = project_path / "analysis_results" / "processed_cow_data_key_traits_scores_pedigree.xlsx"
                    if pedigree_scores_path.exists():
                        # 检查系谱评估结果是否完整
                        pedigree_df = read_excel_identifier_safe(
                            pedigree_scores_path
                        )
                        existing_traits = [col[:-6] for col in pedigree_df.columns if col.endswith('_score')]
                        missing_traits = [trait for trait in selected_traits if trait not in existing_traits]

                        if not missing_traits:
                            # 系谱评估结果完整，直接使用
                            print("使用现有完整的系谱评估结果")
                            if progress_callback:
                                progress_callback(80, "使用现有系谱评估结果...")
                            df = pedigree_df
                        else:
                            # 系谱评估结果不完整，重新计算
                            print(f"系谱评估结果缺少性状: {missing_traits}")
                            if task_info_callback:
                                task_info_callback("计算缺失性状...")

                            # 重要：合并原有性状和需要的性状，避免覆盖原有数据
                            all_traits_to_calc = list(set(existing_traits) | set(selected_traits))
                            print(f"将计算所有性状（保留原有 + 新增）: {len(all_traits_to_calc)} 个")

                            success, message = self.traits_calculator.process_data(
                                main_window, all_traits_to_calc,
                                progress_callback=progress_callback,
                                task_info_callback=task_info_callback
                            )
                            if not success:
                                return False, message
                            df = read_excel_identifier_safe(
                                project_path
                                / "analysis_results"
                                / "processed_cow_data_key_traits_scores_pedigree.xlsx"
                            )
                    else:
                        # 没有任何评估结果，计算系谱评估结果
                        if task_info_callback:
                            task_info_callback("计算性状得分...")
                        success, message = self.traits_calculator.process_data(
                            main_window, selected_traits,
                            progress_callback=progress_callback,
                            task_info_callback=task_info_callback
                        )
                        if not success:
                            return False, message
                        df = read_excel_identifier_safe(
                            project_path
                            / "analysis_results"
                            / "processed_cow_data_key_traits_scores_pedigree.xlsx"
                        )

            identifiers, identifier_error = self.validate_cow_identifiers(df)
            if identifier_error:
                return False, identifier_error
            df["cow_id"] = identifiers

            # 4. 计算指数得分 (向量化优化)
            if task_info_callback:
                task_info_callback("计算指数得分...")
            if progress_callback:
                progress_callback(90, "计算指数得分...")

            score = np.zeros(len(df))
            for trait, weight in weight_values.items():
                if trait in TRAIT_SD:
                    score_col = f'{trait}_score'
                    if score_col in df.columns:
                        # 使用向量化操作，NaN 值用 0 填充
                        trait_scores = df[score_col].fillna(0).values
                        score += (trait_scores / TRAIT_SD[trait]) * weight
            df[f'{weight_name}_index'] = score

            # 5. 排序并添加排名
            if progress_callback:
                progress_callback(95, "排序并添加排名...")
            df.sort_values(
                f'{weight_name}_index',
                ascending=False,
                inplace=True,
                ignore_index=True,
            )
            df['ranking'] = range(1, len(df) + 1)

            # 6. 保存结果（应用格式化）
            if task_info_callback:
                task_info_callback("保存结果...")
            if progress_callback:
                progress_callback(98, "保存结果文件...")

            output_path = project_path / "analysis_results" / f"{self.output_prefix}_cow_index_scores.xlsx"
            if not self.save_results_with_retry(df, output_path, apply_formatting=True):
                return False, "保存结果失败"

            if progress_callback:
                progress_callback(100, "计算完成！")

            return True, "计算完成"

        except Exception as e:
            print(f"计算母牛群指数时发生错误: {str(e)}")
            return False, str(e)

    def process_bull_index(
        self,
        main_window,
        weight_name: str,
        progress_callback=None,
        task_info_callback=None,
        *,
        weight_values: Optional[Dict[str, float]] = None,
        allow_missing_bull_upload: bool = True,
    ) -> Tuple[bool, str]:
        """处理公牛指数计算

        Args:
            main_window: 主窗口实例
            weight_name: 权重配置名称
            progress_callback: 进度回调函数 (progress_value, message)
            task_info_callback: 任务信息回调函数 (task_info)
        """
        try:
            project_path = main_window.selected_project_path

            # 更新进度
            if task_info_callback:
                task_info_callback("检查数据文件...")
            if progress_callback:
                progress_callback(5, "检查备选公牛数据...")

            # 1. 检查并初始化必要的设置
            bull_data_path = project_path / "standardized_data" / "processed_bull_data.xlsx"
            if not bull_data_path.exists():
                return False, "请先上传备选公牛数据"

            # 2. 检查并初始化数据库连接
            if progress_callback:
                progress_callback(10, "连接数据库...")
            if not self.init_db_connection():
                print("数据库连接初始化失败")
                return False, "连接数据库失败"

            # 3. 加载权重配置
            if progress_callback:
                progress_callback(15, "加载权重配置...")
            if weight_values is None:
                weights = self.load_weights()
                if weight_name not in weights:
                    return False, f"未找到权重配置：{weight_name}"
                weight_values = weights[weight_name]
            else:
                weight_values = {
                    str(trait): float(value)
                    for trait, value in weight_values.items()
                    if float(value) != 0
                }
                if not weight_values or not self.validate_weight_values(
                    weight_values
                ):
                    return False, "批量任务中的权重快照无效"
            if not weight_values:
                return False, "权重配置为空"

            selected_traits = list(weight_values.keys())
            if not selected_traits:
                return False, "未找到需要计算的性状"

            # 4. 读取备选公牛数据
            if task_info_callback:
                task_info_callback("读取公牛数据...")
            if progress_callback:
                progress_callback(20, "读取备选公牛数据...")
            try:
                bull_df = read_excel_identifier_safe(bull_data_path)
                if bull_df.empty:
                    return False, "备选公牛数据为空"
            except Exception as e:
                return False, f"读取备选公牛数据失败: {str(e)}"

            # 5. 批量查询公牛性状数据
            if task_info_callback:
                task_info_callback("批量查询公牛性状...")
            if progress_callback:
                progress_callback(30, "批量查询公牛性状数据...")

            all_bull_ids = bull_df['bull_id'].astype(str).tolist()
            batch_results = self.query_bull_traits_batch(all_bull_ids, selected_traits)

            # 向量化填充公牛性状（替代iterrows逐行赋值）
            bull_ids_str = bull_df['bull_id'].astype(str)
            found_ids = set(batch_results.keys())

            for trait in selected_traits:
                trait_map = {
                    bull_id: trait_data.get(trait)
                    for bull_id, (trait_data, _) in batch_results.items()
                }
                bull_df[trait] = bull_ids_str.map(trait_map)

            missing_bulls = [bid for bid in bull_ids_str if bid not in found_ids]

            # 6. 处理缺失的公牛信息
            if missing_bulls and allow_missing_bull_upload:
                if progress_callback:
                    progress_callback(75, f"处理 {len(missing_bulls)} 个缺失公牛...")
                print(f"\n[检查点-指数] 在指数排序中发现 {len(missing_bulls)} 个缺失公牛")
                print(f"[检查点-指数] 调用 process_missing_bulls 进行上传...")
                self.process_missing_bulls(missing_bulls, 'bull_index', main_window.username)
            elif missing_bulls:
                print(
                    f"\n[检查点-指数] 有 {len(missing_bulls)} 个缺失公牛；"
                    "当前为离线牧场组子任务，不上报服务端"
                )
            else:
                print("\n[检查点-指数] 所有公牛数据完整，无缺失公牛")

            # 7. 计算指数得分 (向量化优化)
            if task_info_callback:
                task_info_callback("计算指数得分...")
            if progress_callback:
                progress_callback(85, "计算指数得分...")

            score = np.zeros(len(bull_df))
            valid_score_mask = np.ones(len(bull_df), dtype=bool)
            for trait, weight in weight_values.items():
                if trait in TRAIT_SD and trait in bull_df.columns:
                    trait_values = pd.to_numeric(
                        bull_df[trait], errors='coerce'
                    )
                    valid_score_mask &= trait_values.notna().to_numpy()
                    score += (
                        trait_values.fillna(0).to_numpy()
                        / TRAIT_SD[trait]
                    ) * weight

            # 缺少参与指数计算的任何性状时，不能把缺失值当作0分。
            # 否则在真实指数允许为负数时，缺失公牛会被错误排在有效公牛前面。
            score[~valid_score_mask] = np.nan
            index_col = f'{weight_name}_index'
            bull_df[index_col] = score

            # 8. 排序并添加排名
            if progress_callback:
                progress_callback(90, "排序并添加排名...")
            bull_df = bull_df.sort_values(
                index_col, ascending=False, na_position='last'
            )
            bull_df['ranking'] = pd.Series(
                pd.NA, index=bull_df.index, dtype='Int64'
            )
            valid_index = bull_df[index_col].notna()
            bull_df.loc[valid_index, 'ranking'] = range(
                1, int(valid_index.sum()) + 1
            )

            # 9. 保存结果
            if task_info_callback:
                task_info_callback("保存结果...")
            if progress_callback:
                progress_callback(95, "保存结果文件...")

            output_path = project_path / "analysis_results" / f"{self.output_prefix}_bull_scores.xlsx"
            if not self.save_results_with_retry(bull_df, output_path):
                return False, "保存结果失败"

            if progress_callback:
                progress_callback(100, "计算完成！")

            return True, "计算完成"
                
        except Exception as e:
            print(f"公牛指数计算发生错误: {str(e)}")
            return False, str(e)
            
        finally:
            # 确保关闭数据库连接
            if hasattr(self, 'db_engine') and self.db_engine is not None:
                try:
                    self.db_engine.dispose()
                    self.db_engine = None
                except Exception as e:
                    print(f"关闭数据库连接时发生错误: {str(e)}")
            
    def calculate_cow_traits(self, project_path: Path, selected_traits: List[str]) -> Tuple[bool, Optional[pd.DataFrame]]:
        """计算母牛关键性状"""
        try:
            cow_data_path = project_path / "standardized_data" / "processed_cow_data.xlsx"
            if not self.init_db_connection():
                return False, None
                
            cow_df = read_excel_identifier_safe(cow_data_path)

            # 育种分析仅针对奶牛品种，排除肉牛品种
            from config.breed_constants import filter_dairy_cows
            cow_df = filter_dairy_cows(cow_df, log_prefix="母牛性状计算：")

            # 对每个母牛计算选中的性状
            for trait in selected_traits:
                trait_col = f'sire_{trait}'
                
                # 从数据库查询公牛数据
                bull_ids = cow_df['sire'].dropna().unique()
                bull_traits = {}
                
                for bull_id in bull_ids:
                    if pd.isna(bull_id):
                        continue
                    traits_data, found = self.query_bull_traits(str(bull_id), [trait])
                    if found:
                        bull_traits[str(bull_id)] = traits_data[trait]
                
                # 设置性状值
                cow_df[trait] = cow_df['sire'].apply(
                    lambda x: bull_traits.get(str(x)) if pd.notna(x) else None
                )
            
            return True, cow_df
            
        except Exception as e:
            print(f"计算母牛性状失败: {e}")
            return False, None
        

    # 检查是否已有关键性状结果,如果有,检查是否包含所有选中性状。
    def check_existing_traits_results(self, project_path: Path, selected_traits: list) -> Tuple[Optional[pd.DataFrame], bool]:
        """
        检查是否已有关键性状结果,如果有,检查是否包含所有选中性状。
        
        Args:
            project_path: 项目路径
            selected_traits: 选中的性状列表
            
        Returns:
            Tuple[Optional[pd.DataFrame], bool]: (现有性状结果的DataFrame, 是否包含所有选中性状)
        """
        genomic_path = project_path / "analysis_results" / "processed_cow_data_key_traits_scores_genomic.xlsx"
        pedigree_path = project_path / "analysis_results" / "processed_cow_data_key_traits_scores_pedigree.xlsx"
        
        if genomic_path.exists():
            df = read_excel_identifier_safe(genomic_path)
        elif pedigree_path.exists():
            df = read_excel_identifier_safe(pedigree_path)
        else:
            return None, False
        
        existing_traits = [col[:-6] for col in df.columns if col.endswith('_score')]
        missing_traits = [trait for trait in selected_traits if trait not in existing_traits]

        return df, len(missing_traits) == 0

    def save_with_formatting(self, df, output_path):
        """低内存保存 Excel，并按同一行的来源字段应用颜色。"""
        try:
            write_dataframe_atomic(
                df,
                output_path,
                apply_source_formatting=True,
            )
            print(f"文件已保存并格式化: {output_path}")
            return True

        except Exception as e:
            print(f"保存格式化文件时发生错误: {e}")
            return False

    def save_results_with_retry(self, df: pd.DataFrame, output_path: Path, apply_formatting: bool = False) -> bool:
        """
        保存结果，如果文件被占用则提供重试选项

        Args:
            df: 要保存的数据
            output_path: 保存路径
            apply_formatting: 是否应用格式化（颜色标记）

        Returns:
            bool: 是否保存成功
        """
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QThread

        def _is_main_thread():
            app = QApplication.instance()
            return app is not None and QThread.currentThread() == app.thread()

        while True:
            try:
                if apply_formatting and any('_source' in col for col in df.columns):
                    return self.save_with_formatting(df, output_path)
                write_dataframe_atomic(df, output_path)
                return True
            except PermissionError:
                if _is_main_thread():
                    from PyQt6.QtWidgets import QMessageBox
                    reply = QMessageBox.question(
                        None,
                        "文件被占用",
                        f"文件 {output_path.name} 正在被其他程序使用。\n"
                        "请关闭该文件后点击'重试'继续，或点击'取消'停止操作。",
                        QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel,
                        QMessageBox.StandardButton.Retry
                    )
                    if reply == QMessageBox.StandardButton.Cancel:
                        print(f"用户取消了保存操作: {output_path}")
                        return False
                else:
                    import time
                    for attempt in range(3):
                        time.sleep(1)
                        try:
                            write_dataframe_atomic(
                                df,
                                output_path,
                                apply_source_formatting=(
                                    apply_formatting
                                    and any('_source' in col for col in df.columns)
                                ),
                            )
                            return True
                        except PermissionError:
                            continue
                    print(f"[警告] 文件 {output_path.name} 被占用，保存失败")
                    return False
            except Exception as e:
                print(f"保存文件失败: {e}")
                return False
