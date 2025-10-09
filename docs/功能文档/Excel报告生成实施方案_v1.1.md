# Excel综合报告生成实施方案 v1.1

**文档版本:** v1.1
**创建时间:** 2025-10-07
**基于需求:** Excel报告最终需求.md v1.1
**状态:** 准备开发

---

## 📋 实施决策

### 1. 图表嵌入策略 ✅ 已确定

**方案：** 核心图表嵌入

| Sheet | 图表类型 | 是否嵌入 | 原因 |
|------|---------|---------|------|
| Sheet 1 | 成母牛/后备牛占比饼图 | ✅ 嵌入 | ⭐v1.1新增 基础信息可视化 |
| Sheet 1 | 按胎次分布饼图 | ✅ 嵌入 | ⭐v1.1新增 牛群结构展示 |
| Sheet 2 | 系谱识别饼图×3 | ✅ 嵌入 | 父号/外祖父/外曾外祖父识别率 |
| Sheet 3 | NM$分布图 | ✅ 嵌入 | 柱状图+饼图 |
| Sheet 3 | TPI分布图 | ✅ 嵌入 | 柱状图+饼图 |
| Sheet 3 | NM$正态分布 | ✅ 嵌入 | 核心育种指标 |
| Sheet 3 | TPI正态分布 | ✅ 嵌入 | 核心育种指标 |
| Sheet 3 | 育种指数正态分布 | ✅ 嵌入 | ⭐v1.1新增 核心指标 |
| Sheet 3 | 性状进展折线图 | ✅ 嵌入 | 含对比牧场数据叠加 ⭐v1.1修改 |
| Sheet 4 | 冻精使用热力图 | ❌ 不嵌入 | 数据量大，提供数据即可 |

**预计文件大小：** 2-5MB（完整版）

### 2. 报告版本策略 ✅ v1.1已简化

**方案：** 只生成完整版（取消精简版）⭐v1.1修改

**包含内容：**
- ✅ 所有汇总表
- ✅ 所有明细表
- ✅ 所有嵌入图表
- ✅ 9个Sheet（Sheet 1-8 + Sheet 7A）

**UI设计：**
```
[生成Excel综合报告]  （单一按钮，直接生成完整版）
```

### 3. 多牧场对比模板 ✅ v1.1已简化

**模板文件名：** `多牧场对比数据模板.xlsx`

**模板格式（仅对比牧场性状明细表）：** ⭐v1.1修改

| 牧场名称 | 牛群规模 | 平均NM$ | 平均TPI | 平均产奶 | 平均乳脂率 | 平均乳蛋白率 | ... (其他性状) |
|---------|---------|---------|---------|---------|-----------|-----------|--------------|
| 对比牧场A | 1200 | 450 | 2350 | 12500 | 3.80 | 3.20 | ... |
| 对比牧场B | 800 | 420 | 2280 | 12000 | 3.90 | 3.30 | ... |

**校验规则：**
- 牧场名称不能为空
- NM$、TPI、产奶必须为数字
- 乳脂率、乳蛋白率范围：2.0-6.0%
- 最多支持导入10个对比牧场

---

## 🛠️ 技术实现

### 核心库选择

**使用 openpyxl**
```bash
pip install openpyxl pandas numpy matplotlib scipy
```

**原因：**
- 完整支持 .xlsx 格式
- 支持样式、条件格式、图表
- 纯Python实现，跨平台
- 社区活跃，文档完善

### 项目结构

```
core/
├── excel_report/                     # Excel报告生成模块
│   ├── __init__.py
│   ├── generator.py                  # 主生成器
│   ├── data_collectors/              # 数据收集模块
│   │   ├── __init__.py
│   │   ├── farm_info_collector.py   # Sheet 1
│   │   ├── pedigree_collector.py    # Sheet 2
│   │   ├── traits_collector.py      # Sheet 3
│   │   ├── bull_usage_collector.py  # Sheet 4
│   │   ├── gene_collector.py        # Sheet 5
│   │   ├── inbreeding_collector.py  # Sheet 6
│   │   ├── bull_ranking_collector.py # Sheet 7
│   │   ├── bull_prediction_collector.py # Sheet 7A ⭐v1.1新增
│   │   └── mating_collector.py      # Sheet 8
│   ├── sheet_builders/               # Sheet构建模块
│   │   ├── __init__.py
│   │   ├── base_builder.py          # 基类
│   │   ├── sheet1_builder.py
│   │   ├── sheet2_builder.py
│   │   ├── sheet3_builder.py
│   │   ├── sheet4_builder.py
│   │   ├── sheet5_builder.py
│   │   ├── sheet6_builder.py
│   │   ├── sheet7_builder.py
│   │   ├── sheet7a_builder.py       # ⭐v1.1新增
│   │   └── sheet8_builder.py
│   ├── formatters/                   # 格式化模块
│   │   ├── __init__.py
│   │   ├── style_manager.py         # 样式管理
│   │   ├── conditional_format.py    # 条件格式
│   │   └── chart_builder.py         # 图表构建
│   └── utils/                        # 工具模块
│       ├── __init__.py
│       ├── data_validator.py        # 数据校验
│       └── file_checker.py          # 文件检查
```

### 数据流程

```
用户点击按钮
    ↓
ExcelReportGenerator.generate()
    ↓
检查必要文件 (file_checker)
    ↓
收集所有数据 (data_collectors)
    ↓
按顺序生成9个Sheet (sheet_builders)
    ↓
应用格式化 (formatters)
    ↓
嵌入图表 (chart_builder)
    ↓
保存文件
    ↓
提示用户
```

---

## 📊 核心类设计

### 1. ExcelReportGenerator (主生成器)

```python
# core/excel_report/generator.py

from pathlib import Path
from openpyxl import Workbook
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ExcelReportGenerator:
    """Excel综合报告生成器 v1.1"""

    def __init__(self, project_folder: Path):
        """
        初始化生成器

        Args:
            project_folder: 项目文件夹路径
        """
        self.project_folder = project_folder
        self.analysis_folder = project_folder / "分析结果"

        # 初始化workbook
        self.wb = Workbook()
        self.wb.remove(self.wb.active)  # 删除默认sheet

        # 样式管理器
        from .formatters import StyleManager
        self.style_manager = StyleManager()

        # 图表构建器
        from .formatters import ChartBuilder
        self.chart_builder = ChartBuilder()

    def generate(self) -> tuple[bool, str]:
        """
        生成Excel报告（完整版）

        Returns:
            (成功标志, 文件路径或错误消息)
        """
        try:
            logger.info("开始生成Excel综合报告 v1.1")

            # 1. 检查数据文件
            from .utils import FileChecker
            checker = FileChecker(self.analysis_folder)
            missing_files = checker.check_required_files()
            if missing_files:
                return False, f"缺少必要文件：{', '.join(missing_files)}"

            # 2. 收集所有数据
            logger.info("收集数据...")
            data = self._collect_all_data()

            # 3. 生成9个Sheet
            logger.info("生成Sheet 1: 牧场基础信息")
            self._build_sheet1(data['farm_info'])

            logger.info("生成Sheet 2: 系谱识别分析")
            self._build_sheet2(data['pedigree'])

            logger.info("生成Sheet 3: 育种性状分析")
            self._build_sheet3(data['traits'])

            logger.info("生成Sheet 4: 公牛使用分析")
            self._build_sheet4(data['bull_usage'])

            logger.info("生成Sheet 5: 隐性基因分析")
            self._build_sheet5(data['genes'])

            logger.info("生成Sheet 6: 近交系数分析")
            self._build_sheet6(data['inbreeding'])

            logger.info("生成Sheet 7: 备选公牛排名")
            self._build_sheet7(data['bull_ranking'])

            logger.info("生成Sheet 7A: 备选公牛预测分析")  # ⭐v1.1新增
            self._build_sheet7a(data['bull_prediction'])

            if data.get('mating'):
                logger.info("生成Sheet 8: 选配推荐结果")
                self._build_sheet8(data['mating'])

            # 4. 保存文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"育种分析综合报告_{timestamp}.xlsx"
            output_path = self.analysis_folder / filename

            self.wb.save(output_path)
            logger.info(f"Excel报告已保存: {output_path}")

            return True, str(output_path)

        except Exception as e:
            logger.error(f"生成Excel报告失败: {e}", exc_info=True)
            return False, str(e)

    def _collect_all_data(self) -> dict:
        """收集所有需要的数据"""
        from .data_collectors import (
            collect_farm_info,
            collect_pedigree_data,
            collect_traits_data,
            collect_bull_usage_data,
            collect_gene_data,
            collect_inbreeding_data,
            collect_bull_ranking_data,
            collect_bull_prediction_data,  # ⭐v1.1新增
            collect_mating_data
        )

        return {
            'farm_info': collect_farm_info(self.project_folder),
            'pedigree': collect_pedigree_data(self.analysis_folder),
            'traits': collect_traits_data(self.analysis_folder, self.project_folder),
            'bull_usage': collect_bull_usage_data(self.analysis_folder),
            'genes': collect_gene_data(self.analysis_folder),
            'inbreeding': collect_inbreeding_data(self.analysis_folder),
            'bull_ranking': collect_bull_ranking_data(self.analysis_folder),
            'bull_prediction': collect_bull_prediction_data(self.analysis_folder),  # ⭐v1.1新增
            'mating': collect_mating_data(self.analysis_folder)
        }

    def _build_sheet1(self, data: dict):
        """构建Sheet 1: 牧场基础信息"""
        from .sheet_builders import Sheet1Builder
        builder = Sheet1Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet2(self, data: dict):
        """构建Sheet 2: 系谱识别分析"""
        from .sheet_builders import Sheet2Builder
        builder = Sheet2Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet3(self, data: dict):
        """构建Sheet 3: 育种性状分析"""
        from .sheet_builders import Sheet3Builder
        builder = Sheet3Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet4(self, data: dict):
        """构建Sheet 4: 公牛使用分析"""
        from .sheet_builders import Sheet4Builder
        builder = Sheet4Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet5(self, data: dict):
        """构建Sheet 5: 隐性基因分析"""
        from .sheet_builders import Sheet5Builder
        builder = Sheet5Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet6(self, data: dict):
        """构建Sheet 6: 近交系数分析"""
        from .sheet_builders import Sheet6Builder
        builder = Sheet6Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet7(self, data: dict):
        """构建Sheet 7: 备选公牛排名"""
        from .sheet_builders import Sheet7Builder
        builder = Sheet7Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet7a(self, data: dict):
        """构建Sheet 7A: 备选公牛预测分析 ⭐v1.1新增"""
        from .sheet_builders import Sheet7ABuilder
        builder = Sheet7ABuilder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)

    def _build_sheet8(self, data: dict):
        """构建Sheet 8: 个体选配结果"""
        from .sheet_builders import Sheet8Builder
        builder = Sheet8Builder(self.wb, self.style_manager, self.chart_builder)
        builder.build(data)
```

### 2. StyleManager (样式管理器)

```python
# core/excel_report/formatters/style_manager.py

from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

class StyleManager:
    """统一管理Excel样式"""

    # 颜色定义
    COLOR_HEADER_BG = "2E5C8A"      # 深蓝色
    COLOR_HEADER_TEXT = "FFFFFF"     # 白色
    COLOR_ROW_EVEN = "F5F5F5"        # 浅灰色
    COLOR_TOTAL_BG = "D6E9F8"        # 浅蓝色
    COLOR_RISK_HIGH = "FFE6E6"       # 红色背景
    COLOR_RISK_MEDIUM = "FFF9E6"     # 黄色背景
    COLOR_RISK_LOW = "E6F9E6"        # 绿色背景

    def __init__(self):
        self._init_styles()

    def _init_styles(self):
        """初始化常用样式"""
        # 标题行样式
        self.header_font = Font(
            name='微软雅黑',
            size=12,
            bold=True,
            color=self.COLOR_HEADER_TEXT
        )
        self.header_fill = PatternFill(
            start_color=self.COLOR_HEADER_BG,
            end_color=self.COLOR_HEADER_BG,
            fill_type='solid'
        )
        self.header_alignment = Alignment(
            horizontal='center',
            vertical='center',
            wrap_text=True
        )

        # 数据行样式
        self.data_font = Font(name='微软雅黑', size=10)
        self.data_alignment = Alignment(horizontal='left', vertical='center')
        self.data_alignment_center = Alignment(horizontal='center', vertical='center')
        self.data_alignment_right = Alignment(horizontal='right', vertical='center')

        # 合计行样式
        self.total_font = Font(name='微软雅黑', size=10, bold=True)
        self.total_fill = PatternFill(
            start_color=self.COLOR_TOTAL_BG,
            end_color=self.COLOR_TOTAL_BG,
            fill_type='solid'
        )

        # 边框
        thin_border = Side(border_style="thin", color="000000")
        self.border = Border(
            left=thin_border,
            right=thin_border,
            top=thin_border,
            bottom=thin_border
        )

    def apply_header_style(self, cell):
        """应用标题样式"""
        cell.font = self.header_font
        cell.fill = self.header_fill
        cell.alignment = self.header_alignment
        cell.border = self.border

    def apply_data_style(self, cell, alignment='left'):
        """应用数据样式"""
        cell.font = self.data_font
        cell.border = self.border
        if alignment == 'center':
            cell.alignment = self.data_alignment_center
        elif alignment == 'right':
            cell.alignment = self.data_alignment_right
        else:
            cell.alignment = self.data_alignment

    def apply_total_style(self, cell):
        """应用合计行样式"""
        cell.font = self.total_font
        cell.fill = self.total_fill
        cell.border = self.border
        cell.alignment = self.data_alignment_center

    def apply_risk_color(self, cell, risk_level: str):
        """应用风险等级颜色"""
        if risk_level == 'high':
            cell.fill = PatternFill(
                start_color=self.COLOR_RISK_HIGH,
                end_color=self.COLOR_RISK_HIGH,
                fill_type='solid'
            )
        elif risk_level == 'medium':
            cell.fill = PatternFill(
                start_color=self.COLOR_RISK_MEDIUM,
                end_color=self.COLOR_RISK_MEDIUM,
                fill_type='solid'
            )
        elif risk_level == 'low':
            cell.fill = PatternFill(
                start_color=self.COLOR_RISK_LOW,
                end_color=self.COLOR_RISK_LOW,
                fill_type='solid'
            )
```

### 3. BaseSheetBuilder (Sheet构建器基类)

```python
# core/excel_report/sheet_builders/base_builder.py

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from abc import ABC, abstractmethod

class BaseSheetBuilder(ABC):
    """Sheet构建器基类"""

    def __init__(self, workbook: Workbook, style_manager, chart_builder):
        self.wb = workbook
        self.style_manager = style_manager
        self.chart_builder = chart_builder
        self.ws = None

    @abstractmethod
    def build(self, data: dict):
        """构建Sheet（子类必须实现）"""
        pass

    def _create_sheet(self, title: str) -> Worksheet:
        """创建新的Sheet"""
        self.ws = self.wb.create_sheet(title=title)
        return self.ws

    def _write_header(self, row: int, headers: list, start_col: int = 1):
        """写入标题行"""
        for col_idx, header in enumerate(headers, start=start_col):
            cell = self.ws.cell(row=row, column=col_idx, value=header)
            self.style_manager.apply_header_style(cell)

    def _write_data_row(self, row: int, values: list, start_col: int = 1, alignment='left'):
        """写入数据行"""
        for col_idx, value in enumerate(values, start=start_col):
            cell = self.ws.cell(row=row, column=col_idx, value=value)
            self.style_manager.apply_data_style(cell, alignment)

    def _write_total_row(self, row: int, values: list, start_col: int = 1):
        """写入合计行"""
        for col_idx, value in enumerate(values, start=start_col):
            cell = self.ws.cell(row=row, column=col_idx, value=value)
            self.style_manager.apply_total_style(cell)

    def _set_column_widths(self, widths: dict):
        """设置列宽 {列号: 宽度}"""
        from openpyxl.utils import get_column_letter
        for col_idx, width in widths.items():
            col_letter = get_column_letter(col_idx)
            self.ws.column_dimensions[col_letter].width = width

    def _freeze_panes(self, cell: str):
        """冻结窗格"""
        self.ws.freeze_panes = cell

    def _add_pie_chart(self, data: dict, position: str, title: str):
        """添加饼图"""
        return self.chart_builder.create_pie_chart(
            self.ws, data, position, title
        )

    def _add_bar_chart(self, data: dict, position: str, title: str):
        """添加柱状图"""
        return self.chart_builder.create_bar_chart(
            self.ws, data, position, title
        )

    def _add_line_chart(self, data: dict, position: str, title: str):
        """添加折线图"""
        return self.chart_builder.create_line_chart(
            self.ws, data, position, title
        )
```

---

## 📅 开发计划

### Phase 1: 基础框架 + Sheet 1,2,8 (3天)

**Day 1: 框架搭建**
- [x] 创建项目结构
- [ ] 实现 ExcelReportGenerator 主类
- [ ] 实现 StyleManager
- [ ] 实现 ChartBuilder
- [ ] 实现 BaseSheetBuilder
- [ ] 实现 FileChecker

**Day 2: Sheet 1**
- [ ] 实现 farm_info_collector
- [ ] 实现 Sheet1Builder
  - [ ] 基本信息
  - [ ] 牛群结构统计
  - [ ] 2个饼图 ⭐v1.1新增
  - [ ] 上传数据概览（新格式）⭐v1.1修改
- [ ] 测试 Sheet 1 生成

**Day 3: Sheet 2 & 8**
- [ ] 实现 pedigree_collector
- [ ] 实现 Sheet2Builder
  - [ ] 汇总表
  - [ ] 3个饼图
  - [ ] 明细表
- [ ] 实现 mating_collector
- [ ] 实现 Sheet8Builder（新格式）⭐v1.1修改
- [ ] 测试 Phase 1

### Phase 2: Sheet 3-7 (4天)

**Day 4: Sheet 3 (上)**
- [ ] 实现 traits_collector
- [ ] 实现 Sheet3Builder
  - [ ] 按年份汇总表
  - [ ] NM$分布（图表）
  - [ ] TPI分布（图表）

**Day 5: Sheet 3 (下)**
- [ ] 育种指数正态分布 ⭐v1.1新增
- [ ] NM$正态分布
- [ ] TPI正态分布
- [ ] 性状进展折线图（含对比）⭐v1.1修改
- [ ] 对比牧场功能
- [ ] 明细表

**Day 6: Sheet 4 & 5**
- [ ] 实现 bull_usage_collector
- [ ] 实现 Sheet4Builder
  - [ ] 按年度汇总表
  - [ ] 各年份明细表（新格式）⭐v1.1修改
- [ ] 实现 gene_collector
- [ ] 实现 Sheet5Builder
  - [ ] 汇总表
  - [ ] 后代风险预测（4级）⭐v1.1修改
  - [ ] 明细表（新格式）⭐v1.1修改

**Day 7: Sheet 6, 7, 7A**
- [ ] 实现 inbreeding_collector
- [ ] 实现 Sheet6Builder
- [ ] 实现 bull_ranking_collector
- [ ] 实现 Sheet7Builder（删除品种/出生日期）⭐v1.1修改
- [ ] 实现 bull_prediction_collector ⭐v1.1新增
- [ ] 实现 Sheet7ABuilder ⭐v1.1新增

### Phase 3: 测试优化 (2天)

**Day 8: 集成测试**
- [ ] 完整流程测试
- [ ] 修复bug
- [ ] 性能优化

**Day 9: UI集成**
- [ ] 主窗口添加按钮
- [ ] 进度对话框
- [ ] 错误处理
- [ ] 用户体验优化

---

## ✅ 验收标准

### 功能验收
- [ ] 能够生成完整版报告（9个Sheet）
- [ ] Sheet 1: 包含2个饼图
- [ ] Sheet 2: 包含3个饼图
- [ ] Sheet 3: 包含3个正态分布图 + 折线图（含对比）
- [ ] Sheet 4: 明细表包含"使用支数"列
- [ ] Sheet 5: 4级风险分类 + 新格式明细表
- [ ] Sheet 7: 删除品种/出生日期
- [ ] Sheet 7A: 备选公牛预测分析完整
- [ ] Sheet 8: 新格式选配结果
- [ ] 所有格式正确
- [ ] 生成速度 < 60秒

### 代码质量
- [ ] 代码结构清晰
- [ ] 模块职责明确
- [ ] 日志完善
- [ ] 异常处理健全
- [ ] 注释充分

---

**预计总开发时间:** 9天
**开始日期:** 2025-10-08
**预计完成日期:** 2025-10-18

**最后更新:** 2025-10-07
