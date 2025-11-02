# PPT生成功能完整指南

**文档版本:** v1.0
**更新时间:** 2025-11-02
**适用版本:** v1.2.0+

---

## 📋 目录

1. [概述](#概述)
2. [功能架构](#功能架构)
3. [已实现功能](#已实现功能)
4. [PPT内容结构](#ppt内容结构)
5. [使用指南](#使用指南)
6. [数据依赖](#数据依赖)
7. [自定义配置](#自定义配置)
8. [技术实现](#技术实现)
9. [开发说明](#开发说明)
10. [常见问题](#常见问题)
11. [后续改进计划](#后续改进计划)

---

## 概述

PPT生成功能用于自动生成**牧场遗传改良项目专项服务报告**，涵盖系谱分析、遗传评估、体型评定和公牛使用分析等内容。该功能实现了从数据准备、分析计算到幻灯片生成的全自动化流程。

### 核心特性
- ✅ **全自动化数据准备** - 自动生成所有必需的分析文件
- ✅ **智能数据适配** - 自动处理不同项目的列名差异
- ✅ **数据验证机制** - 自动检查数据完整性和正确性
- ✅ **自动化文本生成** - AI辅助生成分析文本
- ✅ **灵活配置** - 支持自定义性状翻译和阈值
- ✅ **模板支持** - 可使用自定义PPT模板
- ✅ **跨平台字体** - 自动适配不同操作系统的中文字体

---

## 功能架构

### 模块结构

```
core/report/
├── __init__.py                    # 模块初始化
├── ppt_generator.py              # PPT生成主控制器
├── data_preparation.py           # 数据准备模块
├── data_generator.py             # 数据生成器（分析计算）
├── data_adapter.py               # 数据适配器（列名映射）
├── data_validator.py             # 数据验证器
├── analysis_text_generator.py   # 自动化分析文本生成
└── slide_generators/             # 幻灯片生成器
    ├── __init__.py
    ├── base.py                  # 基类（通用功能）
    ├── title_toc.py             # 标题页和目录页
    ├── pedigree_analysis.py     # 系谱分析（第1部分）
    ├── genetic_evaluation.py    # 遗传评估（第2部分）
    ├── linear_score.py          # 体型评定（第3部分）
    └── bull_usage.py            # 公牛使用分析（第4部分）
```

### 配置文件
- **`config/trait_translations.json`** - 性状中英文对照表和阈值配置
  - 性状名称翻译
  - 识别率阈值设置
  - 图表样式配置

---

## 已实现功能

### 1. 数据准备工作流 ✅
**文件位置:** `core/report/data_preparation.py`, `core/report/data_generator.py`

实现了完整的数据准备流程，自动生成PPT所需的所有分析文件。

#### 已实现的数据生成方法：

| 方法名 | 功能说明 | 输出文件 |
|--------|----------|----------|
| `generate_pedigree_identification_analysis()` | 系谱识别情况分析 | `结果-系谱识别情况分析.xlsx` |
| `generate_key_traits_annual_change()` | 关键性状年度变化 | `结果-牛群关键性状年度变化.xlsx` |
| `generate_nm_distribution_charts()` | NM$分布图表 | `在群牛只净利润值分布.xlsx` |
| `generate_quintile_distribution()` | 五等份分布表 | 五等份分布数据 |
| `generate_normal_distribution_charts()` | 正态分布图 | NM$/育种指数正态分布PNG |
| `generate_year_distribution()` | 年份正态分布 | 按年份分组的正态分布图 |
| `generate_traits_progress_charts()` | 性状进展图 | `结果-牛群关键性状进展图/*.png` |
| `generate_semen_usage_trend()` | 冻精使用趋势 | `结果-冻精使用趋势图.xlsx` |
| `generate_index_ranking()` | 指数排名结果 | `结果-指数排名结果.xlsx` |
| `generate_cow_key_traits()` | 母牛关键性状指数 | `结果-母牛关键性状指数.xlsx` |

### 2. 数据适配器 ✅
**文件位置:** `core/report/data_adapter.py`

- ✅ 处理不同项目中的列名差异
- ✅ 自动映射和标准化列名
- ✅ 支持日期格式转换
- ✅ 添加缺失的必需列
- ✅ 数据类型转换

**示例：**
```python
# 自动映射列名
adapted_df = adapter.adapt_dataframe(df, 'cow_data')
# 支持多种列名格式：cow_id / 牛号 / 牛只编号
```

### 3. 自动化分析文本生成 ✅
**文件位置:** `core/report/analysis_text_generator.py`

实现了以下分析文本的自动生成：

- **系谱分析文本**
  - 概述：识别率总体情况
  - 详细分析：父号、外祖父、外曾外祖父识别率
  - 改进建议：针对低识别率的建议

- **遗传评估文本**
  - 性状分析：关键性状的表现
  - 遗传趋势：年度变化趋势
  - 选配建议：基于评估结果的建议

- **育种指数文本**
  - 分布分析：NM$、TPI等指数的分布情况
  - 优秀个体：高指数牛只的特征
  - 选配建议：指数改良方向

- **公牛使用分析文本**
  - 使用情况统计：公牛使用频率
  - 性状贡献：公牛对牛群遗传的贡献
  - 优化建议：公牛使用优化方向

- **性状进展文本**
  - 单个性状的趋势分析
  - 年度变化情况
  - 改进方向建议

### 4. 数据验证和错误处理 ✅
**文件位置:** `core/report/data_validator.py`

完整的数据验证系统：

- ✅ 验证数据框的完整性和正确性
- ✅ 检查必需列是否存在
- ✅ 验证数据类型（日期、数值等）
- ✅ 检查数值范围合理性
- ✅ 验证枚举值的有效性
- ✅ 特定数据类型的业务规则验证
- ✅ 生成详细的验证报告

**验证规则示例：**
```python
# 母牛数据验证规则
{
    'required_columns': ['cow_id', 'birth_date', 'lac'],
    'data_types': {
        'birth_date': 'datetime',
        'lac': 'int'
    },
    'value_ranges': {
        'lac': (0, 15),  # 胎次范围
    },
    'enum_values': {
        '是否在场': ['是', '否']
    }
}
```

### 5. PPT生成器增强 ✅
**文件位置:** `core/report/ppt_generator.py`

- ✅ 支持多种文件名格式，适配不同项目
- ✅ 集成数据验证功能
- ✅ 改进错误处理和用户提示
- ✅ 自动构建缺失的系谱数据
- ✅ 进度显示集成
- ✅ 模板查找和使用

### 6. 中文字体显示问题修复 ✅

在matplotlib图表生成中添加了跨平台的中文字体支持：

- **macOS**: Arial Unicode MS, STHeiti
- **Windows**: SimHei, Microsoft YaHei
- **Linux**: DejaVu Sans

---

## PPT内容结构

生成的PPT包含以下内容，共23页左右（根据选中的性状数量会有变化）：

### 📄 1. 基础信息（2页）

#### 1.1 标题页
- **标题**: {牧场名称}牧场遗传改良项目专项服务
- **作者**: 奶科院育种中心 + {用户名}
- **日期**: {当前日期}

#### 1.2 目录页
展示4个主要模块：
- 01 牧场系谱记录分析
- 02 牛群遗传数据评估
- 03 牛群体型外貌评定
- 04 牧场公牛使用分析

---

### 📊 2. 牧场系谱记录分析（4页）

#### 2.1 标题分隔页
- 显示"01 牧场系谱记录分析"

#### 2.2 系谱完整性分析 ✅ 自动生成
- **数据源**: `结果-系谱识别情况分析.xlsx`
- **展示内容**:
  - 按出生年份分组的系谱识别率统计表
  - 父号识别率（<90%标红）
  - 外祖父识别率（<70%标红）
  - 外曾外祖父识别率（<50%标红）
- **分析维度**:
  - 按出生年份分组（最近5年）
  - 统计父号、外祖父、外曾外祖父的识别率
  - 区分在场/不在场牛只
- **手动填写**: 未识别原因分析（文本框）

#### 2.3 未识别牛只明细 ⚠️ 需手动填写
- 标注：暂不能自动化生成
- 需要手动整理未识别牛只的详细信息

#### 2.4 系谱记录准确性 ⚠️ 需手动填写
- 基于基因组检测结果
- 需要手动整理系谱准确性验证数据

---

### 📈 3. 牛群遗传数据评估（7+N页，N为选中性状数）

#### 3.1 标题分隔页
- 显示"02 牛群遗传数据评估"

#### 3.2 关键育种性状分析 ✅ 自动生成
- **数据源**: `结果-牛群关键性状年度变化.xlsx`
- **展示内容**:
  - 按出生年份分组的关键性状统计表
  - 包含所有育种性状的中英文对照
  - TPI, NM$, MILK, FAT, PROT, SCS等
- **手动填写**: 需关注的关键性状（文本框）

#### 3.3 净利润值(NM$)分布分析 ✅ 自动生成
- **数据源**: `在群牛只净利润值分布.xlsx` (Sheet: NM$分布)
- **展示内容**:
  - 柱状图：各NM$区间的头数分布
  - 饼图：各区间占比
  - 表格：详细数据
- **手动填写**: 分布情况分析（文本框）

#### 3.4 NM$正态分布分析 ✅ 自动生成
- **数据源**: `NM$_年份正态分布.png`（图片文件）
- **展示内容**:
  - 按年份分组的NM$正态分布曲线
  - 对比最近5年的分布变化
- **手动填写**: 分布情况分析（文本框）

#### 3.5 育种指数正态分布分析 ✅ 自动生成
- **数据源**: `育种指数得分_年份正态分布.png`（图片文件）
- **展示内容**:
  - 按年份分组的育种指数正态分布曲线
  - 显示牛群遗传水平的变化趋势
- **手动填写**: 分布情况分析（文本框）

#### 3.6 关键育种性状进展分析 ✅ 自动生成（N页）
- **数据源**:
  - `selected_traits_key_traits.txt`（选中的性状列表）
  - `结果-牛群关键性状进展图/`文件夹中的PNG图片
- **为每个选中的性状生成一页幻灯片**
- **展示内容**:
  - 性状进展趋势图
  - 历年平均值变化
- **手动填写**: 性状进展情况分析（文本框）

---

### 🐄 4. 牛群体型外貌评定（5页）⚠️ 全部需手动制作

#### 4.1 标题分隔页
- 显示"03 牛群体型外貌评定"

#### 4.2 体型外貌线性评分 ⚠️ 需手动制作
- 线性评分数据整理
- 各体型性状的评分分布

#### 4.3 体型外貌缺陷性状占比 ⚠️ 需手动制作
- 缺陷性状统计
- 占比分析

#### 4.4 缺陷性状具体情况 ⚠️ 需手动制作
- 各缺陷性状的详细情况
- 具体牛只列表

#### 4.5 体型外貌进展情况 ⚠️ 需手动制作
- 体型改良趋势分析
- 年度对比

**说明**: 体型外貌评定部分目前需要手动制作，后续版本将实现自动化。

---

### 🔬 5. 牧场公牛使用分析（5页）

#### 5.1 标题分隔页
- 显示"04 牧场公牛使用分析"

#### 5.2 公牛使用整体情况 ✅ 自动生成
- **数据源**: 配种记录数据
- **展示内容**:
  - 公牛使用统计表
  - 按公牛分组的配种头次统计
  - 性控/常规精液使用情况

#### 5.3 公牛使用明细 ✅ 自动生成（多页）
- **数据源**: 配种记录数据
- **展示内容**:
  - 按年份和冻精类型分组展示
  - 每个公牛的详细使用情况
  - 配种头次、受胎情况等

#### 5.4 公牛使用进展 ✅ 自动生成
- **数据源**: `结果-冻精使用趋势图.xlsx`
- **展示内容**:
  - 公牛性状使用趋势折线图
  - TPI、NM$等性状的年度变化

#### 5.5 公牛使用散点图 ✅ 自动生成
- **展示内容**:
  - 公牛使用分布散点图
  - TPI vs NM$ 分布
  - 可视化公牛质量

#### 5.6 结束页
- 感谢页面

---

## 使用指南

### 前置条件

#### 1. 必要的源数据文件

在生成PPT之前，需要确保以下源数据文件存在于项目的 `analysis_results` 文件夹中：

**必需文件:**
- ✅ `牛只信息.xlsx` - 母牛基本信息
- ✅ `公牛性状数据.xlsx` - 公牛性状评估数据
- ✅ `系谱信息.xlsx` - 牛只系谱信息
- ✅ `母牛性状数据.xlsx` - 母牛性状评估数据

**可选文件:**
- `配种记录.xlsx` - 配种记录数据（生成公牛使用分析需要）
- `育种指数得分.xlsx` - 母牛育种指数计算结果
- `母牛关键性状合并.xlsx` - 合并的母牛关键性状数据
- `selected_traits_key_traits.txt` - 选中的性状列表

#### 2. 数据格式要求

各数据文件必须包含以下关键列：

**牛只信息.xlsx:**
- `cow_id` - 牛只编号
- `birth_date` - 出生日期
- `lac` - 胎次
- `是否在场` - 在场状态（是/否）
- `sex` - 性别

**公牛性状数据.xlsx:**
- `NAAB` - 公牛编号
- `TPI`, `NM$`, `MILK`, `FAT`, `PROT` 等性状值

**系谱信息.xlsx:**
- `cow_id` - 牛只编号
- `sire_id` - 父号
- `dam_id` - 母号
- `birth_year` - 出生年份
- `sire_identified` - 父号识别状态
- `mgs_identified` - 外祖父识别状态

### 使用步骤

#### 方法1：在主程序GUI中使用（推荐）

1. **启动程序并选择项目**
   - 打开遗传改良程序
   - 选择或创建一个项目

2. **准备数据**
   - 确保已上传必要的数据文件
   - 可以通过以下分析功能生成部分数据：
     - 系谱识别情况分析
     - 母牛关键性状计算
     - 母牛育种指数计算

3. **生成PPT**
   - 切换到"生成报告"页面
   - 点击"生成PPT报告"按钮
   - 如果缺少数据，系统会提示是否自动生成

4. **输入牧场名称**
   - 在弹出的对话框中输入牧场名称
   - 这将作为PPT的标题

5. **等待生成完成**
   - 系统会显示进度条
   - 生成完成后会提示是否立即打开查看

6. **查看生成的PPT**
   - PPT保存在：`项目文件夹/analysis_results/牧场名称牧场遗传改良项目专项服务报告.pptx`
   - 可以选择立即打开查看

#### 方法2：程序化使用

```python
from core.report.ppt_generator import PPTGenerator

# 创建PPT生成器
generator = PPTGenerator(
    output_folder="./analysis_results",  # 输出文件夹
    username="张三"                       # 用户名
)

# 设置牧场名称
generator.farm_name = "示例牧场"

# 生成报告（会自动进行数据准备和验证）
success = generator.generate_report()

if success:
    print("PPT生成成功！")
    print(f"文件位置: {generator.output_path}")
else:
    print("PPT生成失败，请检查日志")
```

#### 方法3：带进度回调

```python
from PyQt6.QtWidgets import QProgressDialog

# 创建进度对话框
progress_dialog = QProgressDialog("正在生成PPT...", "取消", 0, 100, parent_widget)

# 创建生成器并传入进度回调
generator = PPTGenerator(
    output_folder="./analysis_results",
    username="张三",
    progress_callback=progress_dialog.setValue  # 进度回调
)

# 生成报告
success = generator.generate_report()
```

---

## 数据依赖

### 生成过程中自动创建的文件

PPT生成器会自动生成以下分析文件（如果不存在）：

#### Excel文件
1. `结果-指数排名结果.xlsx` - 母牛指数排名数据
2. `结果-母牛关键性状指数.xlsx` - 母牛关键性状数据
3. `结果-系谱识别情况分析.xlsx` - 系谱识别率统计
4. `结果-牛群关键性状年度变化.xlsx` - 性状年度变化数据
5. `在群牛只净利润值分布.xlsx` - NM$分布数据
6. `结果-冻精使用趋势图.xlsx` - 冻精使用趋势数据

#### 图片文件
1. `NM$_年份正态分布.png` - NM$正态分布图
2. `育种指数得分_年份正态分布.png` - 育种指数正态分布图
3. `结果-牛群关键性状进展图/*.png` - 各性状进展图

#### 其他文件
1. `selected_traits_key_traits.txt` - 选中的关键性状列表
2. PPT模板文件（可选，如果存在则使用）

### 数据集成关系

```
源数据文件
    ↓
数据适配器（列名映射）
    ↓
数据验证器（完整性检查）
    ↓
数据生成器（分析计算）
    ↓
中间分析文件
    ↓
幻灯片生成器
    ↓
最终PPT文件
```

---

## 自定义配置

### 修改性状翻译

编辑 `config/trait_translations.json` 文件：

```json
{
  "traits": {
    "TPI": "育种综合指数",
    "NM$": "净利润值",
    "MILK": "产奶量",
    "FAT": "乳脂量",
    "PROT": "乳蛋白量",
    "SCS": "体细胞评分",
    "DPR": "女儿受胎率",
    "PL": "生产寿命",
    "PTAT": "综合体型评分",
    "UDC": "乳房综合评分",
    "FLC": "肢蹄综合评分"
    // 添加或修改更多性状翻译
  }
}
```

### 修改识别率阈值

在同一配置文件中：

```json
{
  "thresholds": {
    "父号识别率": {
      "warning": 90.0,  // 低于此值显示红色警告
      "unit": "%"
    },
    "外祖父识别率": {
      "warning": 70.0,
      "unit": "%"
    },
    "外曾外祖父识别率": {
      "warning": 50.0,
      "unit": "%"
    }
  }
}
```

### 使用自定义PPT模板

1. **准备模板文件**
   - 创建一个PowerPoint模板（.pptx）
   - 设计好样式、背景、字体等
   - 文件名中包含"template"关键字

2. **放置模板**
   - 将模板文件放在输出文件夹中
   - 例如：`my_custom_template.pptx`

3. **自动使用**
   - 系统会自动查找并使用该模板
   - 如果找不到模板，会创建空白PPT

---

## 技术实现

### 数据生成函数详解

#### 1. 系谱识别情况分析
```python
def generate_pedigree_identification_analysis(table_c, cow_df):
    """
    功能：分析牛群系谱识别率

    输入：
        - table_c: 系谱信息表（包含牛只系谱信息）
        - cow_df: 牛只基本信息（包含出生日期、在场状态等）

    输出：
        - 结果-系谱识别情况分析.xlsx

    分析维度：
        - 按出生年份分组（最近5年）
        - 统计父号、外祖父、外曾外祖父的识别率
        - 区分在场/不在场牛只

    计算方法：
        识别率 = 已识别数量 / 总数量 × 100%
    """
```

#### 2. 母牛关键性状计算
```python
def calculate_key_traits_index(cow_df, bull_traits):
    """
    功能：计算母牛各项育种性状指数

    输入：
        - cow_df: 牛只信息
        - bull_traits: 公牛性状数据

    输出：
        - 结果-母牛关键性状指数.xlsx
        - 结果-牛群关键性状年度变化.xlsx
        - 正态分布图片文件

    计算方法：
        1. 根据系谱信息追溯公牛性状
        2. 计算母牛的遗传预测值
        3. 生成年度统计
    """
```

#### 3. 正态分布图生成
```python
def generate_normal_distribution_charts(df, value_column, file_prefix):
    """
    功能：生成性状值的正态分布图

    参数：
        - df: 数据框
        - value_column: 要分析的值列（如"NM$"或"育种指数得分"）
        - file_prefix: 文件前缀

    输出：
        - {file_prefix}_年份正态分布.png
        - {file_prefix}_胎次正态分布.png
        - 对应的Excel数据文件

    分组方式：
        - 年份分组：最近5年
        - 胎次分组：成母牛/后备牛

    绘图元素：
        - 正态分布曲线（拟合）
        - 实际数据直方图
        - 均值线、标准差区间
    """
```

### 数据适配器工作原理

```python
class DataAdapter:
    """
    数据适配器：处理不同项目中的列名差异
    """

    # 列名映射表
    COLUMN_MAPPINGS = {
        'cow_id': ['cow_id', '牛号', '牛只编号', 'ID'],
        'birth_date': ['birth_date', '出生日期', '生日'],
        'lac': ['lac', '胎次', '胎数', 'parity'],
        'sire_id': ['sire_id', '父号', '父亲编号'],
        'dam_id': ['dam_id', '母号', '母亲编号']
    }

    def adapt_dataframe(self, df, data_type):
        """
        自动映射列名

        工作流程：
        1. 检测现有列名
        2. 查找映射表
        3. 重命名列
        4. 添加缺失列
        5. 转换数据类型
        """
        pass
```

### 数据验证器规则

```python
VALIDATION_RULES = {
    'cow_data': {
        'required_columns': ['cow_id', 'birth_date', 'lac'],
        'data_types': {
            'birth_date': 'datetime',
            'lac': 'int',
            'milk_yield': 'float'
        },
        'value_ranges': {
            'lac': (0, 15),           # 胎次范围 0-15
            'milk_yield': (0, 100)    # 产奶量范围 0-100吨
        },
        'enum_values': {
            '是否在场': ['是', '否'],
            'sex': ['母', 'F', 'female']
        },
        'business_rules': [
            # 自定义业务规则
            'birth_date不能晚于今天',
            '在场牛只必须有最近的产奶记录'
        ]
    }
}
```

---

## 开发说明

### 添加新的幻灯片

#### 步骤1：创建幻灯片生成器类

在 `core/report/slide_generators/` 中创建新文件：

```python
# my_new_slide.py
from .base import BaseSlideGenerator

class MyNewSlideGenerator(BaseSlideGenerator):
    """新的幻灯片生成器"""

    def generate_all_slides(self):
        """生成所有幻灯片"""
        # 1. 生成标题分隔页
        self.create_title_slide()

        # 2. 生成内容页
        self.create_content_slide()

    def create_title_slide(self):
        """创建标题页"""
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[5])
        title = slide.shapes.title
        title.text = "05 我的新分析"

    def create_content_slide(self):
        """创建内容页"""
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[5])

        # 添加标题
        title = slide.shapes.title
        title.text = "详细分析内容"

        # 添加表格
        self.add_table_to_slide(slide, data)

        # 添加图片
        self.add_image_to_slide(slide, image_path)
```

#### 步骤2：在主生成器中调用

修改 `core/report/ppt_generator.py`:

```python
# 导入新的生成器
from .slide_generators.my_new_slide import MyNewSlideGenerator

# 在生成流程中添加
def generate_ppt(self):
    # ... 其他生成器 ...

    # 添加新的幻灯片
    my_generator = MyNewSlideGenerator(self.prs, self.output_folder)
    my_generator.generate_all_slides()
```

### 添加新的数据源

#### 步骤1：定义数据文件

在 `core/report/data_preparation.py` 中添加：

```python
class DataPreparation:
    # 添加新的文件定义
    FILES = {
        # ... 现有文件 ...
        'my_new_analysis': '结果-我的新分析.xlsx'
    }

    def check_my_new_analysis(self):
        """检查新分析文件是否存在"""
        file_path = self.output_folder / self.FILES['my_new_analysis']
        if not file_path.exists():
            # 如果不存在，生成它
            self.generate_my_new_analysis()
```

#### 步骤2：实现数据生成方法

在 `core/report/data_generator.py` 中添加：

```python
def generate_my_new_analysis(self, cow_df, other_data):
    """
    生成新的分析数据

    参数：
        cow_df: 母牛数据
        other_data: 其他必需数据

    返回：
        生成的文件路径
    """
    # 1. 数据处理
    analysis_data = process_data(cow_df, other_data)

    # 2. 保存到Excel
    output_path = self.output_folder / '结果-我的新分析.xlsx'
    analysis_data.to_excel(output_path, index=False)

    return output_path
```

#### 步骤3：在验证中使用

```python
# 在数据验证器中添加规则
VALIDATION_RULES['my_new_analysis'] = {
    'required_columns': ['column1', 'column2'],
    'data_types': {'column1': 'int'},
    # ... 其他规则
}
```

---

## 常见问题

### Q1: 提示缺少数据文件怎么办？

**A:** 有三种解决方案：

1. **自动生成（推荐）**
   - 在提示时选择"是"让系统自动生成
   - 系统会根据源数据自动计算生成分析文件

2. **手动准备**
   - 根据提示查看缺少哪些文件
   - 手动准备相应的Excel文件
   - 确保文件格式符合要求

3. **运行分析功能**
   - 通过主程序的分析功能生成
   - 例如：系谱识别分析、母牛关键性状计算等

### Q2: 生成的PPT中有些页面显示"需手动整理"？

**A:** 这些内容目前需要手动制作：

- **未识别牛只明细** - 需要整理具体的未识别牛只列表
- **系谱记录准确性分析** - 需要基因组检测结果
- **体型外貌评定全部内容** - 需要体型评分数据
- **各部分的分析文本** - 可以使用自动生成的文本，或手动编辑

**后续版本将逐步实现这些部分的自动化。**

### Q3: 如何使用自定义PPT模板？

**A:**

1. 准备PowerPoint模板文件（.pptx）
2. 文件名中包含"template"关键字（如`my_template.pptx`）
3. 将模板文件放在输出文件夹（analysis_results）中
4. 系统会自动识别并使用该模板

**模板要求：**
- 模板会被复制，不会修改原模板
- 系统会在模板基础上添加幻灯片
- 确保模板中有足够的幻灯片布局

### Q4: 图表中的中文显示为方块？

**A:** 这是字体问题，解决方法：

- **Windows**:
  - 确保安装了SimHei或微软雅黑字体
  - 一般Windows系统已自带

- **macOS**:
  - 系统已自动配置Arial Unicode MS
  - 无需额外操作

- **Linux**:
  - 需要安装中文字体包
  - Ubuntu: `sudo apt-get install fonts-wqy-microhei`
  - CentOS: `sudo yum install wqy-microhei-fonts`

### Q5: 生成速度很慢？

**A:** PPT生成涉及大量数据处理和图表生成，以下方法可以提升速度：

1. **减少选中的性状数量**
   - 每个性状都会生成一页幻灯片
   - 只选择需要重点关注的性状

2. **确保数据文件不要过大**
   - 移除不必要的历史数据
   - 只保留分析需要的列

3. **关闭其他占用资源的程序**
   - 特别是Office软件
   - 释放内存和CPU资源

4. **使用SSD硬盘**
   - 提升文件读写速度

### Q6: 数据验证报告显示警告，是否继续？

**A:** 根据警告类型决定：

- **缺少可选列**: 可以继续，但部分分析可能不完整
- **数据范围异常**: 建议检查数据，可能是数据错误
- **日期格式问题**: 建议修正，以确保统计准确
- **缺少必需列**: 必须修正，否则无法生成

**建议：**
- 仔细阅读验证报告
- 修正明显的数据错误
- 对于不影响主要分析的警告，可以忽略

### Q7: 如何修改生成的PPT样式？

**A:** 有两种方法：

1. **使用自定义模板**（推荐）
   - 在模板中预设样式
   - 生成的PPT会继承模板样式

2. **修改代码中的样式配置**
   - 编辑 `slide_generators/base.py`
   - 修改 `TABLE_STYLE`, `FONT_STYLE` 等常量
   ```python
   TABLE_STYLE = {
       'font_name': '微软雅黑',
       'font_size': Pt(10),
       'header_fill': RGBColor(68, 114, 196)
   }
   ```

### Q8: 生成的PPT文件在哪里？

**A:** PPT保存位置：

- **默认位置**: `项目文件夹/analysis_results/`
- **文件名格式**: `{牧场名称}牧场遗传改良项目专项服务报告.pptx`
- **示例**: `示例牧场牧场遗传改良项目专项服务报告.pptx`

### Q9: 如何批量生成多个牧场的PPT？

**A:** 程序化方式批量生成：

```python
from core.report.ppt_generator import PPTGenerator

farms = [
    {'name': '牧场A', 'folder': './projects/farm_a/analysis_results'},
    {'name': '牧场B', 'folder': './projects/farm_b/analysis_results'},
    {'name': '牧场C', 'folder': './projects/farm_c/analysis_results'}
]

for farm in farms:
    generator = PPTGenerator(
        output_folder=farm['folder'],
        username="服务人员"
    )
    generator.farm_name = farm['name']
    success = generator.generate_report()

    if success:
        print(f"{farm['name']} PPT生成成功")
    else:
        print(f"{farm['name']} PPT生成失败")
```

### Q10: 数据验证失败，如何查看详细错误？

**A:**

1. **查看生成的验证报告**
   - 位置：`analysis_results/data_validation_report.txt`
   - 包含详细的验证结果和错误信息

2. **查看日志文件**
   - 位置：程序运行目录的日志文件
   - 包含更详细的调试信息

3. **在代码中打印验证结果**
   ```python
   from core.report.data_validator import DataValidator

   validator = DataValidator()
   is_valid, errors = validator.validate_dataframe(df, 'cow_data')

   if not is_valid:
       print("验证错误：")
       for error in errors:
           print(f"  - {error}")
   ```

---

## 后续改进计划

### 短期计划（1-2周）

#### 1. 完善主程序集成
- ✅ 优化数据准备的自动触发机制
- ✅ 改进进度显示（更详细的步骤提示）
- ✅ 添加取消功能
- ✅ 优化错误提示信息

#### 2. 数据验证增强
- ⏳ 添加更多的业务规则验证
- ⏳ 支持数据修复建议
- ⏳ 生成可交互的验证报告

#### 3. 用户体验优化
- ⏳ 添加PPT预览功能
- ⏳ 支持选择要包含的章节
- ⏳ 优化文件命名规则

### 中期计划（1个月）

#### 1. 体型评定自动化 ⭐ 重要
- ⏳ 读取体型外貌评分数据
- ⏳ 自动生成体型分析
- ⏳ 生成体型进展图表
- ⏳ 实现缺陷性状分析

#### 2. 分析文本智能生成
- ⏳ AI辅助生成分析文本
- ⏳ 基于数据自动总结要点
- ⏳ 支持多种分析角度
- ⏳ 允许用户编辑和保存模板

#### 3. 模板系统完善
- ⏳ 支持多个预设模板
- ⏳ 模板管理界面
- ⏳ 模板预览功能
- ⏳ 模板导入导出

#### 4. 批量生成功能
- ⏳ 支持多牧场批量生成
- ⏳ 生成任务队列管理
- ⏳ 批量生成进度监控
- ⏳ 批量生成报告汇总

### 长期计划（2-3个月）

#### 1. 交互式PPT编辑
- ⏳ 在主程序中预览PPT
- ⏳ 实时编辑幻灯片内容
- ⏳ 拖拽调整图表
- ⏳ 快速导出PDF

#### 2. 多语言支持
- ⏳ 英文版PPT生成
- ⏳ 性状名称多语言配置
- ⏳ 分析文本多语言模板

#### 3. 云端协作
- ⏳ PPT在线编辑
- ⏳ 团队协作功能
- ⏳ 版本管理
- ⏳ 评论和审批流程

#### 4. 高级可视化
- ⏳ 3D图表支持
- ⏳ 交互式图表
- ⏳ 动画效果
- ⏳ 数据钻取功能

---

## 技术支持

### 遇到问题时的检查清单

1. **检查日志文件**
   - 查看详细错误信息
   - 定位问题所在模块

2. **检查数据文件**
   - 确保文件格式正确
   - 验证必需列是否存在
   - 检查数据类型是否正确

3. **检查文件权限**
   - 确保有读取源数据的权限
   - 确保有写入输出文件夹的权限

4. **查看数据验证报告**
   - 位置：`analysis_results/data_validation_report.txt`
   - 根据报告修正数据问题

### 联系技术支持

如果以上方法无法解决问题，请联系技术支持团队：

- **Email**: support@example.com
- **电话**: xxx-xxxx-xxxx
- **技术文档**: 查看完整的开发文档

**提供以下信息以便快速解决问题：**
- 错误信息截图
- 日志文件
- 数据验证报告
- 使用的版本号

---

## 附录

### A. 性状中英文对照表（完整版）

| 英文缩写 | 中文名称 | 说明 |
|---------|---------|------|
| TPI | 育种综合指数 | Total Performance Index |
| NM$ | 净利润值 | Net Merit |
| CM$ | 奶酪价值 | Cheese Merit |
| FM$ | 液态奶价值 | Fluid Merit |
| GM$ | 放牧价值 | Grazing Merit |
| MILK | 产奶量 | Milk yield |
| FAT | 乳脂量 | Fat yield |
| PROT | 乳蛋白量 | Protein yield |
| SCS | 体细胞评分 | Somatic Cell Score |
| PL | 生产寿命 | Productive Life |
| DPR | 女儿受胎率 | Daughter Pregnancy Rate |
| HCR | 母牛受胎率 | Heifer Conception Rate |
| CCR | 母牛受胎率 | Cow Conception Rate |
| PTAT | 综合体型评分 | Type |
| UDC | 乳房综合评分 | Udder Composite |
| FLC | 肢蹄综合评分 | Feet & Legs Composite |

### B. 文件命名规范

| 文件类型 | 命名格式 | 示例 |
|---------|---------|------|
| PPT报告 | {牧场名称}牧场遗传改良项目专项服务报告.pptx | 示例牧场牧场遗传改良项目专项服务报告.pptx |
| 系谱分析 | 结果-系谱识别情况分析.xlsx | - |
| 性状数据 | 结果-母牛关键性状指数.xlsx | - |
| 分布图 | NM$_年份正态分布.png | - |
| 进展图 | {性状名}_进展情况.png | TPI_进展情况.png |

### C. 数据格式示例

详见各数据文件的使用说明。

---

**文档维护:**
- **创建时间:** 2025-11-02
- **最后更新:** 2025-11-02
- **维护人员:** 开发团队
- **版本:** v1.0

**相关文档:**
- [Excel报告生成指南](Excel报告生成指南.md)
- [选配功能说明](选配功能说明.md)
- [数据上传指南](数据上传指南.md)
