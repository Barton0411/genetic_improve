# 奶牛育种智选报告专家系统 (Genetic Improve)

## 项目概述

这是一个专业的奶牛育种分析与决策支持系统，旨在帮助奶牛养殖户和育种专家进行科学的育种决策。系统集成了基因组评估、近交系数分析、性状计算、个体选配和报告生成等功能，为奶牛育种提供了全方位的解决方案。该系统基于先进的生物统计学方法和大数据分析技术，可显著提高育种效率和质量。

## 主要功能

### 已实现功能

#### 育种项目管理
- **项目创建与导入**：支持创建新项目或导入已有项目，便于管理多个育种群体
- **数据组织**：以项目为单位组织和存储所有相关数据，包括牛只信息、系谱、性状数据等
- **项目版本控制**：支持项目的备份和恢复，确保数据安全
- **权限管理**：多级用户权限设置，保障数据安全和隐私

#### 数据上传
- **多源数据导入**：支持Excel、CSV、XML等多种格式的数据导入
- **拖拽上传**：便捷的拖拽式文件上传界面
- **数据标准化**：自动标准化处理上传的奶牛数据，包括：
  - 母牛基础数据（生产记录、系谱信息）
  - 公牛数据（育种值、系谱、基因组评估值）
  - 繁殖数据（配种记录、妊娠检查、分娩记录）
  - 体型鉴定数据
- **数据验证**：上传过程中自动检查数据完整性和合规性，提示异常数据

#### 关键育种性状分析
- **母牛性状分析**：
  - 产奶性能评估（产奶量、乳脂率、乳蛋白率等）
  - 繁殖性能分析（产犊间隔、受胎率等）
  - 健康性状评估（体细胞计数、疾病抵抗力等）
  - 长寿性分析
  - 群体遗传趋势可视化
  
- **公牛性状分析**：
  - 遗传育种值评估
  - 基因组评估值分析
  - 后代测试结果分析
  - 公牛性状传递能力预测
  - 优势公牛筛选

- **配种公牛性状分析**：
  - 配种组合优化
  - 性状互补分析
  - 期望改良效果预测
  - 历史配种结果评估

#### 牛只指数计算排名
- **综合育种指数计算**：根据国家或地区的育种目标，计算个体的综合育种价值
- **自定义指数设置**：支持用户自定义权重，构建符合特定育种目标的指数体系
- **多维度排名**：支持按不同性状或指数进行排名
- **排名可视化**：直观展示排名结果，支持图表导出
- **遗传趋势分析**：评估群体在特定指数上的遗传进展

#### 近交系数及隐性基因分析
- **血统近交系数计算**：
  - Wright系数计算
  - 群体平均近交系数趋势分析
  - 近交情况警示与分级
  
- **路径近交系数分析**：
  - 近交路径追踪与可视化
  - 主要贡献者识别
  - 关键祖先分析
  
- **家系可视化**：
  - 交互式家系图生成
  - 多代系谱展示
  - 关键个体标记
  - 导出高分辨率家系图片
  
- **隐性遗传病风险评估**：
  - 主要隐性遗传病携带风险计算
  - 群体风险状况评估
  - 基因型频率分析
  - 风险警示系统

### 待开发功能

#### 体型外貌鉴定分析
- **体型测量数据处理**：自动处理和标准化体型测量数据
- **线性评分分析**：分析评分结果，计算体型综合指数
- **体型与生产性能关联分析**：研究体型特征与生产性能的关系
- **体型评分可视化**：直观展示体型评分结果
- **体型趋势分析**：评估群体体型特征的变化趋势

#### 个体选配
- **智能配种建议**：基于遗传多样性、性状互补性原则推荐最优配种组合
- **避免近交配种**：自动识别和规避近亲配种风险
- **性状定向改良**：针对特定育种目标优化配种方案
- **群体结构优化**：保持群体遗传多样性的同时提高遗传进展
- **批量配种规划**：支持整个群体的配种规划

#### 报告自动化生成
- **API集成**：连接外部评价API，自动获取最新育种数据和评价结果
- **数据智能分析**：自动分析育种数据，识别关键趋势和问题
- **多格式报告生成**：支持生成PDF、PowerPoint等多种格式的专业报告
- **自定义报告模板**：允许用户定制报告模板和内容
- **周期性报告自动生成**：设定周期自动生成群体评估报告

## 系统要求

- **操作系统**：Windows 10/11
- **处理器**：推荐Intel Core i5或更高，或同等性能的AMD处理器
- **内存**：最低8GB，推荐16GB或更高（处理大型数据集时）
- **存储空间**：至少5GB可用空间（数据库可能需要更多空间）
- **显示器**：最低1366×768分辨率，推荐1920×1080或更高
- **Python版本**：3.9+
- **主要依赖**：
  - PyQt6：用户界面框架
  - SQLAlchemy：数据库ORM支持
  - Pandas：数据处理和分析
  - NetworkX：家系关系图分析
  - Matplotlib：数据可视化
  - OpenCV：视频处理（启动画面）
  - NumPy：科学计算
  - OpenPyXL/xlrd：Excel文件处理

## 安装与使用

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动应用

```bash
python main.py
```

### 基本使用流程

1. **登录系统**：使用用户名和密码登录系统
2. **项目管理**：创建新的育种项目或选择已有项目
3. **数据上传**：上传母牛、公牛、繁殖等数据，系统会自动进行标准化处理
4. **性状分析**：选择相应功能模块进行性状分析和指数计算
5. **近交分析**：利用近交系数分析工具评估近交风险
6. **结果分析**：通过可视化图表分析结果
7. **数据导出**：将分析结果导出为Excel或其他格式

## 项目结构

```
genetic_improve/
├── core/                 # 核心功能模块
│   ├── ai_evaluation/    # AI评估模块
│   ├── breeding_calc/    # 育种计算核心
│   ├── data/             # 数据处理模块
│   ├── inbreeding/       # 近交分析模块
│   ├── matching/         # 个体选配模块
│   └── reporting/        # 报告生成模块
├── config/               # 配置文件
├── gui/                  # 图形用户界面
│   └── resources/        # 界面资源文件
├── utils/                # 工具函数
├── templates/            # 模板文件
├── main.py               # 程序入口
└── requirements.txt      # 依赖项
```

## 开发计划

1. **近期（2023年Q4-2024年Q1）**：
   - 完善体型外貌鉴定分析功能
   - 提高近交分析算法精度
   - 优化用户界面，提升用户体验

2. **中期（2024年Q2-Q3）**：
   - 开发个体选配模块，实现智能化推荐
   - 增强数据处理能力，支持更大规模数据
   - 扩展数据导入格式支持

3. **远期（2024年Q4及以后）**：
   - 集成API服务，实现报告自动化生成
   - 开发移动端应用，支持随时查看数据
   - 构建云端服务，实现数据与分析结果共享

## 技术特点

- **易用性**：直观的用户界面，拖放上传，可视化结果展示，降低使用门槛
- **精确性**：采用科学的计算方法，参考国际先进育种理论，确保分析结果的准确性
- **高效性**：优化的算法和数据结构，提高大规模数据处理效率，支持批量操作
- **扩展性**：模块化设计，便于功能扩展和定制，可根据用户需求进行个性化配置
- **安全性**：多层次数据保护机制，确保育种数据安全和隐私

## 注意事项

- 首次使用时需要建立本地数据库，这可能需要一些时间，建议按照向导一步步完成
- 对于大型育种场的数据分析（超过10,000头牛的数据），建议使用配置较高的计算机
- 定期备份项目数据，避免数据丢失
- 系统更新前请务必备份当前数据
- 对于特殊的育种需求，可联系开发团队定制功能

## 技术支持

对于系统使用过程中遇到的问题，可通过以下方式获取支持：
- 系统内置帮助文档
- 技术支持邮箱：support@genetic-improve.com
- 电话支持：400-XXX-XXXX（工作日9:00-17:00）

## 开发者

该项目由牧科动保育种研发团队开发和维护。如有问题或建议，请联系系统管理员。

---

# Dairy Cattle Breeding Selection and Report System (Genetic Improve)

## Project Overview

This is a professional dairy cattle breeding analysis and decision support system designed to help dairy farmers and breeding experts make scientific breeding decisions. The system integrates genomic evaluation, inbreeding coefficient analysis, trait calculation, individual matching, and report generation functions, providing a comprehensive solution for dairy cattle breeding. The system is based on advanced biostatistical methods and big data analysis technology, which can significantly improve breeding efficiency and quality.

## Main Features

### Implemented Features

#### Breeding Project Management
- **Project Creation and Import**: Support for creating new projects or importing existing projects for managing multiple breeding populations
- **Data Organization**: Organize and store all relevant data by project, including animal information, pedigree, and trait data
- **Project Version Control**: Support for project backup and recovery to ensure data security
- **Permission Management**: Multi-level user permission settings to ensure data security and privacy

#### Data Upload
- **Multi-source Data Import**: Support for importing data in multiple formats including Excel, CSV, XML, etc.
- **Drag-and-drop Upload**: Convenient drag-and-drop file upload interface
- **Data Standardization**: Automatic standardization of uploaded dairy cattle data, including:
  - Cow basic data (production records, pedigree information)
  - Bull data (breeding values, pedigree, genomic evaluation values)
  - Breeding data (mating records, pregnancy checks, calving records)
  - Conformation evaluation data
- **Data Validation**: Automatic checking of data integrity and compliance during upload, prompting abnormal data

#### Key Breeding Trait Analysis
- **Cow Trait Analysis**:
  - Milk production performance evaluation (milk yield, fat percentage, protein percentage, etc.)
  - Reproductive performance analysis (calving interval, conception rate, etc.)
  - Health trait assessment (somatic cell count, disease resistance, etc.)
  - Longevity analysis
  - Population genetic trend visualization
  
- **Bull Trait Analysis**:
  - Genetic breeding value evaluation
  - Genomic evaluation value analysis
  - Progeny testing result analysis
  - Bull trait transmission ability prediction
  - Superior bull screening

- **Mating Bull Trait Analysis**:
  - Mating combination optimization
  - Trait complementarity analysis
  - Expected improvement effect prediction
  - Historical mating result evaluation

#### Animal Index Calculation and Ranking
- **Comprehensive Breeding Index Calculation**: Calculate individual comprehensive breeding value based on national or regional breeding objectives
- **Custom Index Settings**: Support for user-defined weights to build an index system that meets specific breeding objectives
- **Multi-dimensional Ranking**: Support for ranking by different traits or indices
- **Ranking Visualization**: Intuitive display of ranking results, support for chart export
- **Genetic Trend Analysis**: Evaluate genetic progress of the population on specific indices

#### Inbreeding Coefficient and Recessive Gene Analysis
- **Pedigree Inbreeding Coefficient Calculation**:
  - Wright coefficient calculation
  - Population average inbreeding coefficient trend analysis
  - Inbreeding warning and classification
  
- **Path Inbreeding Coefficient Analysis**:
  - Inbreeding path tracking and visualization
  - Major contributor identification
  - Key ancestor analysis
  
- **Pedigree Visualization**:
  - Interactive pedigree chart generation
  - Multi-generation pedigree display
  - Key individual marking
  - Export high-resolution pedigree images
  
- **Recessive Genetic Disease Risk Assessment**:
  - Calculation of major recessive genetic disease carrier risk
  - Population risk status assessment
  - Genotype frequency analysis
  - Risk warning system

### Features Under Development

#### Conformation Evaluation Analysis
- **Conformation Measurement Data Processing**: Automatically process and standardize conformation measurement data
- **Linear Scoring Analysis**: Analyze scoring results and calculate comprehensive conformation index
- **Conformation and Production Performance Correlation Analysis**: Study the relationship between conformation traits and production performance
- **Conformation Score Visualization**: Intuitive display of conformation scoring results
- **Conformation Trend Analysis**: Evaluate changes in population conformation characteristics

#### Individual Mating
- **Intelligent Mating Recommendations**: Recommend optimal mating combinations based on genetic diversity and trait complementarity principles
- **Inbreeding Avoidance**: Automatically identify and avoid risks of inbreeding
- **Trait-oriented Improvement**: Optimize mating plans for specific breeding objectives
- **Population Structure Optimization**: Maintain population genetic diversity while improving genetic progress
- **Batch Mating Planning**: Support mating planning for the entire population

#### Automated Report Generation
- **API Integration**: Connect to external evaluation APIs to automatically obtain the latest breeding data and evaluation results
- **Intelligent Data Analysis**: Automatically analyze breeding data to identify key trends and issues
- **Multi-format Report Generation**: Support generating professional reports in multiple formats such as PDF, PowerPoint, etc.
- **Custom Report Templates**: Allow users to customize report templates and content
- **Periodic Report Auto-generation**: Set up automatic generation of population assessment reports periodically

## System Requirements

- **Operating System**: Windows 10/11
- **Processor**: Recommended Intel Core i5 or higher, or equivalent AMD processor
- **Memory**: Minimum 8GB, recommended 16GB or higher (for processing large datasets)
- **Storage Space**: At least 5GB of available space (database may require more space)
- **Display**: Minimum 1366×768 resolution, recommended 1920×1080 or higher
- **Python Version**: 3.9+
- **Main Dependencies**:
  - PyQt6: UI framework
  - SQLAlchemy: Database ORM support
  - Pandas: Data processing and analysis
  - NetworkX: Pedigree relationship graph analysis
  - Matplotlib: Data visualization
  - OpenCV: Video processing (splash screen)
  - NumPy: Scientific computing
  - OpenPyXL/xlrd: Excel file processing

## Installation and Usage

### Installing Dependencies

```bash
pip install -r requirements.txt
```

### Starting the Application

```bash
python main.py
```

### Basic Workflow

1. **System Login**: Log in to the system using username and password
2. **Project Management**: Create a new breeding project or select an existing one
3. **Data Upload**: Upload cow, bull, breeding data, etc., which will be automatically standardized by the system
4. **Trait Analysis**: Select the appropriate functional module for trait analysis and index calculation
5. **Inbreeding Analysis**: Use inbreeding coefficient analysis tools to assess inbreeding risk
6. **Result Analysis**: Analyze results through visualization charts
7. **Data Export**: Export analysis results to Excel or other formats

## Project Structure

```
genetic_improve/
├── core/                 # Core functional modules
│   ├── ai_evaluation/    # AI evaluation module
│   ├── breeding_calc/    # Breeding calculation core
│   ├── data/             # Data processing module
│   ├── inbreeding/       # Inbreeding analysis module
│   ├── matching/         # Individual matching module
│   └── reporting/        # Report generation module
├── config/               # Configuration files
├── gui/                  # Graphical user interface
│   └── resources/        # Interface resources
├── utils/                # Utility functions
├── templates/            # Template files
├── main.py               # Program entry
└── requirements.txt      # Dependencies
```

## Development Plan

1. **Short-term (Q4 2023-Q1 2024)**:
   - Improve conformation evaluation analysis functionality
   - Enhance inbreeding analysis algorithm accuracy
   - Optimize user interface to improve user experience

2. **Medium-term (Q2-Q3 2024)**:
   - Develop individual matching module for intelligent recommendations
   - Enhance data processing capabilities to support larger scale data
   - Expand support for data import formats

3. **Long-term (Q4 2024 and beyond)**:
   - Integrate API services for automated report generation
   - Develop mobile applications for anytime data access
   - Build cloud services for sharing data and analysis results

## Technical Features

- **Usability**: Intuitive user interface, drag-and-drop upload, visualized result display, lowering usage threshold
- **Accuracy**: Scientific calculation methods, referencing international advanced breeding theories, ensuring the accuracy of analysis results
- **Efficiency**: Optimized algorithms and data structures, improving large-scale data processing efficiency, supporting batch operations
- **Extensibility**: Modular design, facilitating function extension and customization, can be personalized according to user needs
- **Security**: Multi-layered data protection mechanisms ensuring breeding data security and privacy

## Notes

- Initial database setup may take some time when first using the system, it is recommended to follow the wizard step by step
- For large breeding farm data analysis (data for more than 10,000 cattle), a higher configuration computer is recommended
- Regularly backup project data to avoid data loss
- Always backup current data before system updates
- For special breeding needs, contact the development team for customized functions

## Technical Support

For issues encountered during system use, support can be obtained through the following channels:
- Built-in help documentation
- Technical support email: support@genetic-improve.com
- Phone support: 400-XXX-XXXX (workdays 9:00-17:00)

## Developers

This project is developed and maintained by the Muoke Animal Health Breeding R&D Team. For questions or suggestions, please contact the system administrator. 
