"""
图表生成器 - 使用matplotlib/seaborn生成专业图表
"""

import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple, Dict
import logging
from datetime import datetime
import tempfile

from .config import (
    CHART_COLORS, CHART_DPI, CHART_FORMAT,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER, COLOR_PRIMARY,
    FONT_NAME_CN
)

logger = logging.getLogger(__name__)

# 设置中文字体
plt.rcParams['font.sans-serif'] = [FONT_NAME_CN, 'Arial Unicode MS', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# 设置seaborn样式
sns.set_style("whitegrid")
sns.set_palette(CHART_COLORS)


class ChartCreator:
    """图表创建器"""

    def __init__(self, output_dir: Optional[Path] = None):
        """
        初始化图表创建器

        Args:
            output_dir: 图表输出目录，None则使用临时目录
        """
        if output_dir:
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.output_dir = Path(tempfile.gettempdir()) / "ppt_charts"
            self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"图表输出目录: {self.output_dir}")

    def _save_figure(self, fig, filename: str) -> Path:
        """
        保存图表

        Args:
            fig: matplotlib figure对象
            filename: 文件名

        Returns:
            保存的文件路径
        """
        filepath = self.output_dir / f"{filename}.{CHART_FORMAT}"
        fig.savefig(filepath, dpi=CHART_DPI, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        logger.info(f"图表已保存: {filepath.name}")
        return filepath

    def create_bar_chart(
        self,
        data: pd.DataFrame,
        x_col: str,
        y_col: str,
        title: str,
        xlabel: str = "",
        ylabel: str = "",
        color: Optional[str] = None,
        horizontal: bool = False,
        show_values: bool = True,
        figsize: Tuple[float, float] = (10, 6)
    ) -> Path:
        """
        创建柱状图

        Args:
            data: 数据DataFrame
            x_col: X轴列名
            y_col: Y轴列名
            title: 图表标题
            xlabel: X轴标签
            ylabel: Y轴标签
            color: 柱子颜色
            horizontal: 是否水平柱状图
            show_values: 是否显示数值标签
            figsize: 图表尺寸

        Returns:
            图表文件路径
        """
        fig, ax = plt.subplots(figsize=figsize)

        if horizontal:
            bars = ax.barh(data[x_col], data[y_col], color=color or CHART_COLORS[0])
            if show_values:
                for i, (bar, value) in enumerate(zip(bars, data[y_col])):
                    ax.text(value, i, f' {value:.0f}', va='center', fontsize=10)
        else:
            bars = ax.bar(data[x_col], data[y_col], color=color or CHART_COLORS[0])
            if show_values:
                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:.0f}',
                           ha='center', va='bottom', fontsize=10)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.grid(axis='y' if not horizontal else 'x', alpha=0.3, linestyle='--')

        plt.tight_layout()
        return self._save_figure(fig, f"bar_{datetime.now().strftime('%H%M%S%f')}")

    def create_line_chart(
        self,
        data: pd.DataFrame,
        x_col: str,
        y_cols: List[str],
        title: str,
        xlabel: str = "",
        ylabel: str = "",
        labels: Optional[List[str]] = None,
        figsize: Tuple[float, float] = (10, 6),
        show_markers: bool = True
    ) -> Path:
        """
        创建折线图（支持多条线）

        Args:
            data: 数据DataFrame
            x_col: X轴列名
            y_cols: Y轴列名列表
            title: 图表标题
            xlabel: X轴标签
            ylabel: Y轴标签
            labels: 图例标签
            figsize: 图表尺寸
            show_markers: 是否显示数据点标记

        Returns:
            图表文件路径
        """
        fig, ax = plt.subplots(figsize=figsize)

        if labels is None:
            labels = y_cols

        for i, (y_col, label) in enumerate(zip(y_cols, labels)):
            marker = 'o' if show_markers else None
            ax.plot(data[x_col], data[y_col], marker=marker, linewidth=2,
                   label=label, color=CHART_COLORS[i % len(CHART_COLORS)])

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.legend(loc='best', fontsize=10)
        ax.grid(alpha=0.3, linestyle='--')

        plt.tight_layout()
        return self._save_figure(fig, f"line_{datetime.now().strftime('%H%M%S%f')}")

    def create_pie_chart(
        self,
        data: pd.DataFrame,
        labels_col: str,
        values_col: str,
        title: str,
        colors: Optional[List[str]] = None,
        explode: Optional[List[float]] = None,
        show_percentage: bool = True,
        figsize: Tuple[float, float] = (8, 8)
    ) -> Path:
        """
        创建饼图

        Args:
            data: 数据DataFrame
            labels_col: 标签列名
            values_col: 数值列名
            title: 图表标题
            colors: 自定义颜色列表
            explode: 突出显示的扇区（0-0.1之间）
            show_percentage: 是否显示百分比
            figsize: 图表尺寸

        Returns:
            图表文件路径
        """
        fig, ax = plt.subplots(figsize=figsize)

        labels = data[labels_col].tolist()
        values = data[values_col].tolist()

        if colors is None:
            colors = CHART_COLORS[:len(labels)]

        def autopct_format(pct):
            return f'{pct:.1f}%' if show_percentage else ''

        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            colors=colors,
            autopct=autopct_format if show_percentage else None,
            explode=explode,
            startangle=90,
            textprops={'fontsize': 11}
        )

        # 加粗百分比文字
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        plt.tight_layout()
        return self._save_figure(fig, f"pie_{datetime.now().strftime('%H%M%S%f')}")

    def create_histogram(
        self,
        data: pd.Series,
        title: str,
        xlabel: str = "",
        ylabel: str = "频数",
        bins: int = 30,
        show_normal_curve: bool = True,
        color: Optional[str] = None,
        figsize: Tuple[float, float] = (10, 6)
    ) -> Path:
        """
        创建直方图（可选正态分布曲线）

        Args:
            data: 数据Series
            title: 图表标题
            xlabel: X轴标签
            ylabel: Y轴标签
            bins: 分箱数量
            show_normal_curve: 是否显示正态分布曲线
            color: 柱子颜色
            figsize: 图表尺寸

        Returns:
            图表文件路径
        """
        fig, ax = plt.subplots(figsize=figsize)

        # 绘制直方图
        n, bins_edges, patches = ax.hist(
            data.dropna(),
            bins=bins,
            color=color or CHART_COLORS[0],
            alpha=0.7,
            edgecolor='black',
            density=show_normal_curve
        )

        # 添加正态分布曲线
        if show_normal_curve:
            mu = data.mean()
            sigma = data.std()
            x = np.linspace(data.min(), data.max(), 100)
            y = ((1 / (np.sqrt(2 * np.pi) * sigma)) *
                 np.exp(-0.5 * (1 / sigma * (x - mu))**2))
            ax.plot(x, y, 'r--', linewidth=2, label=f'正态分布 (μ={mu:.0f}, σ={sigma:.0f})')
            ax.legend(loc='best', fontsize=10)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        # 添加统计信息
        stats_text = f'样本量: {len(data.dropna())}\n均值: {data.mean():.0f}\n中位数: {data.median():.0f}'
        ax.text(0.02, 0.98, stats_text,
               transform=ax.transAxes,
               fontsize=10,
               verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout()
        return self._save_figure(fig, f"hist_{datetime.now().strftime('%H%M%S%f')}")

    def create_boxplot(
        self,
        data: pd.DataFrame,
        value_col: str,
        group_col: Optional[str] = None,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        figsize: Tuple[float, float] = (10, 6)
    ) -> Path:
        """
        创建箱线图

        Args:
            data: 数据DataFrame
            value_col: 数值列名
            group_col: 分组列名（可选）
            title: 图表标题
            xlabel: X轴标签
            ylabel: Y轴标签
            figsize: 图表尺寸

        Returns:
            图表文件路径
        """
        fig, ax = plt.subplots(figsize=figsize)

        if group_col:
            data_clean = data[[group_col, value_col]].dropna()
            sns.boxplot(x=group_col, y=value_col, data=data_clean, ax=ax, palette=CHART_COLORS)
        else:
            data_clean = data[value_col].dropna()
            ax.boxplot(data_clean, vert=True, patch_artist=True,
                      boxprops=dict(facecolor=CHART_COLORS[0]))

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        plt.tight_layout()
        return self._save_figure(fig, f"box_{datetime.now().strftime('%H%M%S%f')}")

    def create_scatter_plot(
        self,
        data: pd.DataFrame,
        x_col: str,
        y_col: str,
        title: str,
        xlabel: str = "",
        ylabel: str = "",
        color_col: Optional[str] = None,
        size_col: Optional[str] = None,
        figsize: Tuple[float, float] = (10, 6),
        show_regression: bool = False
    ) -> Path:
        """
        创建散点图

        Args:
            data: 数据DataFrame
            x_col: X轴列名
            y_col: Y轴列名
            title: 图表标题
            xlabel: X轴标签
            ylabel: Y轴标签
            color_col: 颜色分类列（可选）
            size_col: 大小列（可选）
            figsize: 图表尺寸
            show_regression: 是否显示回归线

        Returns:
            图表文件路径
        """
        fig, ax = plt.subplots(figsize=figsize)

        if color_col:
            sns.scatterplot(x=x_col, y=y_col, hue=color_col, size=size_col,
                          data=data, ax=ax, palette=CHART_COLORS, alpha=0.7)
        else:
            ax.scatter(data[x_col], data[y_col], color=CHART_COLORS[0], alpha=0.7, s=50)

        # 添加回归线
        if show_regression:
            z = np.polyfit(data[x_col].dropna(), data[y_col].dropna(), 1)
            p = np.poly1d(z)
            ax.plot(data[x_col], p(data[x_col]), "r--", alpha=0.8, linewidth=2, label='趋势线')
            ax.legend(loc='best', fontsize=10)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.grid(alpha=0.3, linestyle='--')

        plt.tight_layout()
        return self._save_figure(fig, f"scatter_{datetime.now().strftime('%H%M%S%f')}")

    def create_grouped_bar_chart(
        self,
        data: pd.DataFrame,
        x_col: str,
        value_cols: List[str],
        title: str,
        xlabel: str = "",
        ylabel: str = "",
        labels: Optional[List[str]] = None,
        figsize: Tuple[float, float] = (12, 6)
    ) -> Path:
        """
        创建分组柱状图

        Args:
            data: 数据DataFrame
            x_col: X轴列名
            value_cols: 数值列名列表
            title: 图表标题
            xlabel: X轴标签
            ylabel: Y轴标签
            labels: 图例标签
            figsize: 图表尺寸

        Returns:
            图表文件路径
        """
        fig, ax = plt.subplots(figsize=figsize)

        if labels is None:
            labels = value_cols

        x = np.arange(len(data[x_col]))
        width = 0.8 / len(value_cols)

        for i, (col, label) in enumerate(zip(value_cols, labels)):
            offset = width * i - (width * len(value_cols) / 2) + width / 2
            bars = ax.bar(x + offset, data[col], width, label=label,
                         color=CHART_COLORS[i % len(CHART_COLORS)])

            # 显示数值
            for bar in bars:
                height = bar.get_height()
                if not np.isnan(height):
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:.0f}',
                           ha='center', va='bottom', fontsize=9)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(data[x_col], rotation=45, ha='right')
        ax.legend(loc='best', fontsize=10)
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        plt.tight_layout()
        return self._save_figure(fig, f"grouped_bar_{datetime.now().strftime('%H%M%S%f')}")

    def create_horizontal_bar_comparison(
        self,
        data: pd.DataFrame,
        label_col: str,
        value_col: str,
        title: str,
        xlabel: str = "",
        top_n: int = 10,
        color_thresholds: Optional[Dict[str, float]] = None,
        figsize: Tuple[float, float] = (10, 8)
    ) -> Path:
        """
        创建水平条形图对比（适合公牛对比、排名展示）

        Args:
            data: 数据DataFrame
            label_col: 标签列名
            value_col: 数值列名
            title: 图表标题
            xlabel: X轴标签
            top_n: 显示前N个
            color_thresholds: 颜色阈值字典 {'green': 0.8, 'yellow': 0.5}
            figsize: 图表尺寸

        Returns:
            图表文件路径
        """
        fig, ax = plt.subplots(figsize=figsize)

        # 取前N个并排序
        data_top = data.nlargest(top_n, value_col)

        # 根据阈值分配颜色
        if color_thresholds:
            colors = []
            for value in data_top[value_col]:
                if value >= color_thresholds.get('green', float('inf')):
                    colors.append('#70AD47')  # 绿色
                elif value >= color_thresholds.get('yellow', float('inf')):
                    colors.append('#FFC000')  # 黄色
                else:
                    colors.append('#C00000')  # 红色
        else:
            colors = CHART_COLORS[0]

        bars = ax.barh(data_top[label_col], data_top[value_col], color=colors)

        # 显示数值
        for i, (bar, value) in enumerate(zip(bars, data_top[value_col])):
            ax.text(value, i, f' {value:.1f}', va='center', fontsize=10)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.invert_yaxis()  # 最高值在上
        ax.grid(axis='x', alpha=0.3, linestyle='--')

        plt.tight_layout()
        return self._save_figure(fig, f"hbar_{datetime.now().strftime('%H%M%S%f')}")

    def create_stacked_bar_chart(
        self,
        data: pd.DataFrame,
        x_col: str,
        value_cols: List[str],
        title: str,
        xlabel: str = "",
        ylabel: str = "",
        labels: Optional[List[str]] = None,
        figsize: Tuple[float, float] = (10, 6)
    ) -> Path:
        """
        创建堆叠柱状图

        Args:
            data: 数据DataFrame
            x_col: X轴列名
            value_cols: 数值列名列表
            title: 图表标题
            xlabel: X轴标签
            ylabel: Y轴标签
            labels: 图例标签
            figsize: 图表尺寸

        Returns:
            图表文件路径
        """
        fig, ax = plt.subplots(figsize=figsize)

        if labels is None:
            labels = value_cols

        x = np.arange(len(data[x_col]))
        bottom = np.zeros(len(data))

        for i, (col, label) in enumerate(zip(value_cols, labels)):
            ax.bar(x, data[col], bottom=bottom, label=label,
                  color=CHART_COLORS[i % len(CHART_COLORS)])
            bottom += data[col]

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(data[x_col], rotation=45, ha='right')
        ax.legend(loc='best', fontsize=10)
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        plt.tight_layout()
        return self._save_figure(fig, f"stacked_{datetime.now().strftime('%H%M%S%f')}")

    def cleanup(self):
        """清理临时图表文件"""
        try:
            import shutil
            if self.output_dir.exists():
                shutil.rmtree(self.output_dir)
                logger.info(f"已清理图表临时目录: {self.output_dir}")
        except Exception as e:
            logger.warning(f"清理临时目录失败: {e}")
