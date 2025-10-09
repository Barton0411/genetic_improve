"""
图表构建器
用于创建Excel中的各种图表
"""

from openpyxl.chart import PieChart, BarChart, LineChart, Reference
from openpyxl.chart.label import DataLabelList


class ChartBuilder:
    """图表构建器"""

    def create_pie_chart(self, worksheet, data_range: dict, position: str, title: str):
        """
        创建饼图（2D商务风格）

        Args:
            worksheet: 工作表对象
            data_range: 数据范围 {'labels': (min_row, max_row, col), 'values': (min_row, max_row, col)}
            position: 图表位置 (如 'E2')
            title: 图表标题

        Returns:
            PieChart对象
        """
        from openpyxl.chart import PieChart
        from openpyxl.chart.text import RichText
        from openpyxl.drawing.text import Paragraph, ParagraphProperties, CharacterProperties, Font as DrawingFont

        # 使用2D饼图
        chart = PieChart()
        chart.style = 10  # 使用商务风格样式
        chart.height = 10  # 高度（厘米）
        chart.width = 10   # 宽度（厘米）

        # 设置标题（14号字体）
        from openpyxl.chart.title import Title
        from openpyxl.chart.text import Text, RichText
        from openpyxl.drawing.text import Paragraph, RegularTextRun

        char_props = CharacterProperties(sz=1400)  # 14号字体 (14 * 100)
        run = RegularTextRun(t=title, rPr=char_props)
        para = Paragraph()
        para.r.append(run)
        rich_text = RichText()
        rich_text.paragraphs.append(para)

        text_obj = Text()
        text_obj.rich = rich_text
        title_obj = Title()
        title_obj.tx = text_obj
        chart.title = title_obj

        # 设置数据
        labels = Reference(
            worksheet,
            min_col=data_range['labels'][2],
            min_row=data_range['labels'][0],
            max_row=data_range['labels'][1]
        )
        data = Reference(
            worksheet,
            min_col=data_range['values'][2],
            min_row=data_range['values'][0],
            max_row=data_range['values'][1]
        )

        chart.add_data(data, titles_from_data=False)
        chart.set_categories(labels)

        # 只显示数值和百分比（不显示类别名和系列名）
        chart.dataLabels = DataLabelList()
        chart.dataLabels.showPercent = True
        chart.dataLabels.showCatName = False  # 不显示类别名
        chart.dataLabels.showVal = True  # 显示数值
        chart.dataLabels.showSerName = False  # 不显示系列名（避免"系列1"）
        chart.dataLabels.showLeaderLines = False
        chart.dataLabels.position = 'bestFit'
        chart.dataLabels.separator = ", "  # 使用逗号+空格分隔

        # 不显示图例
        chart.legend = None

        # 添加图表到工作表
        worksheet.add_chart(chart, position)

        return chart

    def create_bar_chart(self, worksheet, data_range: dict, position: str, title: str,
                        x_axis_title: str = '', y_axis_title: str = ''):
        """
        创建柱状图（2D商务风格）

        Args:
            worksheet: 工作表对象
            data_range: 数据范围
            position: 图表位置
            title: 图表标题
            x_axis_title: X轴标题
            y_axis_title: Y轴标题

        Returns:
            BarChart对象
        """
        from openpyxl.chart import BarChart
        from openpyxl.chart.text import RichText
        from openpyxl.drawing.text import Paragraph, ParagraphProperties, CharacterProperties, Font as DrawingFont

        # 使用2D柱状图
        chart = BarChart()
        chart.style = 11  # 使用商务风格样式
        chart.width = 10   # 宽度（厘米）
        chart.height = 7.5  # 高度（厘米，宽度的3/4）
        chart.type = "col"  # 竖向柱状图
        chart.grouping = "clustered"
        chart.gapWidth = 150  # 柱子间距

        # 设置标题（14号字体）
        from openpyxl.chart.title import Title
        from openpyxl.chart.text import Text, RichText
        from openpyxl.drawing.text import Paragraph, RegularTextRun

        char_props = CharacterProperties(sz=1400)  # 14号字体 (14 * 100)
        run = RegularTextRun(t=title, rPr=char_props)
        para = Paragraph()
        para.r.append(run)
        rich_text = RichText()
        rich_text.paragraphs.append(para)

        text_obj = Text()
        text_obj.rich = rich_text
        title_obj = Title()
        title_obj.tx = text_obj
        chart.title = title_obj

        # 设置数据
        labels = Reference(
            worksheet,
            min_col=data_range['labels'][2],
            min_row=data_range['labels'][0],
            max_row=data_range['labels'][1]
        )
        data = Reference(
            worksheet,
            min_col=data_range['values'][2],
            min_row=data_range['values'][0],
            max_row=data_range['values'][1],
            max_col=data_range['values'][3] if len(data_range['values']) > 3 else data_range['values'][2]
        )

        chart.add_data(data, titles_from_data=False)
        chart.set_categories(labels)

        # 设置坐标轴
        chart.x_axis.title = x_axis_title if x_axis_title else "类别"
        chart.y_axis.title = y_axis_title if y_axis_title else "数量（头）"

        # 只显示数值（不显示类别名和系列名）
        chart.dataLabels = DataLabelList()
        chart.dataLabels.showCatName = False  # 不显示类别名
        chart.dataLabels.showVal = True  # 显示数值
        chart.dataLabels.showSerName = False  # 不显示系列名
        chart.dataLabels.position = 'outEnd'  # 标签显示在柱子顶端外侧

        # 不显示图例
        chart.legend = None

        worksheet.add_chart(chart, position)

        return chart

    def create_line_chart(self, worksheet, data_range: dict, position: str, title: str,
                         x_axis_title: str = '', y_axis_title: str = ''):
        """
        创建折线图

        Args:
            worksheet: 工作表对象
            data_range: 数据范围
            position: 图表位置
            title: 图表标题
            x_axis_title: X轴标题
            y_axis_title: Y轴标题

        Returns:
            LineChart对象
        """
        chart = LineChart()
        chart.title = title
        chart.style = 10
        chart.height = 15
        chart.width = 20

        # 设置数据
        labels = Reference(
            worksheet,
            min_col=data_range['labels'][2],
            min_row=data_range['labels'][0],
            max_row=data_range['labels'][1]
        )
        data = Reference(
            worksheet,
            min_col=data_range['values'][2],
            min_row=data_range['values'][0],
            max_row=data_range['values'][1],
            max_col=data_range['values'][3] if len(data_range['values']) > 3 else data_range['values'][2]
        )

        chart.add_data(data, titles_from_data=True)
        chart.set_categories(labels)

        # 设置坐标轴
        if x_axis_title:
            chart.x_axis.title = x_axis_title
        if y_axis_title:
            chart.y_axis.title = y_axis_title

        # 显示数据标签
        chart.dataLabels = DataLabelList()
        chart.dataLabels.showVal = True

        # 显示网格线
        chart.y_axis.majorGridlines = None

        worksheet.add_chart(chart, position)

        return chart
