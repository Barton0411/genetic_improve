"""
PPT生成模块
"""

import os
import logging
from pathlib import Path
from typing import Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

# 设置日志
logger = logging.getLogger(__name__)

class PPTGenerator:
    """PPT报告生成器"""
    
    def __init__(self, project_path: Path, farm_name: str = "牧场"):
        """
        初始化PPT生成器
        
        Args:
            project_path: 项目路径
            farm_name: 牧场名称
        """
        self.project_path = Path(project_path)
        self.farm_name = farm_name
        self.output_folder = self.project_path / "analysis_results"
        self.output_folder.mkdir(parents=True, exist_ok=True)
        
        # 获取模板路径（使用程序内置的模板）
        self.template_path = Path(__file__).parent.parent.parent / "PPT模版.pptx"
        
    def check_required_files(self) -> Tuple[bool, str]:
        """
        检查生成PPT所需的文件是否存在
        
        Returns:
            Tuple[bool, str]: (是否满足条件, 错误信息)
        """
        # 系谱分析是可自动生成的，所以单独检查
        optional_files = {
            "系谱识别情况分析": self.output_folder / "结果-系谱识别情况分析.xlsx",
        }
        
        # 必须的文件（需要用户手动执行分析）
        required_files = {
            "母牛关键性状指数": self.output_folder / "processed_cow_data_key_traits_scores_genomic.xlsx",
            "母牛育种指数": self.output_folder / "processed_index_cow_index_scores.xlsx",
        }
        
        missing_files = []
        
        # 检查可选文件
        for name, file_path in optional_files.items():
            if not file_path.exists():
                # 检查是否有母牛数据（可以自动生成系谱分析）
                cow_data_file = self.project_path / "standardized_data" / "processed_cow_data.xlsx"
                if not cow_data_file.exists():
                    missing_files.append(name + "（需要先上传母牛数据）")
                else:
                    missing_files.append(name)
        
        # 检查必须文件
        for name, file_path in required_files.items():
            if not file_path.exists():
                missing_files.append(name)
                
        if missing_files:
            return False, f"缺少以下必要文件：{', '.join(missing_files)}"
            
        return True, ""
    
    def generate_ppt(self, progress_callback=None) -> bool:
        """
        生成PPT报告
        
        Args:
            progress_callback: 进度回调函数
            
        Returns:
            bool: 是否成功生成
        """
        try:
            # 创建演示文稿
            if self.template_path.exists():
                # 使用模板创建
                prs = Presentation(str(self.template_path))
                # 删除模板中的所有现有幻灯片
                for i in range(len(prs.slides) - 1, -1, -1):
                    rId = prs.slides._sldIdLst[i].rId
                    prs.part.drop_rel(rId)
                    del prs.slides._sldIdLst[i]
                logger.info("使用PPT模板创建演示文稿")
            else:
                # 创建空白演示文稿
                prs = Presentation()
                # 设置幻灯片大小为16:9
                prs.slide_width = Inches(16)
                prs.slide_height = Inches(9)
                logger.info("创建空白演示文稿")
                
            if progress_callback:
                progress_callback("正在生成标题页...", 10)
                
            # 生成各个页面
            self._create_title_slide(prs)
            
            if progress_callback:
                progress_callback("正在生成目录页...", 20)
            self._create_toc_slide(prs)
            
            if progress_callback:
                progress_callback("正在生成系谱分析页...", 30)
            self._create_pedigree_analysis_slide(prs)
            
            if progress_callback:
                progress_callback("正在生成系谱完整性分析页...", 40)
            self._create_pedigree_completeness_slide(prs)
            
            if progress_callback:
                progress_callback("正在生成关键性状分析页...", 50)
            self._create_key_traits_analysis_slide(prs)
            
            if progress_callback:
                progress_callback("正在生成育种指数分布页...", 60)
            self._create_breeding_index_distribution_slide(prs)
            
            if progress_callback:
                progress_callback("正在生成选配推荐汇总页...", 70)
            self._create_mating_recommendation_slide(prs)
            
            if progress_callback:
                progress_callback("正在生成结束页...", 80)
            self._create_bye_slide(prs)
            
            # 保存PPT
            output_path = self.output_folder / f"{self.farm_name}牧场遗传改良项目专项服务报告.pptx"
            prs.save(str(output_path))
            
            if progress_callback:
                progress_callback("PPT报告生成完成！", 100)
                
            logger.info(f"PPT报告已保存至: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"生成PPT报告时发生错误: {str(e)}")
            raise
            
    def _create_title_slide(self, prs):
        """创建标题页"""
        slide_layout = prs.slide_layouts[0] if len(prs.slide_layouts) > 0 else prs.slide_layouts[5]
        slide = prs.slides.add_slide(slide_layout)
        
        # 添加标题
        title = f"{self.farm_name}牧场遗传改良项目专项服务"
        left = Inches(2)
        top = Inches(4.5)
        width = Inches(12)
        height = Inches(1.5)
        title_shape = slide.shapes.add_textbox(left, top, width, height)
        
        title_frame = title_shape.text_frame
        title_frame.text = title
        title_para = title_frame.paragraphs[0]
        title_para.alignment = PP_ALIGN.CENTER
        font = title_para.font
        font.name = "微软雅黑"
        font.size = Pt(48)
        font.bold = True
        font.color.rgb = RGBColor(0, 0, 0)
        
        # 添加日期
        date_str = datetime.now().strftime("%Y年%m月")
        date_left = Inches(2)
        date_top = Inches(6.5)
        date_width = Inches(12)
        date_height = Inches(0.5)
        date_shape = slide.shapes.add_textbox(date_left, date_top, date_width, date_height)
        
        date_frame = date_shape.text_frame
        date_frame.text = date_str
        date_para = date_frame.paragraphs[0]
        date_para.alignment = PP_ALIGN.CENTER
        date_font = date_para.font
        date_font.name = "微软雅黑"
        date_font.size = Pt(24)
        date_font.color.rgb = RGBColor(89, 89, 89)
        
    def _create_toc_slide(self, prs):
        """创建目录页"""
        slide_layout = prs.slide_layouts[5]  # 使用空白布局
        slide = prs.slides.add_slide(slide_layout)
        
        # 添加标题
        title = "目录"
        left, top, width, height = Inches(0.5), Inches(0.5), Inches(15), Inches(1)
        title_shape = slide.shapes.add_textbox(left, top, width, height)
        title_frame = title_shape.text_frame
        title_frame.text = title
        title_para = title_frame.paragraphs[0]
        title_para.alignment = PP_ALIGN.CENTER
        title_para.font.name = "微软雅黑"
        title_para.font.size = Pt(44)
        title_para.font.bold = True
        
        # 定义目录项
        toc_items = [
            ("01", "牧场系谱记录分析", "系谱完整性 系谱准确性"),
            ("02", "牛群遗传数据评估", "关键性状 育种指数 分布分析"),
            ("03", "选配推荐方案", "个体选配 近交控制 隐性基因"),
            ("04", "项目总结与建议", "改良建议 后续计划")
        ]
        
        # 创建网格布局
        columns = 2
        spacing = Inches(0.5)
        cell_width = Inches(6.5)
        cell_height = Inches(2.5)
        
        total_grid_width = columns * cell_width + (columns - 1) * spacing
        slide_width = prs.slide_width
        grid_left = (slide_width - total_grid_width) / 2
        
        rows = (len(toc_items) + columns - 1) // columns
        total_grid_height = rows * cell_height + (rows - 1) * spacing
        slide_height = prs.slide_height
        grid_top = (slide_height - total_grid_height) / 2 + Inches(0.5)
        
        for i, (number, title, subtitle) in enumerate(toc_items):
            left = grid_left + (i % columns) * (cell_width + spacing)
            top = grid_top + (i // columns) * (cell_height + spacing)
            
            # 添加编号
            number_box = slide.shapes.add_textbox(left, top, Inches(0.5), Inches(0.5))
            number_frame = number_box.text_frame
            number_frame.text = number
            number_frame.paragraphs[0].font.name = "微软雅黑"
            number_frame.paragraphs[0].font.size = Pt(24)
            number_frame.paragraphs[0].font.color.rgb = RGBColor(0, 176, 240)
            
            # 添加主标题
            title_box = slide.shapes.add_textbox(left, top + Inches(0.5), cell_width, Inches(0.4))
            title_frame = title_box.text_frame
            title_frame.text = title
            title_frame.paragraphs[0].font.name = "微软雅黑"
            title_frame.paragraphs[0].font.size = Pt(18)
            title_frame.paragraphs[0].font.bold = True
            
            # 添加副标题
            subtitle_box = slide.shapes.add_textbox(left, top + Inches(0.9), cell_width, Inches(1))
            subtitle_frame = subtitle_box.text_frame
            subtitle_frame.clear()
            
            subtitle_items = subtitle.split()
            for item in subtitle_items:
                p = subtitle_frame.add_paragraph()
                p.text = "• " + item
                p.font.name = "微软雅黑"
                p.font.size = Pt(14)
                p.font.color.rgb = RGBColor(89, 89, 89)
                p.level = 1
                
    def _create_pedigree_analysis_slide(self, prs):
        """创建系谱分析标题页"""
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)
        
        # 添加序号
        number_box = slide.shapes.add_textbox(Inches(5.67), Inches(1.12), Inches(2), Inches(2))
        number_frame = number_box.text_frame
        number_frame.text = "01"
        number_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        font = number_frame.paragraphs[0].font
        font.name = "Arial"
        font.size = Pt(166)
        font.color.rgb = RGBColor(255, 255, 255)
        font.color.transparency = 0.69
        
        # 添加标题
        title_box = slide.shapes.add_textbox(Inches(2.67), Inches(4.13), Inches(8), Inches(2))
        title_frame = title_box.text_frame
        title_frame.text = "牧场系谱记录分析"
        title_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        font = title_frame.paragraphs[0].font
        font.name = "微软雅黑"
        font.size = Pt(40)
        font.color.rgb = RGBColor(255, 255, 255)
        
    def _create_pedigree_completeness_slide(self, prs):
        """创建系谱完整性分析页"""
        slide_layout = prs.slide_layouts[5]
        slide = prs.slides.add_slide(slide_layout)
        
        # 添加标题
        title = f"1.1 {self.farm_name}牧场系谱完整性分析"
        left, top, width, height = Inches(0.583), Inches(0.732), Inches(10), Inches(0.571)
        title_shape = slide.shapes.add_textbox(left, top, width, height)
        title_frame = title_shape.text_frame
        title_frame.text = title
        title_para = title_frame.paragraphs[0]
        title_para.alignment = PP_ALIGN.LEFT
        title_para.font.name = "微软雅黑"
        title_para.font.size = Pt(28)
        title_para.font.bold = True
        
        # 尝试加载数据并创建表格
        try:
            analysis_file = self.output_folder / "结果-系谱识别情况分析.xlsx"
            if analysis_file.exists():
                df = pd.read_excel(analysis_file)
                df = df[df['是否在场'] == '是'].head(6)  # 只显示在场的前6行
                
                # 创建表格
                table_rows, table_cols = min(len(df) + 1, 7), 9
                left, top, width, height = Inches(0.874), Inches(1.72), Inches(14.5), Inches(5)
                table = slide.shapes.add_table(table_rows, table_cols, left, top, width, height).table
                
                # 设置表头
                headers = ['是否在场', '出生年份', '头数', '父号可识别头数', '父号识别率', 
                          '外祖父可识别头数', '外祖父识别率', '外曾外祖父可识别头数', '外曾外祖父识别率']
                
                for i, header in enumerate(headers):
                    cell = table.cell(0, i)
                    cell.text = header
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = RGBColor(79, 129, 189)
                    para = cell.text_frame.paragraphs[0]
                    para.font.name = "微软雅黑"
                    para.font.size = Pt(14)
                    para.font.bold = True
                    para.font.color.rgb = RGBColor(255, 255, 255)
                    para.alignment = PP_ALIGN.CENTER
                    
                # 填充数据
                for row in range(1, min(table_rows, len(df) + 1)):
                    for col in range(table_cols):
                        cell = table.cell(row, col)
                        if col == 1:  # 出生年份列
                            value = str(df.iloc[row-1]['birth_year_group'])
                        else:
                            value = str(df.iloc[row-1, col])
                        cell.text = value
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = RGBColor(233, 237, 244)
                        para = cell.text_frame.paragraphs[0]
                        para.font.name = "微软雅黑"
                        para.font.size = Pt(12)
                        para.alignment = PP_ALIGN.CENTER
                        
        except Exception as e:
            logger.warning(f"创建系谱完整性表格时出错: {e}")
            
    def _create_key_traits_analysis_slide(self, prs):
        """创建关键性状分析页"""
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)
        
        # 添加序号
        number_box = slide.shapes.add_textbox(Inches(5.67), Inches(1.12), Inches(2), Inches(2))
        number_frame = number_box.text_frame
        number_frame.text = "02"
        number_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        font = number_frame.paragraphs[0].font
        font.name = "Arial"
        font.size = Pt(166)
        font.color.rgb = RGBColor(255, 255, 255)
        font.color.transparency = 0.69
        
        # 添加标题
        title_box = slide.shapes.add_textbox(Inches(2.67), Inches(4.13), Inches(8), Inches(2))
        title_frame = title_box.text_frame
        title_frame.text = "牛群遗传数据评估"
        title_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        font = title_frame.paragraphs[0].font
        font.name = "微软雅黑"
        font.size = Pt(40)
        font.color.rgb = RGBColor(255, 255, 255)
        
    def _create_breeding_index_distribution_slide(self, prs):
        """创建育种指数分布页"""
        slide_layout = prs.slide_layouts[5]
        slide = prs.slides.add_slide(slide_layout)
        
        # 添加标题
        title = f"2.1 {self.farm_name}牧场育种指数分布情况"
        left, top, width, height = Inches(0.583), Inches(0.732), Inches(10), Inches(0.571)
        title_shape = slide.shapes.add_textbox(left, top, width, height)
        title_frame = title_shape.text_frame
        title_frame.text = title
        title_para = title_frame.paragraphs[0]
        title_para.alignment = PP_ALIGN.LEFT
        title_para.font.name = "微软雅黑"
        title_para.font.size = Pt(28)
        title_para.font.bold = True
        
        # 添加说明文字
        info_text = "育种指数反映了母牛的综合遗传潜力，分布情况显示了牛群的整体遗传水平。"
        info_box = slide.shapes.add_textbox(Inches(1), Inches(1.5), Inches(14), Inches(0.5))
        info_frame = info_box.text_frame
        info_frame.text = info_text
        info_para = info_frame.paragraphs[0]
        info_para.font.name = "微软雅黑"
        info_para.font.size = Pt(16)
        info_para.font.color.rgb = RGBColor(89, 89, 89)
        
    def _create_mating_recommendation_slide(self, prs):
        """创建选配推荐汇总页"""
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)
        
        # 添加序号
        number_box = slide.shapes.add_textbox(Inches(5.67), Inches(1.12), Inches(2), Inches(2))
        number_frame = number_box.text_frame
        number_frame.text = "03"
        number_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        font = number_frame.paragraphs[0].font
        font.name = "Arial"
        font.size = Pt(166)
        font.color.rgb = RGBColor(255, 255, 255)
        font.color.transparency = 0.69
        
        # 添加标题
        title_box = slide.shapes.add_textbox(Inches(2.67), Inches(4.13), Inches(8), Inches(2))
        title_frame = title_box.text_frame
        title_frame.text = "选配推荐方案"
        title_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        font = title_frame.paragraphs[0].font
        font.name = "微软雅黑"
        font.size = Pt(40)
        font.color.rgb = RGBColor(255, 255, 255)
        
    def _create_bye_slide(self, prs):
        """创建结束页"""
        slide_layout = prs.slide_layouts[5]
        slide = prs.slides.add_slide(slide_layout)
        
        # 添加感谢文字
        thanks_text = "谢谢"
        left = Inches(2)
        top = Inches(3.5)
        width = Inches(12)
        height = Inches(2)
        thanks_shape = slide.shapes.add_textbox(left, top, width, height)
        
        thanks_frame = thanks_shape.text_frame
        thanks_frame.text = thanks_text
        thanks_para = thanks_frame.paragraphs[0]
        thanks_para.alignment = PP_ALIGN.CENTER
        font = thanks_para.font
        font.name = "微软雅黑"
        font.size = Pt(72)
        font.bold = True
        font.color.rgb = RGBColor(0, 0, 0) 