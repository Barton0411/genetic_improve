"""
矩阵式推荐生成器
生成完整的母牛×公牛配对矩阵，包含所有配对信息
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json

logger = logging.getLogger(__name__)

class MatrixRecommendationGenerator:
    """生成完整配对矩阵的推荐生成器"""
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.cow_data = None
        self.bull_data = None
        self.inbreeding_data = None
        self.genetic_defect_data = None
        self.cow_score_columns = []  # 存储找到的母牛得分列
        self.group_manager = None  # 分组管理器
        self.last_error = None  # 存储最后的错误信息
        self.skipped_bulls = []  # 存储被跳过的公牛
        
    def load_data(self, skip_missing_bulls: bool = False) -> bool:
        """加载所需数据

        Args:
            skip_missing_bulls: 是否跳过缺失数据的公牛继续选配
        """
        self.skip_missing_bulls_flag = skip_missing_bulls
        try:
            # 加载母牛数据
            cow_file = self.project_path / "analysis_results" / "processed_index_cow_index_scores.xlsx"
            if not cow_file.exists():
                error_msg = f"未找到母牛指数数据文件: {cow_file}"
                logger.error(error_msg)
                self.last_error = error_msg
                return False
            self.cow_data = pd.read_excel(cow_file)
            
            # 检查母牛得分列 - 查找任何包含 '_index' 或 'Index' 的列
            index_cols = [col for col in self.cow_data.columns if '_index' in col.lower() or 'index' in col.lower()]
            
            # 过滤掉明显不是得分的列（如 index_date 等）
            score_cols = [col for col in index_cols if not any(
                exclude in col.lower() for exclude in ['date', 'time', 'id', 'name', 'type']
            )]
            
            if not score_cols:
                logger.error("母牛数据中缺少育种指数得分列（如 *_index 或 *Index*），请先进行母牛育种指数计算")
                return False
            
            # 记录找到的得分列
            self.cow_score_columns = score_cols
            logger.info(f"找到母牛得分列: {score_cols}")
                
            logger.info(f"加载了 {len(self.cow_data)} 头母牛数据")
            
            # 加载公牛数据
            bull_file = self.project_path / "standardized_data" / "processed_bull_data.xlsx"
            if not bull_file.exists():
                error_msg = f"未找到公牛数据文件: {bull_file}"
                logger.error(error_msg)
                self.last_error = error_msg
                return False
            self.bull_data = pd.read_excel(bull_file)
            
            # 加载公牛性状数据（从数据库或其他文件）
            if not self._load_bull_traits():
                return False
            
            logger.info(f"加载了 {len(self.bull_data)} 头公牛数据")

            # 数据质量检查和汇总
            self._check_bull_data_quality()

            # 加载近交系数数据
            if not self._load_inbreeding_data():
                return False

            # 加载隐性基因数据
            if not self._load_genetic_defect_data():
                return False

            return True
            
        except Exception as e:
            error_msg = f"加载数据失败: {str(e)}"
            logger.error(error_msg)
            self.last_error = error_msg
            return False
            
    def _load_inbreeding_data(self):
        """加载近交系数数据"""
        try:
            # 尝试查找备选公牛近交系数文件
            possible_files = list(self.project_path.glob("**/备选公牛_近交系数及隐性基因分析结果_*.xlsx"))
            
            if not possible_files:
                error_msg = f"未找到备选公牛近交系数及隐性基因分析结果文件，请先进行「备选公牛近交和隐性基因分析」"
                logger.error(error_msg)
                self.last_error = error_msg
                return False
            
            # 使用最新的文件
            latest_file = max(possible_files, key=lambda x: x.stat().st_mtime)
            self.inbreeding_data = pd.read_excel(latest_file)
            logger.info(f"从 {latest_file.name} 加载了近交系数数据")
            
            # 验证数据完整性
            required_cols = ['母牛号', '原始备选公牛号', '后代近交系数']
            missing_cols = [col for col in required_cols if col not in self.inbreeding_data.columns]
            if missing_cols:
                error_msg = f"近交系数文件缺少必要列: {missing_cols}"
                logger.error(error_msg)
                self.last_error = error_msg
                return False
                
            return True
                
        except Exception as e:
            error_msg = f"加载近交系数数据失败: {e}"
            logger.error(error_msg)
            self.last_error = error_msg
            return False
            
    def _load_genetic_defect_data(self):
        """加载隐性基因数据"""
        try:
            # 通常和近交系数在同一个文件中
            if self.inbreeding_data is not None:
                self.genetic_defect_data = self.inbreeding_data
                
                # 验证是否包含隐性基因列
                defect_genes = ['HH1', 'HH2', 'HH3', 'HH4', 'HH5', 'HH6']
                found_genes = [gene for gene in defect_genes if gene in self.genetic_defect_data.columns]
                
                if not found_genes:
                    logger.warning("近交系数文件中未找到隐性基因数据列")
                    logger.warning("将跳过隐性基因检查")
                else:
                    logger.info(f"找到隐性基因列: {found_genes}")
                
                return True
            else:
                logger.error("隐性基因数据依赖于近交系数数据")
                return False
                    
        except Exception as e:
            logger.error(f"加载隐性基因数据失败: {e}")
            return False
            
    def _load_bull_traits(self):
        """加载公牛性状数据"""
        try:
            # 优先尝试从项目的公牛指数计算结果文件加载
            bull_scores_file = self.project_path / "analysis_results" / "processed_index_bull_scores.xlsx"
            if bull_scores_file.exists():
                bull_scores_df = pd.read_excel(bull_scores_file)
                
                # 查找指数列（类似母牛的处理方式）
                index_cols = [col for col in bull_scores_df.columns if '_index' in col.lower() or 'index' in col.lower()]
                score_cols = [col for col in index_cols if not any(
                    exclude in col.lower() for exclude in ['date', 'time', 'id', 'name', 'type']
                )]
                
                if score_cols:
                    # 使用找到的第一个指数列
                    score_col = score_cols[0]
                    logger.info(f"使用公牛指数列: {score_col}")
                    
                    # 合并到公牛数据
                    self.bull_data = self.bull_data.merge(
                        bull_scores_df[['bull_id', score_col]].rename(columns={score_col: 'Index Score'}),
                        on='bull_id',
                        how='left'
                    )
                    
                    # 检查是否有缺失值
                    missing_bulls = self.bull_data[self.bull_data['Index Score'].isna()]['bull_id'].tolist()
                    if missing_bulls:
                        logger.warning(f"以下公牛在指数文件中缺少数据，将尝试从数据库获取: {missing_bulls}")
                        # 记录但继续处理
                        self.skipped_bulls.extend(missing_bulls)

                    # 如果至少有一部分公牛有数据，继续处理
                    if self.bull_data['Index Score'].notna().any():
                        logger.info(f"从公牛指数文件加载了 {self.bull_data['Index Score'].notna().sum()} 头公牛数据")
                        # 继续尝试从数据库补充缺失的数据
                    else:
                        logger.warning("公牛指数文件中所有公牛都缺少数据，尝试从数据库获取")
                else:
                    logger.warning("公牛指数文件中未找到指数列")
            
            # 如果文件不存在或数据不完整，尝试从数据库获取
            from sqlalchemy import create_engine, text
            import os
            
            # 查找数据库文件
            db_path = self.project_path.parent.parent.parent / "local_bull_library.db"
            if not db_path.exists():
                # 尝试其他可能的路径
                db_path = Path("/Users/Shared/Files From d.localized/projects/mating/genetic_improve/local_bull_library.db")
            
            if db_path.exists():
                engine = create_engine(f'sqlite:///{db_path}')
                
                # 查询公牛性状
                query = """
                SELECT `BULL NAAB` as bull_id, `NM$`, `TPI`, `MILK`, `FAT`, `FAT %`, 
                       `PROT`, `PROT%`, `PL`, `DPR`, `UDC`, `FLC`, `RFI`
                FROM bull_library
                """
                
                with engine.connect() as conn:
                    bull_traits = pd.read_sql(text(query), conn)
                    
                # 合并到公牛数据中
                if not bull_traits.empty:
                    # 计算综合指数得分（使用TPI或NM$作为主要指标）
                    bull_traits['Index Score'] = bull_traits[['TPI', 'NM$']].max(axis=1)
                    
                    # 合并数据
                    self.bull_data = self.bull_data.merge(
                        bull_traits[['bull_id', 'Index Score', 'TPI', 'NM$']], 
                        on='bull_id', 
                        how='left'
                    )
                    
                    # 补充缺失数据的公牛性状
                    missing_bulls = self.bull_data[self.bull_data['Index Score'].isna()]['bull_id'].tolist()
                    if missing_bulls:
                        # 只为缺失的公牛补充数据
                        missing_traits = bull_traits[bull_traits['bull_id'].isin(missing_bulls)]
                        if not missing_traits.empty:
                            missing_traits['Index Score'] = missing_traits[['TPI', 'NM$']].max(axis=1)
                            # 更新缺失的数据
                            for _, bull in missing_traits.iterrows():
                                self.bull_data.loc[self.bull_data['bull_id'] == bull['bull_id'], 'Index Score'] = bull['Index Score']
                    
                    engine.dispose()
                    
                    # 最终检查
                    final_missing = self.bull_data[self.bull_data['Index Score'].isna()]['bull_id'].tolist()
                    if final_missing:
                        # 记录被跳过的公牛
                        self.skipped_bulls = list(set(self.skipped_bulls + final_missing))

                        valid_count = self.bull_data['Index Score'].notna().sum()
                        if valid_count > 0:
                            # 有部分公牛有数据，允许继续
                            warning_msg = f"以下 {len(final_missing)} 头公牛缺少性状数据，将被跳过选配: {final_missing[:5]}{'...' if len(final_missing) > 5 else ''}"
                            logger.warning(warning_msg)
                            self.last_error = f"警告: {warning_msg}\n但有 {valid_count} 头公牛可用于选配"
                            logger.info(f"使用 {valid_count} 头公牛的数据进行选配")
                            return True
                        else:
                            # 没有任何公牛有数据
                            error_msg = f"所有公牛都缺少性状数据，无法进行选配。\n缺失的公牛: {final_missing[:10]}...（共{len(final_missing)}头）\n请先进行公牛育种指数计算或更新公牛数据库"
                            logger.error(error_msg)
                            self.last_error = error_msg
                            return False
                    
                    logger.info("成功从数据库补充公牛性状数据")
                    return True
                else:
                    engine.dispose()
                    # 检查是否已经有数据
                    if 'Index Score' in self.bull_data.columns and self.bull_data['Index Score'].notna().any():
                        logger.info("使用已有的公牛指数数据")
                        return True
                    else:
                        error_msg = "公牛数据库中没有性状数据，请先进行公牛育种指数计算"
                        logger.error(error_msg)
                        self.last_error = error_msg
                        return False
            else:
                # 检查是否已经从文件加载了数据
                if 'Index Score' in self.bull_data.columns and self.bull_data['Index Score'].notna().all():
                    logger.info("使用公牛指数文件数据")
                    return True
                else:
                    # 即使没有数据库，如果有部分公牛有数据也允许继续
                    if 'Index Score' in self.bull_data.columns and self.bull_data['Index Score'].notna().any():
                        valid_count = self.bull_data['Index Score'].notna().sum()
                        missing_bulls = self.bull_data[self.bull_data['Index Score'].isna()]['bull_id'].tolist()

                        # 记录被跳过的公牛
                        self.skipped_bulls = list(set(self.skipped_bulls + missing_bulls))

                        if missing_bulls:
                            warning_msg = f"以下 {len(missing_bulls)} 头公牛缺少指数数据，将被跳过选配: {missing_bulls[:5]}{'...' if len(missing_bulls) > 5 else ''}"
                            logger.warning(warning_msg)
                            self.last_error = f"警告: {warning_msg}\n但有 {valid_count} 头公牛可用于选配"

                        logger.info(f"使用 {valid_count} 头公牛的指数数据进行选配")
                        return True
                    else:
                        error_msg = "所有公牛都缺少指数数据，无法进行选配。请先进行公牛育种指数计算"
                        logger.error(error_msg)
                        self.last_error = error_msg
                        return False
                
        except Exception as e:
            logger.error(f"加载公牛性状失败: {e}")
            # 检查是否已经有数据
            if 'Index Score' in self.bull_data.columns and self.bull_data['Index Score'].notna().any():
                logger.info("使用已有的公牛指数数据")
                return True
            else:
                logger.error("请先进行公牛育种指数计算")
                return False

    def _check_bull_data_quality(self):
        """检查公牛数据质量并生成汇总报告"""
        if self.bull_data.empty:
            return

        total_bulls = len(self.bull_data)
        regular_bulls = len(self.bull_data[self.bull_data['classification'] == '常规'])
        sexed_bulls = len(self.bull_data[self.bull_data['classification'] == '性控'])

        # 检查库存
        no_inventory = 0
        low_inventory = 0
        if '支数' in self.bull_data.columns:
            no_inventory = self.bull_data[
                self.bull_data['支数'].isna() | (self.bull_data['支数'] <= 0)
            ].shape[0]
            low_inventory = self.bull_data[
                (self.bull_data['支数'] > 0) & (self.bull_data['支数'] < 5)
            ].shape[0]

        # 检查数据完整性
        no_data = 0
        if 'Index Score' in self.bull_data.columns:
            no_data = self.bull_data['Index Score'].isna().sum()

        # 生成汇总报告
        logger.info("=" * 60)
        logger.info("公牛数据质量汇总")
        logger.info("=" * 60)
        logger.info(f"总公牛数: {total_bulls} (常规: {regular_bulls}, 性控: {sexed_bulls})")

        if no_inventory > 0 or low_inventory > 0:
            logger.warning(f"库存问题: 无库存 {no_inventory} 头, 低库存(<5) {low_inventory} 头")

        if no_data > 0:
            logger.warning(f"数据问题: {no_data} 头公牛缺少Index Score")
            # 列出缺少数据的公牛
            missing_data_bulls = self.bull_data[self.bull_data['Index Score'].isna()]['bull_id'].tolist()
            if len(missing_data_bulls) <= 10:
                logger.warning(f"  缺少数据的公牛: {missing_data_bulls}")
            else:
                logger.warning(f"  缺少数据的公牛(前10头): {missing_data_bulls[:10]}...")

        # 统计将被使用的有效公牛数
        valid_bulls = self.bull_data[
            (self.bull_data['支数'] > 0) &
            (self.bull_data['Index Score'].notna())
        ]
        valid_regular = len(valid_bulls[valid_bulls['classification'] == '常规'])
        valid_sexed = len(valid_bulls[valid_bulls['classification'] == '性控'])

        logger.info(f"有效公牛数(有库存且有数据): {len(valid_bulls)} (常规: {valid_regular}, 性控: {valid_sexed})")

        # 【优化】直接过滤公牛数据，只保留有效的公牛，避免后续重复检查
        original_count = len(self.bull_data)
        self.bull_data = valid_bulls.copy()
        if original_count > len(self.bull_data):
            filtered_bulls = original_count - len(self.bull_data)
            logger.info(f"已过滤 {filtered_bulls} 头无效公牛（无库存或无数据），后续将不再检查")

            # 记录被过滤的公牛ID，便于追踪
            if 'Index Score' in self.bull_data.columns:
                filtered_bull_ids = []
                for _, bull in pd.concat([
                    self.bull_data[self.bull_data['支数'].isna() | (self.bull_data['支数'] <= 0)],
                    self.bull_data[self.bull_data['Index Score'].isna()]
                ]).drop_duplicates().iterrows():
                    if bull['bull_id'] not in self.bull_data['bull_id'].values:
                        filtered_bull_ids.append(bull['bull_id'])
                if filtered_bull_ids and len(filtered_bull_ids) <= 5:
                    logger.debug(f"被过滤的公牛: {filtered_bull_ids}")

        logger.info("=" * 60)

    def generate_matrices(self, progress_callback=None) -> Dict[str, pd.DataFrame]:
        """生成所有配对矩阵

        Args:
            progress_callback: 进度回调函数，接收(message, percentage)
        """
        logger.info("开始生成配对矩阵...")

        if progress_callback:
            progress_callback("正在准备数据...", 5)

        # 准备母牛和公牛ID列表
        cow_ids = self.cow_data['cow_id'].astype(str).tolist()

        # 过滤掉没有Index Score的公牛
        valid_bull_data = self.bull_data[self.bull_data['Index Score'].notna()].copy()
        skipped_count = len(self.bull_data) - len(valid_bull_data)
        if skipped_count > 0:
            logger.info(f"过滤掉 {skipped_count} 头缺少指数数据的公牛")

        # 分别处理常规和性控公牛
        regular_bulls = valid_bull_data[valid_bull_data['classification'] == '常规']
        sexed_bulls = valid_bull_data[valid_bull_data['classification'] == '性控']

        regular_bull_ids = regular_bulls['bull_id'].astype(str).tolist() if not regular_bulls.empty else []
        sexed_bull_ids = sexed_bulls['bull_id'].astype(str).tolist() if not sexed_bulls.empty else []

        # 创建结果字典
        matrices = {}

        # 生成常规冻精矩阵
        if regular_bull_ids:
            logger.info(f"生成常规冻精配对矩阵 ({len(cow_ids)}×{len(regular_bull_ids)})")

            if progress_callback:
                progress_callback(f"生成常规后代得分矩阵 ({len(cow_ids)}×{len(regular_bull_ids)})...", 10)
            matrices['常规_后代得分'] = self._create_score_matrix(cow_ids, regular_bull_ids, regular_bulls)

            if progress_callback:
                progress_callback(f"生成常规近交系数矩阵...", 20)
            matrices['常规_近交系数'] = self._create_inbreeding_matrix(cow_ids, regular_bull_ids)

            if progress_callback:
                progress_callback(f"生成常规隐性基因矩阵...", 30)
            matrices['常规_隐性基因'] = self._create_genetic_defect_matrix(cow_ids, regular_bull_ids)

        # 生成性控冻精矩阵
        if sexed_bull_ids:
            logger.info(f"生成性控冻精配对矩阵 ({len(cow_ids)}×{len(sexed_bull_ids)})")

            if progress_callback:
                progress_callback(f"生成性控后代得分矩阵 ({len(cow_ids)}×{len(sexed_bull_ids)})...", 50)
            matrices['性控_后代得分'] = self._create_score_matrix(cow_ids, sexed_bull_ids, sexed_bulls)

            if progress_callback:
                progress_callback(f"生成性控近交系数矩阵...", 60)
            matrices['性控_近交系数'] = self._create_inbreeding_matrix(cow_ids, sexed_bull_ids)

            if progress_callback:
                progress_callback(f"生成性控隐性基因矩阵...", 70)
            matrices['性控_隐性基因'] = self._create_genetic_defect_matrix(cow_ids, sexed_bull_ids)

        # 生成推荐汇总（保持原有格式的兼容性）
        logger.info("生成推荐汇总...")
        if progress_callback:
            progress_callback("生成推荐汇总...", 85)

        matrices['推荐汇总'] = self._generate_recommendation_summary()

        if progress_callback:
            progress_callback("矩阵生成完成", 95)

        return matrices
        
    def _create_score_matrix(self, cow_ids: List[str], bull_ids: List[str], bull_df: pd.DataFrame) -> pd.DataFrame:
        """创建后代得分矩阵（优化版）"""
        import numpy as np

        # 检查公牛数据
        if 'Index Score' not in bull_df.columns:
            raise ValueError("公牛数据缺少Index Score列")

        # 预处理：获取公牛得分向量
        bull_scores_dict = dict(zip(
            bull_df['bull_id'].astype(str),
            bull_df['Index Score']
        ))
        bull_scores = np.array([bull_scores_dict[bid] for bid in bull_ids])

        # 预处理：获取母牛得分向量
        cow_scores = []
        for cow_id in cow_ids:
            cow_row = self.cow_data[self.cow_data['cow_id'].astype(str) == cow_id]
            if not cow_row.empty:
                # 从已识别的得分列中获取得分
                score_found = False
                for col in self.cow_score_columns:
                    if col in cow_row.columns and pd.notna(cow_row.iloc[0][col]):
                        cow_scores.append(cow_row.iloc[0][col])
                        score_found = True
                        break

                if not score_found:
                    raise ValueError(f"母牛 {cow_id} 缺少得分数据")
            else:
                raise ValueError(f"找不到母牛 {cow_id} 的数据")

        cow_scores = np.array(cow_scores)

        # 向量化计算后代得分矩阵
        # 使用广播创建矩阵：每个母牛得分与所有公牛得分的平均
        cow_matrix = cow_scores.reshape(-1, 1)  # 列向量
        bull_matrix = bull_scores.reshape(1, -1)  # 行向量

        # 后代得分 = 双亲平均
        offspring_scores = 0.5 * (cow_matrix + bull_matrix)

        # 创建DataFrame并四舍五入
        score_matrix = pd.DataFrame(
            np.round(offspring_scores, 2),
            index=cow_ids,
            columns=bull_ids
        )

        return score_matrix
        
    def _create_inbreeding_matrix(self, cow_ids: List[str], bull_ids: List[str]) -> pd.DataFrame:
        """创建近交系数矩阵（优化版）"""
        import numpy as np

        # 如果没有近交数据，直接返回全0矩阵
        if self.inbreeding_data is None:
            logger.info("没有近交系数数据，使用默认值0")
            return pd.DataFrame("0.000%", index=cow_ids, columns=bull_ids)

        # 预处理：创建查找字典
        inbreeding_dict = {}

        # 找到实际的列名
        cow_cols = ['母牛号', 'dam_id', 'cow_id']
        bull_cols = ['原始备选公牛号', '备选公牛号', '公牛号', 'sire_id', 'bull_id']
        coeff_cols = ['后代近交系数', '近交系数', 'inbreeding_coefficient']

        cow_col = next((col for col in cow_cols if col in self.inbreeding_data.columns), None)
        bull_col = next((col for col in bull_cols if col in self.inbreeding_data.columns), None)
        coeff_col = next((col for col in coeff_cols if col in self.inbreeding_data.columns), None)

        if cow_col and bull_col and coeff_col:
            # 构建查找字典，一次遍历
            for _, row in self.inbreeding_data.iterrows():
                key = (str(row[cow_col]), str(row[bull_col]))
                value = row[coeff_col]
                if pd.notna(value):
                    if isinstance(value, str) and '%' in value:
                        value = float(value.replace('%', '')) / 100
                    inbreeding_dict[key] = float(value)

        # 使用向量化操作创建矩阵
        result = np.zeros((len(cow_ids), len(bull_ids)))

        for i, cow_id in enumerate(cow_ids):
            for j, bull_id in enumerate(bull_ids):
                key = (str(cow_id), str(bull_id))
                result[i, j] = inbreeding_dict.get(key, 0.0)

        # 转换为DataFrame并格式化
        inbreeding_matrix = pd.DataFrame(result, index=cow_ids, columns=bull_ids)

        # 向量化格式化
        formatted_matrix = inbreeding_matrix.applymap(lambda x: f"{x*100:.3f}%")

        non_zero_count = (inbreeding_matrix > 0).sum().sum()
        logger.info(f"近交系数矩阵：非零值数量 = {non_zero_count}/{len(cow_ids)*len(bull_ids)}")

        return formatted_matrix
        
    def _create_genetic_defect_matrix(self, cow_ids: List[str], bull_ids: List[str]) -> pd.DataFrame:
        """创建隐性基因状态矩阵（优化版）"""
        import numpy as np

        # 如果没有隐性基因数据，直接返回全"safe"矩阵
        if self.genetic_defect_data is None:
            logger.info("没有隐性基因数据，使用默认值safe")
            return pd.DataFrame("safe", index=cow_ids, columns=bull_ids)

        # 预处理：创建查找字典
        cow_defects = {}
        bull_defects = {}

        # 找到实际的列名
        id_cols = ['母牛号', '公牛号', 'animal_id', 'bull_id', 'cow_id']
        defect_cols = [col for col in self.genetic_defect_data.columns if col not in id_cols]

        id_col = next((col for col in id_cols if col in self.genetic_defect_data.columns), None)

        if id_col and defect_cols:
            # 构建查找字典
            for _, row in self.genetic_defect_data.iterrows():
                animal_id = str(row[id_col])
                defects = []
                for col in defect_cols:
                    if pd.notna(row[col]) and str(row[col]).upper() == 'C':
                        defects.append(col)

                # 同时存储到母牛和公牛字典中
                if animal_id in cow_ids:
                    cow_defects[animal_id] = defects
                if animal_id in bull_ids:
                    bull_defects[animal_id] = defects

        # 使用向量化操作创建矩阵
        result = []

        for cow_id in cow_ids:
            row_result = []
            cow_carriers = cow_defects.get(str(cow_id), [])

            for bull_id in bull_ids:
                bull_carriers = bull_defects.get(str(bull_id), [])

                # 检查是否有相同的隐性基因携带
                if cow_carriers and bull_carriers:
                    common = set(cow_carriers) & set(bull_carriers)
                    if common:
                        row_result.append("risk")
                    else:
                        row_result.append("safe")
                else:
                    row_result.append("safe")

            result.append(row_result)

        genetic_matrix = pd.DataFrame(result, index=cow_ids, columns=bull_ids)

        risk_count = (genetic_matrix == "risk").sum().sum()
        logger.info(f"隐性基因矩阵：风险配对数量 = {risk_count}/{len(cow_ids)*len(bull_ids)}")

        return genetic_matrix
        
    def _get_inbreeding_coefficient(self, cow_id: str, bull_id: str) -> float:
        """获取近交系数"""
        if self.inbreeding_data is None:
            return 0.0
            
        try:
            # 尝试不同的列名组合
            cow_cols = ['母牛号', 'dam_id', 'cow_id']
            bull_cols = ['原始备选公牛号', '备选公牛号', '公牛号', 'sire_id', 'bull_id']
            coeff_cols = ['后代近交系数', '近交系数', 'inbreeding_coefficient']  # 优先使用后代近交系数
            
            # 找到实际的列名
            cow_col = next((col for col in cow_cols if col in self.inbreeding_data.columns), None)
            bull_col = next((col for col in bull_cols if col in self.inbreeding_data.columns), None)
            coeff_col = next((col for col in coeff_cols if col in self.inbreeding_data.columns), None)
            
            if not all([cow_col, bull_col, coeff_col]):
                logger.debug(f"缺少必要列: cow_col={cow_col}, bull_col={bull_col}, coeff_col={coeff_col}")
                return 0.0
                
            # 查找数据
            mask = (self.inbreeding_data[cow_col].astype(str) == str(cow_id)) & \
                   (self.inbreeding_data[bull_col].astype(str) == str(bull_id))
            
            # 调试特定配对
            if cow_id == '24115' and bull_id == '007HO16284':
                logger.debug(f"调试配对 24115-007HO16284:")
                logger.debug(f"  使用列: {cow_col}={cow_id}, {bull_col}={bull_id}")
                logger.debug(f"  找到记录数: {mask.sum()}")
                if mask.any():
                    row = self.inbreeding_data.loc[mask].iloc[0]
                    logger.debug(f"  {coeff_col}: {row[coeff_col]}")
                   
            if mask.any():
                coeff = self.inbreeding_data.loc[mask, coeff_col].iloc[0]
                # 处理百分比格式
                if isinstance(coeff, str):
                    if '%' in coeff:
                        # 去掉百分号并转换
                        value = float(coeff.replace('%', '')) / 100
                        if cow_id == '24115' and bull_id == '007HO16284':
                            logger.debug(f"  解析结果: '{coeff}' -> {value}")
                        return value
                    else:
                        # 尝试直接转换
                        try:
                            return float(coeff)
                        except:
                            return 0.0
                return float(coeff) if pd.notna(coeff) else 0.0
                
        except Exception as e:
            logger.debug(f"获取近交系数失败 ({cow_id}, {bull_id}): {e}")
            
        return 0.0
    
    def _get_cow_score(self, cow_data):
        """从母牛数据中获取得分"""
        # 尝试从已识别的得分列中获取
        for col in self.cow_score_columns:
            if isinstance(cow_data, pd.Series):
                if col in cow_data.index and pd.notna(cow_data[col]):
                    return cow_data[col]
            elif isinstance(cow_data, dict):
                if col in cow_data and pd.notna(cow_data.get(col)):
                    return cow_data[col]
        return None
        
    def _check_genetic_defects(self, cow_id: str, bull_id: str) -> str:
        """检查隐性基因状态"""
        if self.genetic_defect_data is None:
            return "Safe"
            
        try:
            # 尝试不同的列名组合
            cow_cols = ['母牛号', 'dam_id', 'cow_id']
            bull_cols = ['原始备选公牛号', '备选公牛号', '公牛号', 'sire_id', 'bull_id']
            
            # 找到实际的列名
            cow_col = next((col for col in cow_cols if col in self.genetic_defect_data.columns), None)
            bull_col = next((col for col in bull_cols if col in self.genetic_defect_data.columns), None)
            
            if not all([cow_col, bull_col]):
                return "Safe"
                
            # 查找数据
            mask = (self.genetic_defect_data[cow_col].astype(str) == str(cow_id)) & \
                   (self.genetic_defect_data[bull_col].astype(str) == str(bull_id))
                   
            if mask.any():
                row = self.genetic_defect_data.loc[mask].iloc[0]
                
                # 检查各种隐性基因
                defect_genes = ['HH1', 'HH2', 'HH3', 'HH4', 'HH5', 'HH6', 
                               'MW', 'BLAD', 'CVM', 'DUMPS', 'Citrullinemia',
                               'Brachyspina', 'Factor XI', 'Mulefoot', 
                               'Cholesterol deficiency', 'Chondrodysplasia']
                
                for gene in defect_genes:
                    if gene in row.index:
                        status = str(row[gene]).strip()
                        # 新的判定逻辑：只检查 '高风险' 状态
                        if status == '高风险':
                            logger.debug(f"检测到隐性基因风险: {gene}={row[gene]} for {cow_id} x {bull_id}")
                            return "高风险"
                            
        except Exception as e:
            logger.debug(f"检查隐性基因失败 ({cow_id}, {bull_id}): {e}")
            
        return "-"
        
    def _generate_recommendation_summary(self) -> pd.DataFrame:
        """生成推荐汇总（兼容原有格式）"""
        recommendations = []
        skipped_cows = 0
        
        logger.info(f"开始生成推荐汇总，母牛总数: {len(self.cow_data)}")
        
        for _, cow in self.cow_data.iterrows():
            cow_id = str(cow['cow_id'])
            
            # 复制母牛基本信息
            rec = {
                'cow_id': cow_id,
                'breed': cow.get('breed', ''),
                'group': cow.get('group', ''),
                'birth_date': cow.get('birth_date', ''),
                'index_score': self._get_cow_score(cow)
            }
            
            has_valid_bulls = False  # 标记是否有任何有效的公牛
            
            # 为每种冻精类型生成前3个推荐
            for semen_type in ['常规', '性控']:
                type_bulls = self.bull_data[self.bull_data['classification'] == semen_type]

                if not type_bulls.empty:
                    # 【优化】数据已在加载时过滤，直接使用有效公牛
                    valid_type_bulls = []

                    for _, bull in type_bulls.iterrows():
                        bull_id = str(bull['bull_id'])
                        bull_score = bull['Index Score']
                        valid_type_bulls.append((bull_id, bull_score, bull))

                    # 计算有效公牛的得分
                    bull_scores = []
                    for bull_id, bull_score, bull in valid_type_bulls:
                        
                        # 获取母牛得分
                        cow_score = self._get_cow_score(cow)
                        
                        if cow_score is None:
                            # 跳过没有得分的母牛
                            if len(bull_scores) == 0:  # 只在第一次记录
                                logger.warning(f"母牛 {cow_id} 没有得分，跳过该母牛")
                                skipped_cows += 1
                            continue
                        offspring_score = 0.5 * (cow_score + bull_score)
                        inbreeding_coeff = self._get_inbreeding_coefficient(cow_id, bull_id)
                        gene_status = self._check_genetic_defects(cow_id, bull_id)
                        
                        # 只添加满足约束的公牛（避开高风险）
                        if inbreeding_coeff <= 0.03125 and gene_status != '高风险':
                            bull_scores.append({
                                'bull_id': bull_id,
                                'offspring_score': offspring_score,
                                'inbreeding_coeff': inbreeding_coeff,
                                'gene_status': gene_status
                            })
                    
                    # 按得分排序
                    bull_scores.sort(key=lambda x: x['offspring_score'], reverse=True)
                    
                    if bull_scores:  # 如果有有效的公牛
                        has_valid_bulls = True
                    
                    # 保存前3个推荐
                    for i in range(min(3, len(bull_scores))):
                        if i < len(bull_scores):
                            rec[f'推荐{semen_type}冻精{i+1}选'] = bull_scores[i]['bull_id']
                            rec[f'{semen_type}冻精{i+1}近交系数'] = f"{bull_scores[i]['inbreeding_coeff']*100:.3f}%"
                            rec[f'{semen_type}冻精{i+1}隐性基因情况'] = bull_scores[i]['gene_status']
                            rec[f'{semen_type}冻精{i+1}得分'] = round(bull_scores[i]['offspring_score'], 2)
                        else:
                            rec[f'推荐{semen_type}冻精{i+1}选'] = ''
                            rec[f'{semen_type}冻精{i+1}近交系数'] = ''
                            rec[f'{semen_type}冻精{i+1}隐性基因情况'] = ''
                            rec[f'{semen_type}冻精{i+1}得分'] = ''
                    
                    # 保存所有有效公牛信息（不只是前3个，用于递进机制）
                    rec[f'{semen_type}_valid_bulls'] = str(bull_scores)
            
            if not has_valid_bulls:
                logger.warning(f"母牛 {cow_id} 没有任何有效的公牛可选（可能因为近交系数或隐性基因约束）")
                skipped_cows += 1
                # 但仍然添加到推荐列表中，以便在分配时显示为无法分配
                            
            recommendations.append(rec)
        
        logger.info(f"推荐汇总生成完成:")
        logger.info(f"  总母牛数: {len(self.cow_data)}")
        logger.info(f"  跳过的母牛数: {skipped_cows}")
        logger.info(f"  生成推荐的母牛数: {len(recommendations)}")
        
        return pd.DataFrame(recommendations)
        
    def save_matrices(self, matrices: Dict[str, pd.DataFrame], output_file: Path):
        """保存所有矩阵到Excel文件"""
        try:
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                for sheet_name, df in matrices.items():
                    df.to_excel(writer, sheet_name=sheet_name)
                    
                    # 调整列宽
                    worksheet = writer.sheets[sheet_name]
                    for column in worksheet.columns:
                        max_length = 0
                        column = [cell for cell in column]
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 30)
                        worksheet.column_dimensions[column[0].column_letter].width = adjusted_width
                        
            logger.info(f"配对矩阵已保存至: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存配对矩阵失败: {e}")
            return False