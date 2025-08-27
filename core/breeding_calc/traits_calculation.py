# core/breeding_calc/traits_calculation.py

from pathlib import Path
import pandas as pd
import numpy as np
import datetime
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

    def process_data(self, main_window, selected_traits: list, progress_callback=None, task_info_callback=None) -> Tuple[bool, str]:
        """执行关键性状计算的核心逻辑"""
        try:
            # 1. 初始化必要的设置
            print("1. 初始化数据库连接...")
            if task_info_callback:
                task_info_callback("初始化数据库连接")
            if progress_callback:
                progress_callback(5, "正在初始化数据库连接...")
            
            if not self.init_db_connection():
                return False, "连接数据库失败"

            project_path = main_window.selected_project_path
            success, error_msg = self.check_project_data(project_path, "processed_cow_data.xlsx")
            if not success:
                return False, error_msg

            # 2. 读取母牛数据，获取公牛列表
            print("2. 读取母牛数据...")
            if task_info_callback:
                task_info_callback("读取母牛数据")
            if progress_callback:
                progress_callback(10, "正在读取母牛数据文件...")
                
            cow_df = self.read_data(project_path, "processed_cow_data.xlsx")
            if cow_df is None:
                return False, "读取母牛数据失败"
            
            print(f"成功读取 {len(cow_df)} 条母牛记录")
            if progress_callback:
                progress_callback(15, f"成功读取 {len(cow_df)} 条母牛记录")
            
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
            
            print(f"共发现 {len(bull_ids)} 个公牛ID")
            if progress_callback:
                progress_callback(20, f"数据预处理完成，共发现 {len(bull_ids)} 个公牛ID")

            # 3. 处理每个公牛的性状数据
            print("3. 处理公牛性状数据...")
            if task_info_callback:
                task_info_callback("处理公牛性状数据")
            if progress_callback:
                progress_callback(25, "开始处理公牛性状数据...")
                
            bull_traits = {}
            total_bulls = len(bull_ids)
            for i, bull_id in enumerate(bull_ids, 1):
                print(f"处理公牛 {bull_id} ({i}/{total_bulls})")
                if task_info_callback:
                    task_info_callback(f"处理公牛 {bull_id} ({i}/{total_bulls})")
                if progress_callback and i % 10 == 0:  # 每10个公牛更新一次进度
                    current_progress = 25 + int((i / total_bulls) * 20)
                    progress_callback(current_progress, f"正在处理公牛 {i}/{total_bulls}: {bull_id}")
                    
                traits_data = self.get_bull_traits(bull_id, selected_traits)
                if traits_data:
                    bull_traits[bull_id] = traits_data

            if progress_callback:
                progress_callback(45, f"公牛性状数据处理完成，获取到 {len(bull_traits)} 个公牛的性状数据")

            # 4. 更新母牛数据中的公牛性状
            print("4. 更新母牛数据中的公牛性状...")
            if task_info_callback:
                task_info_callback("更新母牛数据中的公牛性状")
            if progress_callback:
                progress_callback(50, "开始更新母牛数据中的公牛性状...")
            
            for col in ['sire', 'mgs', 'mmgs']:
                for trait in selected_traits:
                    trait_col = f'{col}_{trait}'
                    cow_df[trait_col] = cow_df[col].map(lambda x: bull_traits.get(x, {}).get(trait))
                    identified_count = cow_df[trait_col].notna().sum()
                    print(f"{trait_col}: 找到 {identified_count} 条记录")

            if progress_callback:
                progress_callback(60, "母牛数据中的公牛性状更新完成")

            # 5. 保存详细结果
            print("5. 保存详细计算结果...")
            if task_info_callback:
                task_info_callback("保存详细计算结果")
            if progress_callback:
                progress_callback(65, "正在保存详细计算结果...")
                
            output_dir = project_path / "analysis_results"
            output_dir.mkdir(exist_ok=True)
            detail_output_path = output_dir / f"{self.output_prefix}_detail.xlsx"
            if not self.save_results_with_retry(cow_df, detail_output_path):
                return False, "保存详细结果失败"

            if progress_callback:
                progress_callback(70, f"详细结果已保存到: {detail_output_path.name}")

            # 6. 处理年度数据
            print("6. 处理年度数据...")
            if task_info_callback:
                task_info_callback("处理年度数据")
            if progress_callback:
                progress_callback(75, "正在处理年度数据...")
                
            yearly_output_path = output_dir / f"{self.output_prefix}_mean_by_year.xlsx"
            if not self.process_yearly_data(detail_output_path, yearly_output_path, selected_traits):
                return False, "处理年度数据失败"

            if progress_callback:
                progress_callback(80, f"年度数据处理完成，保存到: {yearly_output_path.name}")

            # 7. 计算性状得分
            print("7. 计算性状得分...")
            if task_info_callback:
                task_info_callback("计算性状得分")
            if progress_callback:
                progress_callback(85, "正在计算性状得分...")
                
            pedigree_output_path = output_dir / f"{self.output_prefix}_scores_pedigree.xlsx"
            if not self.calculate_trait_scores(detail_output_path, yearly_output_path, pedigree_output_path):
                return False, "计算性状得分失败"

            if progress_callback:
                progress_callback(90, f"性状得分计算完成，保存到: {pedigree_output_path.name}")

            # 8. 检查并处理基因组数据
            print("8. 检查基因组数据...")
            if task_info_callback:
                task_info_callback("检查并处理基因组数据")
            if progress_callback:
                progress_callback(95, "正在检查基因组数据...")
                
            genomic_data_path = project_path / "standardized_data" / "processed_genomic_data.xlsx"
            if genomic_data_path.exists():
                print("发现基因组数据，开始更新...")
                if progress_callback:
                    progress_callback(97, "发现基因组数据，正在更新...")
                genomic_output_path = output_dir / f"{self.output_prefix}_scores_genomic.xlsx"
                if not self.update_genomic_data(pedigree_output_path, genomic_data_path, genomic_output_path):
                    return False, "更新基因组数据失败"
                print("基因组数据更新完成")
                if progress_callback:
                    progress_callback(99, f"基因组数据更新完成，保存到: {genomic_output_path.name}")
            else:
                print("未找到基因组数据文件，跳过基因组数据更新")
                if progress_callback:
                    progress_callback(99, "未找到基因组数据文件，跳过基因组数据更新")

            if progress_callback:
                progress_callback(100, "所有计算步骤已完成！")
            if task_info_callback:
                task_info_callback("计算完成")
            print("所有计算步骤已完成!")
            return True, "计算完成"

        except Exception as e:
            print(f"计算过程出错: {str(e)}")
            if progress_callback:
                progress_callback(None, f"计算过程出错: {str(e)}")
            return False, str(e)

    def process_yearly_data(self, detail_path: Path, output_path: Path, selected_traits: list) -> bool:
        """处理年度关键性状数据"""
        try:
            # 读取详细数据
            df = pd.read_excel(detail_path)
            
            # 检查birth_year列是否存在
            if 'birth_year' not in df.columns:
                print("错误：数据中缺少birth_year列")
                return False
            
            # 清理birth_year数据，移除空值和无效值
            df = df.dropna(subset=['birth_year'])
            df['birth_year'] = pd.to_numeric(df['birth_year'], errors='coerce')
            df = df.dropna(subset=['birth_year'])
            
            # 过滤合理的年份范围（1900-当前年份+10）
            current_year = datetime.datetime.now().year
            df = df[(df['birth_year'] >= 1900) & (df['birth_year'] <= current_year + 10)]
            
            if len(df) == 0:
                print("错误：没有有效的出生年份数据")
                return False
            
            # 获取出生年份范围
            min_year = int(df['birth_year'].min())
            max_year = int(df['birth_year'].max())
            
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
            import traceback
            print(f"处理年度数据失败: {e}")
            print(f"详细错误信息: {traceback.format_exc()}")
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

    def update_genomic_data(self, pedigree_path: Path, genomic_path: Path, output_path: Path) -> bool:
        """用基因组数据更新关键性状得分"""
        try:
            # 1. 读取系谱数据文件
            df_pedigree = pd.read_excel(pedigree_path)
            
            # 2. 读取基因组数据
            df_genomic = pd.read_excel(genomic_path)
            
            # 打印基因组数据的列名以便调试
            print(f"基因组数据列名: {df_genomic.columns.tolist()[:30]}...")  # 打印前30个
            print(f"基因组数据行数: {len(df_genomic)}")
            
            # 检查cow_id列是否存在
            if 'cow_id' not in df_genomic.columns:
                print("警告：基因组数据中缺少cow_id列")
                return False
            
            # 打印部分cow_id以验证
            print(f"基因组数据中的前5个cow_id: {df_genomic['cow_id'].head().tolist()}")
            print(f"系谱数据中的前5个cow_id: {df_pedigree['cow_id'].head().tolist()}")
            
            # 3. 初始化数据来源标记
            score_columns = [col for col in df_pedigree.columns if col.endswith('_score')]
            for col in score_columns:
                df_pedigree[f"{col}_source"] = "P"  # 默认标记为系谱来源
            
            # 4. 更新得分和数据来源
            traits = [col[:-6] for col in score_columns]  # 去掉 '_score' 后缀
            print(f"需要匹配的性状: {traits}")
            
            # 检查基因组数据中存在哪些性状列
            existing_traits = []
            for trait in traits:
                if trait in df_genomic.columns:
                    existing_traits.append(trait)
            print(f"基因组数据中存在的性状: {existing_traits}")
            
            # 统计更新数量
            update_count = 0
            matched_cows = 0
            
            for idx, row in df_pedigree.iterrows():
                cow_id = row['cow_id']
                # 确保cow_id类型一致（都转为字符串）
                genomic_row = df_genomic[df_genomic['cow_id'].astype(str) == str(cow_id)]
                
                if not genomic_row.empty:
                    matched_cows += 1
                    # 遍历每个性状
                    for trait in traits:
                        score_col = f'{trait}_score'
                        source_col = f'{trait}_score_source'
                        
                        # 直接检查该性状是否在基因组数据中
                        if trait in genomic_row.columns:
                            trait_value = genomic_row[trait].iloc[0]
                            if pd.notna(trait_value):
                                df_pedigree.loc[idx, score_col] = trait_value
                                df_pedigree.loc[idx, source_col] = "G"
                                update_count += 1
                                if update_count <= 10:  # 只打印前10个更新
                                    print(f"更新: 母牛 {cow_id} 的 {trait} = {trait_value}")
            
            print(f"匹配到的母牛数: {matched_cows}")
            print(f"总共更新了 {update_count} 个性状值")
            
            # 5. 添加基因组性状计数列
            source_cols = [col for col in df_pedigree.columns if col.endswith('_source')]
            df_pedigree['genomic_traits_count'] = df_pedigree[source_cols].apply(
                lambda x: (x == "G").sum(), axis=1
            )
            
            # 6. 保存结果
            try:
                df_pedigree.to_excel(output_path, index=False)
                return True
            except PermissionError:
                print(f"文件 {output_path} 被占用")
                return False
            except Exception as e:
                print(f"保存基因组数据更新结果失败: {e}")
                return False
                
        except Exception as e:
            print(f"更新基因组数据时发生错误: {e}")
            return False

    def get_bull_traits(self, bull_id: str, selected_traits: list) -> dict:
        """
        从数据库获取公牛的性状数据
        
        Args:
            bull_id: 公牛ID
            selected_traits: 选中的性状列表
            
        Returns:
            dict: 包含性状数据的字典，如果未找到则返回None
        """
        try:
            if pd.isna(bull_id):
                return None
                
            bull_id = str(bull_id)  # 确保ID是字符串
            with self.db_engine.connect() as conn:
                # 先尝试用 BULL NAAB 查询
                if len(bull_id) <= 10:
                    result = conn.execute(
                        text("SELECT * FROM bull_library WHERE `BULL NAAB`=:bull_id"),
                        {"bull_id": bull_id}
                    ).fetchone()
                else:
                    # 对于长ID，使用 BULL REG 查询
                    result = conn.execute(
                        text("SELECT * FROM bull_library WHERE `BULL REG`=:bull_id"),
                        {"bull_id": bull_id}
                    ).fetchone()
                
                if result:
                    # 如果找到了公牛，提取所选性状数据
                    result_dict = dict(result._mapping)
                    return {trait: result_dict.get(trait) for trait in selected_traits}
                    
                return None
                
        except Exception as e:
            print(f"获取公牛 {bull_id} 的性状数据时发生错误: {e}")
            return None      