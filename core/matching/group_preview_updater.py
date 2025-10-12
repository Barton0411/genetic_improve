"""
分组预览更新器
用于在分组预览中显示每个公牛的剩余支数
"""

import pandas as pd
import logging
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)

class GroupPreviewUpdater:
    """分组预览更新器"""
    
    def __init__(self, allocation_result_df: pd.DataFrame, bull_data_df: pd.DataFrame):
        """
        初始化
        
        Args:
            allocation_result_df: 分配结果DataFrame
            bull_data_df: 公牛数据DataFrame（包含原始支数）
        """
        self.allocation_result = allocation_result_df
        self.bull_data = bull_data_df
        self._calculate_remaining_counts()
        
    def _calculate_remaining_counts(self):
        """计算每个公牛的剩余支数"""
        # 统计每个公牛的使用次数
        bull_usage = {}
        
        for _, row in self.allocation_result.iterrows():
            for col in row.index:
                if '选' in col and ('常规' in col or '性控' in col) and not col.endswith('_剩余支数'):
                    bull_id = row[col]
                    if pd.notna(bull_id) and bull_id != '':
                        bull_usage[bull_id] = bull_usage.get(bull_id, 0) + 1
                        
        # 计算剩余支数
        self.bull_remaining = {}
        for _, bull in self.bull_data.iterrows():
            bull_id = str(bull['bull_id'])
            total_count = bull.get('semen_count', 0)
            used_count = bull_usage.get(bull_id, 0)
            self.bull_remaining[bull_id] = max(0, total_count - used_count)
            
    def update_group_preview_table(self, table_widget: QTableWidget, group_name: str):
        """
        更新分组预览表格
        
        Args:
            table_widget: QTableWidget对象
            group_name: 分组名称
        """
        try:
            # 获取该分组的数据
            group_data = self.allocation_result[
                self.allocation_result['group'] == group_name
            ]
            
            if group_data.empty:
                return
                
            # 清空表格
            table_widget.setRowCount(0)
            
            # 设置列头
            headers = ['母牛号', '指数得分']
            
            # 添加选配结果列头
            for i in range(1, 4):
                for semen_type in ['性控', '常规']:
                    headers.append(f"{i}选{semen_type}")
                    
            table_widget.setColumnCount(len(headers))
            table_widget.setHorizontalHeaderLabels(headers)
            
            # 填充数据
            for _, cow in group_data.iterrows():
                row_position = table_widget.rowCount()
                table_widget.insertRow(row_position)
                
                # 母牛号
                table_widget.setItem(
                    row_position, 0, 
                    QTableWidgetItem(str(cow['cow_id']))
                )
                
                # 指数得分
                score = cow.get('Combine Index Score', 0)
                table_widget.setItem(
                    row_position, 1,
                    QTableWidgetItem(f"{score:.2f}")
                )
                
                # 选配结果
                col_index = 2
                for i in range(1, 4):
                    for semen_type in ['性控', '常规']:
                        col_name = f"{i}选{semen_type}"
                        bull_id = cow.get(col_name, '')
                        
                        if pd.notna(bull_id) and bull_id != '':
                            # 显示公牛ID和剩余支数
                            remaining = self.bull_remaining.get(bull_id, 0)
                            display_text = f"{bull_id} (剩{remaining}支)"
                        else:
                            display_text = ""
                            
                        table_widget.setItem(
                            row_position, col_index,
                            QTableWidgetItem(display_text)
                        )
                        col_index += 1
                        
            # 调整列宽
            table_widget.resizeColumnsToContents()
            
        except Exception as e:
            logger.error(f"更新分组预览失败: {e}")
            
    def get_group_summary(self, group_name: str) -> dict:
        """
        获取分组的汇总信息
        
        Args:
            group_name: 分组名称
            
        Returns:
            包含汇总信息的字典
        """
        group_data = self.allocation_result[
            self.allocation_result['group'] == group_name
        ]
        
        if group_data.empty:
            return {}
            
        # 统计该组使用的公牛
        group_bull_usage = {}
        
        for _, row in group_data.iterrows():
            for col in row.index:
                if '选' in col and ('常规' in col or '性控' in col) and not col.endswith('_剩余支数'):
                    bull_id = row[col]
                    if pd.notna(bull_id) and bull_id != '':
                        group_bull_usage[bull_id] = group_bull_usage.get(bull_id, 0) + 1
                        
        # 生成汇总
        summary = {
            '母牛数量': len(group_data),
            '平均指数': group_data['Combine Index Score'].mean(),
            '使用公牛数': len(group_bull_usage),
            '公牛使用情况': []
        }
        
        # 添加每个公牛的使用情况
        for bull_id, usage_count in sorted(group_bull_usage.items(), 
                                          key=lambda x: x[1], 
                                          reverse=True):
            bull_info = self.bull_data[self.bull_data['bull_id'] == bull_id]
            if not bull_info.empty:
                semen_type = bull_info.iloc[0].get('semen_type', '')
                total_count = bull_info.iloc[0].get('semen_count', 0)
                remaining = self.bull_remaining.get(bull_id, 0)
                
                summary['公牛使用情况'].append({
                    '公牛ID': bull_id,
                    '类型': semen_type,
                    '使用次数': usage_count,
                    '总支数': total_count,
                    '剩余支数': remaining
                })
                
        return summary
        
    def export_group_preview(self, group_name: str, output_path: str):
        """
        导出分组预览到Excel
        
        Args:
            group_name: 分组名称
            output_path: 输出文件路径
        """
        try:
            group_data = self.allocation_result[
                self.allocation_result['group'] == group_name
            ].copy()
            
            if group_data.empty:
                logger.warning(f"分组 {group_name} 没有数据")
                return False
                
            # 添加剩余支数信息到每个选配结果
            for col in group_data.columns:
                if '选' in col and ('常规' in col or '性控' in col) and not col.endswith('_剩余支数'):
                    group_data[f"{col}_剩余支数"] = group_data[col].map(
                        lambda x: self.bull_remaining.get(x, 0) if pd.notna(x) and x != '' else ''
                    )
                    
            # 保存到Excel
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # 保存详细数据
                group_data.to_excel(writer, sheet_name='选配详情', index=False)
                
                # 保存汇总信息
                summary = self.get_group_summary(group_name)
                if summary and '公牛使用情况' in summary:
                    bull_usage_df = pd.DataFrame(summary['公牛使用情况'])
                    bull_usage_df.to_excel(writer, sheet_name='公牛使用汇总', index=False)
                    
                # 保存基本信息
                info_df = pd.DataFrame([{
                    '分组名称': group_name,
                    '母牛数量': summary.get('母牛数量', 0),
                    '平均指数': f"{summary.get('平均指数', 0):.2f}",
                    '使用公牛数': summary.get('使用公牛数', 0)
                }])
                info_df.to_excel(writer, sheet_name='分组信息', index=False)
                
            logger.info(f"分组预览已导出到: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出分组预览失败: {e}")
            return False