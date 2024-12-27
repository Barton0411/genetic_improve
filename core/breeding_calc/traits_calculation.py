# core/breeding_calc/traits_calculation.py

from pathlib import Path
import pandas as pd
import numpy as np
from typing import Tuple, Optional
from sqlalchemy import create_engine, text
from PyQt6.QtWidgets import QMessageBox
from sklearn.linear_model import LinearRegression

from .base_calculation import BaseCowCalculation

class TraitsCalculation(BaseCowCalculation):
    def __init__(self):
        super().__init__()
        self.output_prefix = "processed_cow_data_key_traits"
        self.required_columns = ['cow_id', 'birth_date', 'birth_date_dam', 'birth_date_mgd']

    def process_data(self, main_window, selected_traits: list, progress_callback=None) -> Tuple[bool, str]:
        """执行关键性状计算的核心逻辑"""
        try:
            # 1. 初始化必要的设置
            if not self.init_db_connection():
                return False, "连接数据库失败"

            project_path = main_window.selected_project_path
            success, error_msg = self.check_project_data(project_path, "processed_cow_data.xlsx")
            if not success:
                return False, error_msg

            # 2. 读取母牛数据，获取公牛列表
            cow_df = self.read_data(project_path, "processed_cow_data.xlsx")
            if cow_df is None:
                return False, "读取母牛数据失败"
            
            # 添加birth_year列
            cow_df['birth_year'] = pd.to_datetime(cow_df['birth_date']).dt.year
            
            # 添加sire_identified等列
            for col in ['sire', 'mgs', 'mmgs']:
                cow_df[f"{col}_identified"] = False
            
            # 获取所有公牛ID
            bull_ids = set()
            for col in ['sire', 'mgs', 'mmgs']:
                if col in cow_df.columns:
                    bull_ids.update(cow_df[col].dropna().unique())

            # 3. 处理每个公牛的性状数据
            bull_traits = {}
            missing_bulls = []
            
            for bull_id in bull_ids:
                if pd.isna(bull_id):
                    continue
                traits_data, found = self.query_bull_traits(str(bull_id), selected_traits)
                if found:
                    bull_traits[str(bull_id)] = traits_data
                else:
                    missing_bulls.append(bull_id)

            # 4. 处理缺失的公牛信息
            if missing_bulls:
                if not self.process_missing_bulls(missing_bulls, 'traits_calculation', main_window.username):
                    print("警告：缺失公牛信息上传失败")

            # 5. 合并性状数据到母牛数据中
            for bull_type in ['sire', 'mgs', 'mmgs']:
                for trait in selected_traits:
                    cow_df[f"{bull_type}_{trait}"] = cow_df[bull_type].apply(
                        lambda x: bull_traits.get(str(x), {}).get(trait) if pd.notna(x) else np.nan
                    )
                
                # 更新identified列
                cow_df[f"{bull_type}_identified"] = cow_df[bull_type].apply(
                    lambda x: str(x) in bull_traits if pd.notna(x) else False
                )

            # 6. 保存详细结果
            output_dir = self.create_output_directory(project_path)
            if not output_dir:
                return False, "创建输出目录失败"

            detail_output_path = output_dir / f"{self.output_prefix}_detail.xlsx"
            if not self.save_results_with_retry(cow_df, detail_output_path):
                return False, "保存详细结果失败"

            # 7. 处理年度平均值
            yearly_output_path = output_dir / f"{self.output_prefix}_mean_by_year.xlsx"
            if not self.process_yearly_data(detail_output_path, yearly_output_path, selected_traits):
                return False, "处理年度数据失败"

            # 8. 计算性状得分
            pedigree_output_path = output_dir / f"{self.output_prefix}_scores_pedigree.xlsx"
            if not self.calculate_trait_scores(detail_output_path, yearly_output_path, pedigree_output_path):
                return False, "计算性状得分失败"

            # 9. 更新基因组数据（如果有）
            genomic_data_path = project_path / "standardized_data" / "processed_genomic_data.xlsx"
            if genomic_data_path.exists():
                genomic_output_path = output_dir / f"{self.output_prefix}_scores_genomic.xlsx"
                if not self.update_genomic_data(pedigree_output_path, genomic_data_path, genomic_output_path):
                    return False, "更新基因组数据失败"

            return True, "计算完成"

        except Exception as e:
            return False, str(e)

    def process_yearly_data(self, detail_path: Path, output_path: Path, selected_traits: list) -> bool:
        """处理年度关键性状数据"""
        try:
            # 读取详细数据
            df = pd.read_excel(detail_path)
            
            # 获取出生年份范围
            min_year = df['birth_year'].min()
            max_year = df['birth_year'].max()
            
            # 获取默认值
            default_values = self.get_default_values(selected_traits)
            
            # 处理每个性状
            results = {}
            for trait in selected_traits:
                trait_col = f'sire_{trait}'
                
                if trait_col not in df.columns:
                    # 使用默认值
                    all_years = pd.DataFrame({'birth_year': range(min_year, max_year + 1)})
                    all_years['mean'] = default_values[trait]
                    all_years['interpolated'] = True
                else:
                    # 计算年度均值
                    yearly_means = df.groupby('birth_year').agg({
                        trait_col: ['count', 'mean']
                    }).reset_index()
                    yearly_means.columns = ['birth_year', 'count', 'mean']
                    
                    # 处理数据
                    valid_years = yearly_means[yearly_means['count'] >= 10]
                    all_years = self.process_trait_yearly_data(
                        valid_years, min_year, max_year, default_values[trait]
                    )
                
                results[trait] = all_years
            
            # 保存结果
            return self.save_yearly_results(results, output_path)
            
        except Exception as e:
            print(f"处理年度数据失败: {e}")
            return False

    def process_trait_yearly_data(self, valid_years: pd.DataFrame, min_year: int, 
                                max_year: int, default_value: float) -> pd.DataFrame:
        """处理单个性状的年度数据"""
        if len(valid_years) > 1:
            # 有多个有效年份，进行回归
            X = valid_years['birth_year'].values.reshape(-1, 1)
            y = valid_years['mean'].values
            reg = LinearRegression().fit(X, y)
            
            all_years = pd.DataFrame({'birth_year': range(min_year, max_year + 1)})
            all_years['mean'] = reg.predict(all_years['birth_year'].values.reshape(-1, 1))
            all_years['interpolated'] = ~all_years['birth_year'].isin(valid_years['birth_year'])
            
        elif len(valid_years) == 1:
            # 只有一个有效年份
            valid_year = valid_years['birth_year'].iloc[0]
            valid_mean = valid_years['mean'].iloc[0]
            
            all_years = pd.DataFrame({'birth_year': range(min_year, max_year + 1)})
            if valid_year == min_year:
                slope = default_value - valid_mean
            else:
                slope = (valid_mean - default_value) / (valid_year - min_year)
            
            all_years['mean'] = all_years['birth_year'].apply(
                lambda x: valid_mean + slope * (x - valid_year) if x > valid_year
                else np.interp(x, [min_year, valid_year], [default_value, valid_mean])
            )
            all_years['interpolated'] = ~all_years['birth_year'].isin([valid_year])
            
        else:
            # 没有有效年份
            all_years = pd.DataFrame({'birth_year': range(min_year, max_year + 1)})
            all_years['mean'] = default_value
            all_years['interpolated'] = True
            
        return all_years

    def get_default_values(self, selected_traits: list) -> dict:
        """获取默认值（从999HO99999）"""
        default_values = {}
        try:
            with self.db_engine.connect() as conn:
                default_bull = conn.execute(
                    text("SELECT * FROM bull_library WHERE `BULL NAAB`='999HO99999'")
                ).fetchone()
                if default_bull:
                    default_bull_dict = dict(default_bull._mapping)
                    for trait in selected_traits:
                        default_values[trait] = default_bull_dict.get(trait, 0)
                else:
                    for trait in selected_traits:
                        default_values[trait] = 0
        except Exception as e:
            print(f"获取默认值失败: {e}")
            for trait in selected_traits:
                default_values[trait] = 0
        
        return default_values

    def save_yearly_results(self, results: dict, output_path: Path) -> bool:
        """保存年度结果"""
        try:
            with pd.ExcelWriter(output_path) as writer:
                for trait, data in results.items():
                    data.to_excel(writer, sheet_name=trait, index=False)
            return True
        except Exception as e:
            print(f"保存年度结果失败: {e}")
            return False

    def calculate_trait_scores(self, detail_path: Path, yearly_path: Path, 
                             output_path: Path) -> bool:
        """计算性状得分"""
        try:
            df = pd.read_excel(detail_path)
            
            # 处理日期列
            date_columns = ['birth_date', 'birth_date_dam', 'birth_date_mgd']
            for col in date_columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
            
            df['birth_year'] = df['birth_date'].dt.year
            df['dam_birth_year'] = df['birth_date_dam'].dt.year
            df['mgd_birth_year'] = df['birth_date_mgd'].dt.year
            
            # 读取年度数据
            yearly_data = {}
            with pd.ExcelFile(yearly_path) as xls:
                for sheet in xls.sheet_names:
                    yearly_data[sheet] = pd.read_excel(xls, sheet_name=sheet)
                    yearly_data[sheet].set_index('birth_year', inplace=True)
            
            # 获取默认值
            default_values = self.get_default_values(list(yearly_data.keys()))
            
            # 设置权重
            weights = {
                'sire': 0.5,
                'mgs': 0.25,
                'mmgs': 0.125,
                'default': 0.125
            }
            
            # 计算得分
            for trait in yearly_data.keys():
                score_column = f'{trait}_score'
                df[score_column] = self.calculate_single_trait_score(
                    df, trait, yearly_data[trait], default_values[trait], weights
                )
            
            return self.save_results_with_retry(df, output_path)
            
        except Exception as e:
            print(f"计算性状得分失败: {e}")
            return False

    def calculate_single_trait_score(self, df: pd.DataFrame, trait: str, 
                                   yearly_data: pd.DataFrame, default_value: float, 
                                   weights: dict) -> pd.Series:
        """计算单个性状的得分"""
        trait_score = pd.Series(0.0, index=df.index)
        
        # 处理sire
        sire_col = f'sire_{trait}'
        trait_score += self.calculate_bull_contribution(
            df, sire_col, 'birth_year', yearly_data, default_value, weights['sire']
        )
        
        # 处理mgs
        mgs_col = f'mgs_{trait}'
        trait_score += self.calculate_bull_contribution(
            df, mgs_col, 'dam_birth_year', yearly_data, default_value, weights['mgs']
        )
        
        # 处理mmgs
        mmgs_col = f'mmgs_{trait}'
        trait_score += self.calculate_bull_contribution(
            df, mmgs_col, 'mgd_birth_year', yearly_data, default_value, weights['mmgs']
        )
        
        # 添加默认值的贡献
        trait_score += weights['default'] * default_value
        
        return trait_score

    def calculate_bull_contribution(self, df: pd.DataFrame, trait_col: str, 
                                  year_col: str, yearly_data: pd.DataFrame, 
                                  default_value: float, weight: float) -> pd.Series:
        """计算单个公牛的贡献"""
        contribution = pd.Series(0.0, index=df.index)
        
        mask = pd.isna(df[trait_col])
        if year_col in df.columns:
            mask_with_year = mask & pd.notna(df[year_col])
            years = df.loc[mask_with_year, year_col].astype(int)
            valid_years = years[years.isin(yearly_data.index)]
            
            contribution.loc[valid_years.index] = (
                weight * yearly_data.loc[valid_years, 'mean'].values
            )
            
            # 对于有年份但无对应年度数据的情况使用默认值
            contribution.loc[mask] = weight * default_value
        else:
            contribution.loc[mask] = weight * default_value
        
        # 对于有性状值的情况直接使用实际值
        contribution.loc[~mask] = weight * df.loc[~mask, trait_col]
        
        return contribution

    def update_genomic_data(self, pedigree_path: Path, genomic_path: Path, 
                           output_path: Path) -> bool:
        """用基因组数据更新关键性状得分"""
        try:
            # 读取数据
            df_pedigree = pd.read_excel(pedigree_path)
            df_genomic = pd.read_excel(genomic_path)
            
            # 为所有得分列添加来源列
            score_columns = [col for col in df_pedigree.columns if col.endswith('_score')]
            for col in score_columns:
                df_pedigree[f"{col}_source"] = "P"
            
            # 用基因组数据更新得分
            for trait in [col.replace('_score', '') for col in score_columns]:
                score_col = f"{trait}_score"
                source_col = f"{trait}_score_source"
                
                # 遍历每一行数据
                for idx, row in df_pedigree.iterrows():
                    genomic_row = df_genomic[df_genomic['cow_id'] == row['cow_id']]
                    
                    if not genomic_row.empty and trait in genomic_row.columns:
                        if pd.notna(genomic_row[trait].iloc[0]):
                            df_pedigree.at[idx, score_col] = genomic_row[trait].iloc[0]
                            df_pedigree.at[idx, source_col] = "G"
            
            # 添加基因组性状计数列
            df_pedigree['genomic_traits_count'] = df_pedigree[
                [col for col in df_pedigree.columns if col.endswith('_source')]
            ].apply(lambda x: (x == "G").sum(), axis=1)
            
            # 保存结果
            return self.save_results_with_retry(df_pedigree, output_path)
            
        except Exception as e:
            print(f"更新基因组数据失败: {e}")
            return False