"""
数据生成器模块

负责调用原有的数据生成函数，为PPT报告准备数据
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
import pandas as pd
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)


class DataGenerator:
    """数据生成器类，封装原有的数据生成逻辑"""
    
    def __init__(self, output_folder: str):
        """
        初始化数据生成器
        
        Args:
            output_folder: 输出文件夹路径
        """
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(exist_ok=True)
        
    def generate_pedigree_identification_analysis(self, table_c: pd.DataFrame, cow_df: pd.DataFrame) -> bool:
        """
        生成系谱识别情况分析表
        
        Args:
            table_c: 包含牛只系谱信息的表格
            cow_df: 牛只基本信息
            
        Returns:
            是否成功生成
        """
        try:
            merged_df = table_c.copy()
            
            # 添加性别限制，排除性别为"公"的记录
            merged_df = merged_df[merged_df['sex'] != '公']
            
            # 获取牛群中的最大出生年份
            max_birth_year = merged_df['birth_year'].max()
            
            # 创建出生年份分组
            merged_df['birth_year_group'] = pd.cut(
                merged_df['birth_year'],
                bins=[-float('inf')] + list(range(max_birth_year-4, max_birth_year)) + [float('inf')],
                labels=[f'{max_birth_year-4}年及以前'] + [str(year) for year in range(max_birth_year-3, max_birth_year+1)]
            )
            
            # 创建分析函数
            def analyze_group(group):
                total = len(group)
                sire_identified = (group['sire_identified'] == '已识别').sum()
                mgs_identified = (group['mgs_identified'] == '已识别').sum()
                mmgs_identified = (group['mmgs_identified'] == '已识别').sum()
                return pd.Series({
                    '头数': total,
                    '父号可识别头数': sire_identified,
                    '父号识别率': sire_identified / total if total > 0 else 0,
                    '外祖父可识别头数': mgs_identified,
                    '外祖父识别率': mgs_identified / total if total > 0 else 0,
                    '外曾外祖父可识别头数': mmgs_identified,
                    '外曾外祖父识别率': mmgs_identified / total if total > 0 else 0,
                })
            
            # 总体分析
            results = []
            total_result = merged_df.groupby('birth_year_group').apply(analyze_group).reset_index()
            total_result['是否在场'] = '总计'
            results.append(total_result)
            
            # 添加总计的合计行
            total_summary = merged_df.pipe(analyze_group)
            total_summary = pd.DataFrame(total_summary).T.reset_index(drop=True)
            total_summary['birth_year_group'] = '合计'
            total_summary['是否在场'] = '总计'
            results.append(total_summary)
            
            # 添加空行
            empty_row = pd.DataFrame({'是否在场': [''], 'birth_year_group': ['']})
            results.append(empty_row)
            
            # 按是否在场分组并创建结果表
            for in_herd in merged_df['是否在场'].unique():
                df_in_herd = merged_df[merged_df['是否在场'] == in_herd]
                result = df_in_herd.groupby('birth_year_group').apply(analyze_group).reset_index()
                result['是否在场'] = in_herd
                results.append(result)
                
                # 添加小计行
                subtotal = df_in_herd.pipe(analyze_group)
                subtotal = pd.DataFrame(subtotal).T.reset_index(drop=True)
                subtotal['birth_year_group'] = '合计'
                subtotal['是否在场'] = in_herd
                results.append(subtotal)
                
                # 添加空行
                results.append(empty_row)
            
            # 合并所有结果
            final_result = pd.concat(results, ignore_index=True)
            
            # 重新排序列
            final_result = final_result[[
                '是否在场', 'birth_year_group', '头数', 
                '父号可识别头数', '父号识别率', 
                '外祖父可识别头数', '外祖父识别率', 
                '外曾外祖父可识别头数', '外曾外祖父识别率'
            ]]
            
            # 格式化百分比列
            percentage_columns = ['父号识别率', '外祖父识别率', '外曾外祖父识别率']
            for col in percentage_columns:
                final_result[col] = final_result[col].apply(lambda x: f"{x:.2%}" if pd.notnull(x) else '')
            
            # 保存结果
            output_file = self.output_folder / "结果-系谱识别情况分析.xlsx"
            final_result.to_excel(output_file, index=False)
            logger.info(f"系谱识别情况分析表已保存至: {output_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"生成系谱识别情况分析失败: {str(e)}")
            return False
    
    def generate_key_traits_annual_change(self, merged_cow_key_traits_scores: pd.DataFrame, 
                                         selected_traits: List[str]) -> bool:
        """
        生成关键性状年度变化表
        
        Args:
            merged_cow_key_traits_scores: 合并的母牛关键性状数据
            selected_traits: 选中的性状列表
            
        Returns:
            是否成功生成
        """
        try:
            # 确保birth_date是日期类型
            merged_cow_key_traits_scores['birth_date'] = pd.to_datetime(
                merged_cow_key_traits_scores['birth_date']
            )
            
            # 获取牛群中的最大出生年份
            max_birth_year = merged_cow_key_traits_scores['birth_date'].dt.year.max()
            
            # 创建出生年份分组
            merged_cow_key_traits_scores['birth_year_group'] = pd.cut(
                merged_cow_key_traits_scores['birth_date'].dt.year,
                bins=[-float('inf')] + list(range(max_birth_year-4, max_birth_year)) + [float('inf')],
                labels=[f'{max_birth_year-4}年及以前'] + [f'{year}年' for year in range(max_birth_year-3, max_birth_year+1)]
            )
            
            # 创建分析函数
            def analyze_group(group):
                total = len(group)
                result = {'头数': total}
                for trait in selected_traits:
                    if trait in group.columns:
                        result[trait] = round(group[trait].mean(), 2)
                return pd.Series(result)
            
            # 总体分析
            results = []
            
            total_result = merged_cow_key_traits_scores.groupby(
                'birth_year_group', observed=True
            ).apply(analyze_group).reset_index()
            total_result['是否在场'] = '合计'
            results.append(total_result)
            
            # 添加总计的合计行
            total_summary = merged_cow_key_traits_scores.pipe(analyze_group)
            total_summary = pd.DataFrame(total_summary).T.reset_index(drop=True)
            total_summary['birth_year_group'] = '合计'
            total_summary['是否在场'] = '合计'
            results.append(total_summary)
            
            # 添加空行
            empty_row = pd.DataFrame({'是否在场': [''], 'birth_year_group': ['']})
            results.append(empty_row)
            
            # 按是否在场分组并创建结果表
            if '是否在场' in merged_cow_key_traits_scores.columns:
                for in_herd in merged_cow_key_traits_scores['是否在场'].unique():
                    df_in_herd = merged_cow_key_traits_scores[
                        merged_cow_key_traits_scores['是否在场'] == in_herd
                    ]
                    result = df_in_herd.groupby('birth_year_group').apply(analyze_group).reset_index()
                    result['是否在场'] = in_herd
                    results.append(result)
                    
                    # 添加小计行
                    subtotal = df_in_herd.pipe(analyze_group)
                    subtotal = pd.DataFrame(subtotal).T.reset_index(drop=True)
                    subtotal['birth_year_group'] = '合计'
                    subtotal['是否在场'] = in_herd
                    results.append(subtotal)
                    
                    # 添加空行
                    results.append(empty_row)
            
            # 合并所有结果
            final_result = pd.concat(results, ignore_index=True)
            
            # 重新排序列
            final_result = final_result[['是否在场', 'birth_year_group', '头数'] + selected_traits]
            
            # 保存结果
            output_file = self.output_folder / "结果-牛群关键性状年度变化.xlsx"
            final_result.to_excel(output_file, index=False)
            logger.info(f"关键性状年度变化表已保存至: {output_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"生成关键性状年度变化表失败: {str(e)}")
            return False
    
    def generate_nm_distribution_charts(self, merged_cow_key_traits_scores: pd.DataFrame) -> bool:
        """
        生成NM$分布图表
        
        Args:
            merged_cow_key_traits_scores: 合并的母牛关键性状数据
            
        Returns:
            是否成功生成
        """
        try:
            # 数据处理
            df = merged_cow_key_traits_scores.copy()
            
            # 添加"是否在场"限制条件
            if '是否在场' in df.columns:
                df = df[df['是否在场'] != '否']
            
            if 'NM$' not in df.columns:
                raise ValueError("NM$ column not found in the dataframe")
            
            df['NM$'] = pd.to_numeric(df['NM$'], errors='coerce')
            
            # 动态确定区间
            min_value = df['NM$'].min()
            max_value = df['NM$'].max()
            
            # 根据数据范围确定步长
            range_value = max_value - min_value
            step = 300  # 默认步长
            
            if range_value > 3000:
                step = 500
            elif range_value <= 1500:
                step = 200
            
            # 创建区间
            lower_bound = np.floor(min_value / step) * step
            upper_bound = np.ceil(max_value / step) * step
            bins = np.arange(lower_bound, upper_bound + step, step)
            
            # 创建标签
            labels = [f'{bins[i]:.0f}-{bins[i+1]:.0f}' for i in range(len(bins)-1)]
            
            df['NM$_group'] = pd.cut(df['NM$'], bins=bins, labels=labels, include_lowest=True)
            nm_distribution = df['NM$_group'].value_counts().sort_index()
            
            nm_percentages = nm_distribution / len(df)
            
            # 创建DataFrame保存结果
            result_df = pd.DataFrame({
                'NM$区间': nm_distribution.index,
                '头数': nm_distribution.values,
                '占比': nm_percentages.values
            })
            
            # 保存到Excel
            output_file = self.output_folder / "在群牛只净利润值分布.xlsx"
            with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
                result_df.to_excel(writer, sheet_name='NM$分布', index=False)
                
                # 获取工作簿和工作表
                workbook = writer.book
                worksheet = writer.sheets['NM$分布']
                
                # 格式化占比列为百分比
                percent_format = workbook.add_format({'num_format': '0.00%'})
                worksheet.set_column('C:C', 12, percent_format)
            
            logger.info(f"NM$分布表已保存至: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"生成NM$分布图表失败: {str(e)}")
            return False
    
    def generate_quintile_distribution(self, df: pd.DataFrame, value_column: str, 
                                     file_prefix: str) -> bool:
        """
        生成五等份分布表
        
        Args:
            df: 数据框
            value_column: 要分析的值列
            file_prefix: 文件前缀
            
        Returns:
            是否成功生成
        """
        try:
            import xlsxwriter
            
            excel_file = self.output_folder / f"{file_prefix}_5等份分布表.xlsx"
            
            workbook = xlsxwriter.Workbook(str(excel_file), {'nan_inf_to_errors': True})
            worksheet = workbook.add_worksheet("5等份分布")
            
            # 定义格式
            title_fmt = workbook.add_format({'bold': True, 'font_size': 14})
            header_fmt = workbook.add_format({'bold': True, 'border': 1, 'align': 'center'})
            border_fmt = workbook.add_format({'border': 1})
            number_fmt = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
            
            worksheet.write('A1', f"{value_column}5等份分布", title_fmt)
            
            current_row = 2
            
            for cattle_type in ['成母牛', '后备牛']:
                if cattle_type == '成母牛':
                    if 'lac' in df.columns:
                        data = df[(df['lac'] >= 1)]
                    else:
                        continue
                else:
                    if 'lac' in df.columns:
                        data = df[((df['lac'] == 0) | (df['lac'].isna()))]
                    else:
                        continue
                
                # 过滤条件
                if '是否在场' in data.columns:
                    data = data[data['是否在场'] != '否']
                if 'sex' in data.columns:
                    data = data[data['sex'] != '公']
                
                if value_column in data.columns:
                    data = data[value_column]
                else:
                    continue
                
                # 将数据转换为数值类型
                data = pd.to_numeric(data, errors='coerce')
                
                # 处理 NaN/INF 值
                data = data.replace([np.inf, -np.inf], np.nan)
                data = data.dropna()
                
                if data.empty:
                    logger.warning(f"没有{cattle_type}的数据，跳过生成分布表。")
                    continue
                
                quintiles = np.percentile(data, [20, 40, 60, 80])
                
                # 计算每个区间的头数和统计值
                intervals = [
                    (float('-inf'), quintiles[0]),
                    (quintiles[0], quintiles[1]),
                    (quintiles[1], quintiles[2]),
                    (quintiles[2], quintiles[3]),
                    (quintiles[3], float('inf'))
                ]
                
                stats = []
                for start, end in intervals:
                    if start == float('-inf'):
                        mask = (data <= end)
                    elif end == float('inf'):
                        mask = (data > start)
                    else:
                        mask = (data > start) & (data <= end)
                    
                    interval_data = data[mask]
                    stats.append({
                        'count': len(interval_data),
                        'average': interval_data.mean() if not interval_data.empty else 0,
                        'min': interval_data.min() if not interval_data.empty else 0,
                        'max': interval_data.max() if not interval_data.empty else 0
                    })
                
                # 写入小标题
                worksheet.write(current_row, 0, f"{cattle_type}分布", title_fmt)
                current_row += 1
                
                # 写入表头
                headers = ['指数分布', '头数', 'AVERAGE', 'MIN', 'MAX']
                for col, header in enumerate(headers):
                    worksheet.write(current_row, col, header, header_fmt)
                current_row += 1
                
                # 写入数据
                distribution_labels = ['最差20%', '20%', '20%', '20%', '最优20%']
                for row, (label, stat) in enumerate(zip(distribution_labels, stats)):
                    worksheet.write(current_row + row, 0, label, border_fmt)
                    worksheet.write(current_row + row, 1, stat['count'], border_fmt)
                    
                    for col, key in enumerate(['average', 'min', 'max'], start=2):
                        value = stat[key]
                        if pd.isna(value) or value in [np.inf, -np.inf]:
                            value = 0
                        worksheet.write(current_row + row, col, value, number_fmt)
                
                current_row += len(distribution_labels) + 2  # 添加空行
            
            # 调整列宽
            worksheet.set_column('A:E', 15)
            
            workbook.close()
            
            logger.info(f"{value_column}5等份分布表已保存: {excel_file}")
            return True
            
        except Exception as e:
            logger.error(f"生成五等份分布表失败: {str(e)}")
            return False
    
    def generate_normal_distribution_charts(self, df: pd.DataFrame, value_column: str, 
                                          file_prefix: str) -> bool:
        """
        生成正态分布图
        
        Args:
            df: 数据框
            value_column: 要分析的值列
            file_prefix: 文件前缀
            
        Returns:
            是否成功生成
        """
        try:
            import matplotlib.pyplot as plt
            from scipy import stats
            import matplotlib.font_manager as fm
            
            # 设置中文字体
            import platform
            if platform.system() == 'Darwin':  # macOS
                plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'STHeiti']
            elif platform.system() == 'Windows':
                plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
            else:  # Linux
                plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False  # 正确显示负号
            
            # 过滤在场的牛只
            if '是否在场' in df.columns:
                df_in_herd = df[df['是否在场'] == '是']
            else:
                df_in_herd = df
                
            if df_in_herd.empty:
                logger.warning("没有在场的牛只数据，无法生成分布图")
                return False
                
            # 生成年份分布
            success = self.generate_year_distribution(df_in_herd, value_column, file_prefix)
            
            return success
            
        except Exception as e:
            logger.error(f"生成正态分布图失败: {str(e)}")
            return False
    
    def generate_year_distribution(self, df: pd.DataFrame, value_column: str, 
                                 file_prefix: str) -> bool:
        """
        生成年份正态分布图
        
        Args:
            df: 数据框
            value_column: 要分析的值列
            file_prefix: 文件前缀
            
        Returns:
            是否成功生成
        """
        try:
            import matplotlib.pyplot as plt
            from scipy import stats
            
            # 确保birth_date是日期类型
            df['birth_date'] = pd.to_datetime(df['birth_date'])
            
            max_birth_year = df['birth_date'].dt.year.max()
            df['group'] = pd.cut(
                df['birth_date'].dt.year,
                bins=[-float('inf')] + list(range(max_birth_year-4, max_birth_year+1)),
                labels=[f'{max_birth_year-4}年及以前'] + [f'{year}年' for year in range(max_birth_year-3, max_birth_year+1)]
            )
            
            plt.figure(figsize=(12, 8))
            
            cmap = plt.cm.get_cmap('Set1')
            unique_groups = df['group'].unique()
            colors = cmap(np.linspace(0, 1, len(unique_groups)))
            
            legend_text = []
            
            for i, (group, group_data) in enumerate(df.groupby('group', observed=True)):
                group_values = group_data[value_column].dropna()
                
                if len(group_values) > 0:
                    mean = np.mean(group_values)
                    std = np.std(group_values)
                    
                    x = np.linspace(mean - 3*std, mean + 3*std, 100)
                    y = stats.norm.pdf(x, mean, std)
                    
                    plt.plot(x, y, color=colors[i], linestyle=['-', '--'][i % 2], label=group)
                    
                    legend_text.append(f"{group}\n均值: {mean:.1f}\n标准差: {std:.2f}\nN: {len(group_values)}")
            
            plt.title(f'{value_column}值年份分布', fontsize=16)
            plt.xlabel(f'{value_column}值', fontsize=12)
            plt.ylabel('密度', fontsize=12)
            plt.grid(True, linestyle='--', alpha=0.7)
            
            plt.legend(legend_text, loc='upper right', bbox_to_anchor=(1.25, 1), fontsize=10)
            
            plt.tight_layout()
            
            output_file = self.output_folder / f"{file_prefix}_年份正态分布.png"
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 保存数据到Excel
            excel_file = self.output_folder / f"{file_prefix}_年份正态分布数据.xlsx"
            with pd.ExcelWriter(excel_file, engine='xlsxwriter') as writer:
                for group, group_data in df.groupby('group', observed=True):
                    sheet_name = str(group)[:31]  # Excel工作表名称限制
                    group_data.to_excel(writer, sheet_name=sheet_name, index=False)
            
            logger.info(f"年份正态分布图已保存: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"生成年份分布图失败: {str(e)}")
            return False
    
    def generate_traits_progress_charts(self, df: pd.DataFrame, selected_traits: List[str]) -> bool:
        """
        生成性状进展图
        
        Args:
            df: 母牛关键性状数据
            selected_traits: 选中的性状列表
            
        Returns:
            是否成功生成
        """
        try:
            import matplotlib.pyplot as plt
            
            # 创建输出文件夹
            progress_folder = self.output_folder / "结果-牛群关键性状进展图"
            progress_folder.mkdir(exist_ok=True)
            
            # 设置中文字体
            import platform
            if platform.system() == 'Darwin':  # macOS
                plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'STHeiti']
            elif platform.system() == 'Windows':
                plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
            else:  # Linux
                plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
            
            # 过滤在场的牛只
            if '是否在场' in df.columns:
                df = df[df['是否在场'] == '是']
                
            # 确保birth_date是日期类型
            df['birth_date'] = pd.to_datetime(df['birth_date'])
            df['birth_year'] = df['birth_date'].dt.year
            
            # 获取最大出生年份
            max_year = df['birth_year'].max()
            years = list(range(max_year-4, max_year+1))
            
            for trait in selected_traits:
                if trait not in df.columns:
                    logger.warning(f"性状 {trait} 不在数据中，跳过")
                    continue
                    
                plt.figure(figsize=(10, 6))
                
                # 计算每年的平均值
                yearly_means = []
                yearly_counts = []
                for year in years:
                    year_data = df[df['birth_year'] == year][trait].dropna()
                    if len(year_data) > 0:
                        yearly_means.append(year_data.mean())
                        yearly_counts.append(len(year_data))
                    else:
                        yearly_means.append(np.nan)
                        yearly_counts.append(0)
                
                # 绘制折线图
                valid_indices = [i for i, val in enumerate(yearly_means) if not np.isnan(val)]
                valid_years = [years[i] for i in valid_indices]
                valid_means = [yearly_means[i] for i in valid_indices]
                
                plt.plot(valid_years, valid_means, marker='o', markersize=8, linewidth=2)
                
                # 添加数据标签
                for i, (year, mean, count) in enumerate(zip(valid_years, valid_means, 
                                                           [yearly_counts[j] for j in valid_indices])):
                    plt.text(year, mean, f'{mean:.1f}\nn={count}', ha='center', va='bottom')
                
                plt.title(f'{trait}进展情况', fontsize=16)
                plt.xlabel('出生年份', fontsize=12)
                plt.ylabel(f'{trait}平均值', fontsize=12)
                plt.grid(True, linestyle='--', alpha=0.7)
                plt.xticks(years)
                
                # 添加趋势线
                if len(valid_years) > 1:
                    z = np.polyfit(valid_years, valid_means, 1)
                    p = np.poly1d(z)
                    plt.plot(valid_years, p(valid_years), "r--", alpha=0.8, 
                            label=f'趋势线: y={z[0]:.2f}x+{z[1]:.2f}')
                    plt.legend()
                
                plt.tight_layout()
                
                output_file = progress_folder / f"{trait}进展情况.png"
                plt.savefig(output_file, dpi=300, bbox_inches='tight')
                plt.close()
                
                logger.info(f"{trait}进展图已保存: {output_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"生成性状进展图失败: {str(e)}")
            return False
    
    def generate_semen_usage_trend(self, breeding_df: pd.DataFrame, 
                                  bull_traits: pd.DataFrame, 
                                  selected_traits: List[str]) -> bool:
        """
        生成冻精使用趋势图数据
        
        Args:
            breeding_df: 配种记录数据
            bull_traits: 公牛性状数据
            selected_traits: 选中的性状列表
            
        Returns:
            是否成功生成
        """
        try:
            # 合并配种记录和公牛性状
            if 'BULL NAAB' not in breeding_df.columns:
                logger.error("配种记录中缺少BULL NAAB列")
                return False
                
            merged_df = pd.merge(
                breeding_df, 
                bull_traits, 
                left_on='BULL NAAB', 
                right_on='NAAB', 
                how='left'
            )
            
            # 按年份和冻精类型汇总
            if '配种日期' in merged_df.columns:
                merged_df['配种日期'] = pd.to_datetime(merged_df['配种日期'])
                merged_df['年份'] = merged_df['配种日期'].dt.year
                
            # 创建结果数据框
            result_data = []
            
            # 计算每年每个冻精类型的平均值
            yearly_summary = merged_df.groupby(['年份', '冻精类型']).agg({
                **{trait: 'mean' for trait in selected_traits if trait in merged_df.columns},
                'BULL NAAB': 'count'  # 使用次数
            }).rename(columns={'BULL NAAB': '使用次数'}).reset_index()
            
            # 计算总体年度平均值
            yearly_total = merged_df.groupby('年份').agg({
                **{trait: 'mean' for trait in selected_traits if trait in merged_df.columns},
                'BULL NAAB': 'count'
            }).rename(columns={'BULL NAAB': '使用次数'}).reset_index()
            yearly_total['冻精类型'] = '总体均值'
            
            # 合并数据
            final_result = pd.concat([yearly_summary, yearly_total], ignore_index=True)
            
            # 保存结果
            output_file = self.output_folder / "结果-冻精使用趋势图.xlsx"
            with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
                # 为每个性状创建一个工作表
                for trait in selected_traits:
                    if trait in final_result.columns:
                        pivot_data = final_result.pivot(
                            index='年份', 
                            columns='冻精类型', 
                            values=trait
                        )
                        pivot_data.to_excel(writer, sheet_name=trait[:31])
                        
                # 保存汇总数据
                final_result.to_excel(writer, sheet_name='汇总', index=False)
                
            logger.info(f"冻精使用趋势图数据已保存: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"生成冻精使用趋势图数据失败: {str(e)}")
            return False
    
    def generate_index_ranking(self, cow_df: pd.DataFrame, 
                             breeding_index_scores: pd.DataFrame,
                             selected_traits: List[str]) -> bool:
        """
        生成指数排名结果
        
        Args:
            cow_df: 母牛基本信息
            breeding_index_scores: 育种指数得分
            selected_traits: 选中的性状列表
            
        Returns:
            是否成功生成
        """
        try:
            # 合并数据
            if 'cow_id' not in cow_df.columns or 'cow_id' not in breeding_index_scores.columns:
                logger.error("缺少cow_id列，无法合并数据")
                return False
                
            merged_df = pd.merge(
                cow_df, 
                breeding_index_scores, 
                on='cow_id', 
                how='inner'
            )
            
            # 筛选在场的牛只
            if '是否在场' in merged_df.columns:
                merged_df = merged_df[merged_df['是否在场'] == '是']
                
            # 按育种指数得分排名
            if '育种指数得分' in merged_df.columns:
                merged_df = merged_df.sort_values('育种指数得分', ascending=False)
                merged_df['排名'] = range(1, len(merged_df) + 1)
            else:
                logger.error("缺少育种指数得分列")
                return False
                
            # 选择输出列
            output_columns = ['cow_id', '排名', '育种指数得分']
            if 'birth_date' in merged_df.columns:
                output_columns.append('birth_date')
            if 'lac' in merged_df.columns:
                output_columns.append('lac')
                
            # 添加选中的性状
            for trait in selected_traits:
                if trait in merged_df.columns:
                    output_columns.append(trait)
                    
            result_df = merged_df[output_columns]
            
            # 保存结果
            output_file = self.output_folder / "结果-指数排名结果.xlsx"
            result_df.to_excel(output_file, index=False)
            
            logger.info(f"指数排名结果已保存: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"生成指数排名结果失败: {str(e)}")
            return False
    
    def generate_cow_key_traits(self, cow_df: pd.DataFrame, 
                              cow_traits: pd.DataFrame,
                              selected_traits: List[str]) -> bool:
        """
        生成母牛关键性状指数
        
        Args:
            cow_df: 母牛基本信息
            cow_traits: 母牛性状数据
            selected_traits: 选中的性状列表
            
        Returns:
            是否成功生成
        """
        try:
            # 合并数据
            if 'cow_id' not in cow_df.columns or 'ID' not in cow_traits.columns:
                logger.error("缺少ID列，无法合并数据")
                return False
                
            merged_df = pd.merge(
                cow_df, 
                cow_traits, 
                left_on='cow_id', 
                right_on='ID', 
                how='inner'
            )
            
            # 筛选在场的牛只
            if '是否在场' in merged_df.columns:
                merged_df = merged_df[merged_df['是否在场'] == '是']
                
            # 选择输出列
            output_columns = ['cow_id']
            if 'birth_date' in merged_df.columns:
                output_columns.append('birth_date')
            if 'lac' in merged_df.columns:
                output_columns.append('lac')
            if '是否在场' in merged_df.columns:
                output_columns.append('是否在场')
                
            # 添加选中的性状
            for trait in selected_traits:
                if trait in merged_df.columns:
                    output_columns.append(trait)
                    
            result_df = merged_df[output_columns]
            
            # 保存结果
            output_file = self.output_folder / "结果-母牛关键性状指数.xlsx"
            result_df.to_excel(output_file, index=False)
            
            logger.info(f"母牛关键性状指数已保存: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"生成母牛关键性状指数失败: {str(e)}")
            return False