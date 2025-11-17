"""
PPT报告配置参数
"""

from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

# ==================== PPT布局配置（新模板 ppt模版-2.pptx）====================

# 幻灯片布局索引
LAYOUT_COVER = 0  # 封面
LAYOUT_SECTION = 1  # 间隔页
LAYOUT_CONTENT_1 = 2  # 正文页1
LAYOUT_CONTENT_2 = 3  # 正文页2
LAYOUT_TITLE_ONLY = 4  # 图片/标题页
LAYOUT_ONE_COLUMN_TEXT = 5  # 1_图片页（作为手工页面的空白底）
LAYOUT_BLANK = 5  # 模板无独立空白页，复用1_图片页
LAYOUT_TOC_4 = 1  # 模板使用间隔页绘制目录

# ==================== 3色配色方案（严格遵守3色原则）====================
# 来源：从旧模板背景图提取 + 专业文字配色
# 使用规范：仅使用以下3种颜色

# 【颜色1】蓝色 - 装饰线条（来自模板背景）
COLOR_DECORATION = RGBColor(0, 139, 206)  # 蓝色
# 使用场景：装饰线条、图表主色

# 【颜色1B】黄绿色 - 左侧色条
COLOR_BAR_GREEN = RGBColor(138, 184, 74)  # 黄绿色
# 使用场景：目录左侧色条

# 【颜色2】深灰 - 文字主色
COLOR_TEXT_MAIN = RGBColor(64, 64, 64)  # 深灰
# 使用场景：正文标题、重要文字、副标题

# 【颜色3】浅灰 - 辅助文字色
COLOR_TEXT_LIGHT = RGBColor(128, 128, 128)  # 浅灰
# 使用场景：描述文字、注释说明、日期时间、次要信息

# 【特殊元素】按钮蓝 - 封面汇报人按钮背景
COLOR_BUTTON_BG = RGBColor(50, 140, 207)  # 按钮蓝色
# 使用场景：封面页汇报人按钮背景

# 【特殊元素】编号背景 - 浅色半透明背景
COLOR_NUMBER_BG = RGBColor(174, 200, 223)  # 浅蓝灰色
# 使用场景：目录编号背景框

# 【特殊元素】目录背景 - 深蓝色椭圆
COLOR_TOC_BG = RGBColor(30, 130, 195)  # 深蓝色
# 使用场景：目录整体背景椭圆

# 【特殊元素】封面标题深蓝色
COLOR_COVER_TITLE = RGBColor(0, 51, 102)  # 深蓝色
# 使用场景：封面标题、副标题、日期

# 兼容性别名（保持代码兼容）
COLOR_PRIMARY = COLOR_DECORATION  # 主装饰色
COLOR_TEXT_TITLE = RGBColor(0, 0, 0)  # 标题黑色（封面专用）
COLOR_TEXT_BODY = COLOR_TEXT_MAIN  # 正文 -> 深灰
COLOR_TEXT_SECONDARY = COLOR_TEXT_LIGHT  # 副文本 -> 浅灰
COLOR_TEXT_COMMENT = COLOR_TEXT_LIGHT  # 评论 -> 浅灰

# 章节页副标题颜色（浅天蓝色，与目录页一致）
COLOR_SECTION_SUBTITLE = RGBColor(220, 235, 250)  # 浅蓝白色

# 图表专用颜色别名（映射到3色体系）
COLOR_SUCCESS = COLOR_DECORATION  # 成功/正向 -> 蓝色
COLOR_WARNING = COLOR_TEXT_LIGHT  # 警告 -> 浅灰
COLOR_DANGER = COLOR_TEXT_MAIN  # 危险 -> 深灰

# 表格配色（使用3色体系）
COLOR_TABLE_HEADER = COLOR_DECORATION  # 表头：蓝色
COLOR_TABLE_TEXT = COLOR_TEXT_MAIN  # 表格文字：深灰
COLOR_TABLE_ODD = RGBColor(255, 255, 255)  # 奇数行：白色背景
COLOR_TABLE_EVEN = RGBColor(248, 248, 248)  # 偶数行：浅灰背景

# 图表配色（主要使用蓝色系）
CHART_COLORS = [
    '#008BCE',  # 主蓝色 RGB(0, 139, 206)
    '#404040',  # 深灰色 RGB(64, 64, 64)
    '#808080',  # 浅灰色 RGB(128, 128, 128)
    '#B3D9ED',  # 浅蓝色（蓝色变体）
    '#1A5F8A',  # 深蓝色（蓝色变体）
]

# ==================== 字体配置 ====================

FONT_NAME_CN = "微软雅黑"  # 中文字体（专业商务标准）
FONT_NAME_EN = "Arial"  # 英文字体/数字

# ==================== 字号配置（专业设计标准）====================
# 参考标准：封面54-66pt，章节40-48pt，正文页标题32-36pt，内容20-24pt

# 封面页字号
FONT_SIZE_COVER_TITLE = Pt(60)  # 封面主标题：60pt
FONT_SIZE_COVER_SUBTITLE = Pt(26)  # 封面副标题：26pt

# 章节页字号（统一标准）
FONT_SIZE_SECTION_TITLE = Pt(60)  # 章节标题：60pt，白色
FONT_SIZE_SECTION_SUBTITLE = Pt(20)  # 章节副标题：20pt，浅天蓝色
FONT_SIZE_SECTION_NUMBER = Pt(80)  # 章节编号：80pt，带底色

# 正文页字号（统一标准）
FONT_SIZE_CONTENT_TITLE = Pt(36)  # 页面标题：36pt
FONT_SIZE_CONTENT_SUBTITLE = Pt(24)  # 正文小标题：24pt
FONT_SIZE_CONTENT_BODY = Pt(18)  # 正文内容：18pt

# 图表字号（统一标准）
FONT_SIZE_CHART_TITLE = Pt(14)  # 图表标题：14pt，不加粗
FONT_SIZE_CHART_AXIS = Pt(12)  # 图表轴标签：12pt
FONT_SIZE_CHART_LEGEND = Pt(12)  # 图表图例：12pt
FONT_SIZE_CHART_LABEL = Pt(12)  # 图表数据标签：12pt

# 兼容性别名（旧代码）
FONT_SIZE_TITLE = Pt(32)  # 页面标题：32pt（旧版）
FONT_SIZE_SUBTITLE = Pt(20)  # 副标题：20pt（旧版）
FONT_SIZE_BODY = Pt(20)  # 正文内容：20pt（旧版）
FONT_SIZE_COMMENT = Pt(16)  # 评论说明：16pt
FONT_SIZE_TABLE_HEADER = Pt(14)  # 表头：14pt
FONT_SIZE_TABLE_DATA = Pt(12)  # 表格数据：12pt

# ==================== 行间距配置（专业设计标准）====================
# 参考标准：正文1.2-1.5倍，标题1.0-1.2倍

LINE_SPACING_TITLE = 1.1  # 标题行距：1.1倍（紧凑有力）
LINE_SPACING_BODY = 1.3  # 正文行距：1.3倍（舒适阅读）
LINE_SPACING_TABLE = 1.0  # 表格行距：1.0倍（紧凑）

# ==================== 位置与尺寸配置 ====================

# 章节页装饰条尺寸（统一标准）
SECTION_BAR_WIDTH = 6.5  # cm
SECTION_BAR_HEIGHT = 1.0  # cm

# 内容页左侧文本框高度（统一标准）
CONTENT_LEFT_BOX_HEIGHT = Inches(15 / 2.54)  # 15cm转英寸

# 标题位置
TITLE_LEFT = Inches(0.5)
TITLE_TOP = Inches(0.5)
TITLE_WIDTH = Inches(15)
TITLE_HEIGHT = Inches(0.6)

# 评论框位置（页面底部）
COMMENT_LEFT = Inches(0.8)
COMMENT_TOP = Inches(6.3)
COMMENT_WIDTH = Inches(12.5)
COMMENT_HEIGHT = Inches(0.8)

# 内容区域（标题和评论之间）
CONTENT_LEFT = Inches(0.8)
CONTENT_TOP = Inches(1.3)
CONTENT_WIDTH = Inches(12.5)
CONTENT_HEIGHT = Inches(4.8)

# 图表尺寸
CHART_WIDTH = Inches(6)
CHART_HEIGHT = Inches(4)

# 表格尺寸
TABLE_WIDTH = Inches(12)
TABLE_ROW_HEIGHT = Inches(0.35)

# ==================== 图表配置 ====================

# matplotlib图表DPI
CHART_DPI = 300

# 图表样式
CHART_STYLE = 'seaborn-v0_8-darkgrid'

# 图表保存格式
CHART_FORMAT = 'png'

# ==================== 数据源映射 ====================

# Excel Sheet名称到数据的映射
EXCEL_SHEET_MAPPING = {
    'farm_info': {
        'sheet_name': '牧场基础信息',
        'required': True,
        'dynamic': False,
        'detail_only': False,
        'header': None,
        'description': '封面信息 + 牧场概况基础数据'
    },
    'raw_data': {
        'sheet_name': '牧场牛群原始数据',
        'required': False,
        'dynamic': True,
        'detail_only': True,
        'description': '原始牛只档案，供统计/对比使用'
    },
    'pedigree_analysis': {
        'sheet_name': '系谱识别分析',
        'required': True,
        'dynamic': True,
        'detail_only': False,
        'description': '系谱识别率汇总'
    },
    'pedigree_detail': {
        'sheet_name': '全群母牛系谱识别明细',
        'required': False,
        'dynamic': True,
        'detail_only': True,
        'description': '系谱缺失/明细列表（可选分页）'
    },
    'traits_yearly': {
        'sheet_name': '年份汇总与性状进展',
        'required': False,
        'dynamic': True,
        'detail_only': False,
        'description': '年度头数与性状趋势'
    },
    'traits_summary': {
        'sheet_name': '育种性状明细',
        'required': True,
        'dynamic': True,
        'detail_only': False,
        'description': '多性状明细列表'
    },
    'traits_index_distribution': {
        'sheet_name': '育种指数分布分析',
        'required': True,
        'dynamic': True,
        'detail_only': False,
        'description': '综合指数分布区间'
    },
    'traits_tpi': {
        'sheet_name': 'TPI分布分析',
        'required': True,
        'dynamic': True,
        'detail_only': False,
        'description': 'TPI 区间分布'
    },
    'traits_nm': {
        'sheet_name': 'NM$分布分析',
        'required': True,
        'dynamic': True,
        'detail_only': False,
        'description': 'NM$ 区间分布'
    },
    'cow_index_rank': {
        'sheet_name': '母牛指数排名明细',
        'required': True,
        'dynamic': True,
        'detail_only': False,
        'description': '母牛排名及综合指数'
    },
    'breeding_genes': {
        'sheet_name': '配种记录-隐性基因分析',
        'required': False,
        'dynamic': True,
        'detail_only': False,
        'description': '配种隐性基因载体统计'
    },
    'breeding_inbreeding': {
        'sheet_name': '配种记录-近交系数分析',
        'required': False,
        'dynamic': True,
        'detail_only': False,
        'description': '配种近交区间统计'
    },
    'breeding_detail': {
        'sheet_name': '配种记录-隐性基因及近交系数明细',
        'required': False,
        'dynamic': True,
        'detail_only': True,
        'description': '配种记录明细（大表，可分页或跳过）'
    },
    'used_bulls_summary': {
        'sheet_name': '已用公牛性状汇总',
        'required': True,
        'dynamic': True,
        'detail_only': False,
        'description': '已用公牛按年份/性状汇总'
    },
    'used_bulls_detail': {
        'sheet_name': '已用公牛性状明细',
        'required': False,
        'dynamic': True,
        'detail_only': True,
        'description': '已用公牛明细列表（配次/性状）'
    },
    'candidate_bulls_rank': {
        'sheet_name': '备选公牛排名',
        'required': True,
        'dynamic': True,
        'detail_only': False,
        'description': '优质冻精筛选与排名'
    },
    'candidate_bulls_genes': {
        'sheet_name': '备选公牛-隐性基因分析',
        'required': False,
        'dynamic': True,
        'detail_only': False,
        'description': '备选公牛隐性基因风险'
    },
    'candidate_bulls_inbreeding': {
        'sheet_name': '备选公牛-近交系数分析',
        'required': False,
        'dynamic': True,
        'detail_only': False,
        'description': '备选公牛后代近交评估'
    },
    'candidate_bulls_detail': {
        'sheet_name': '备选公牛-明细表',
        'required': False,
        'dynamic': True,
        'detail_only': True,
        'description': '备选公牛与母牛匹配明细'
    },
    'mating_results': {
        'sheet_name': '个体选配推荐结果',
        'required': True,
        'dynamic': True,
        'detail_only': False,
        'description': '选配统计摘要 + 推荐列表'
    },
}

# ==================== 风险等级阈值 ====================

# 近交系数风险等级
INBREEDING_THRESHOLDS = {
    'low': 0.03125,  # <3.125% 低风险
    'medium': 0.0625,  # 3.125-6.25% 中风险
    'high': 0.125,  # 6.25-12.5% 高风险
    # >12.5% 极高风险
}

# 基因纯合风险等级
GENE_RISK_THRESHOLDS = {
    'safe': 0.03125,  # <3.125% 安全
    'low': 0.0625,  # 3.125-6.25% 低风险
    'medium': 0.125,  # 6.25-12.5% 中风险
    # >12.5% 高风险
}

# TPI/NM$分段阈值（可根据实际情况调整）
TPI_THRESHOLDS = {
    'very_low': 2400,
    'low': 2600,
    'medium': 2800,
    'high': 3000,
}

NM_THRESHOLDS = {
    'very_low': 500,
    'low': 700,
    'medium': 900,
    'high': 1100,
}
