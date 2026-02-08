# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 需求记录规则

每当用户提出新需求时，将需求记录到 `docs/` 目录下对应的文档中：
- 新功能/重构需求 → 创建或更新相关的需求文档
- 如果没有对应文档，创建新的 markdown 文件记录

## 项目概述

伊利奶牛选配系统 - 基于 PyQt6 的桌面应用，用于牛群数据管理、育种分析和个体选配计算。支持多数据源（伊起牛、慧牧云、优源-DC305）自动识别和标准化。

## 常用命令

```bash
# 运行应用
python main.py

# 语法检查
python -m py_compile <file.py>

# 打包 Mac 版本
pyinstaller GeneticImprove.spec

# 打包 Windows 版本
pyinstaller GeneticImprove_win.spec
```

注意：项目没有正式的测试框架或测试套件。`scripts/` 下有手动测试脚本。

## 版本管理

- 版本号格式：`主版本号.次版本号.修订号.构建号`（如 1.2.2.7）
- 版本定义在 `version.py` 的 `VERSION` 变量和 `VERSION_HISTORY` 列表
- 发布时使用 `/release` 斜杠命令或直接说"发布 vX.X.X.X"
- 发布流程详见 `docs/版本发布提示词模板.md`，文档更新规则详见 `docs/文档维护规则.md`

## CI/CD

- GitHub Actions 工作流：`.github/workflows/build-releases.yml`
- 触发条件：推送 `v*.*.*` 格式的 Git 标签
- 产物：Windows (OneDir) + macOS (.app/DMG)
- 构建使用 Python 3.9 + PyInstaller

## 核心架构

### 分层结构

```
gui/                  # PyQt6 界面层
  ├─ main_window.py   # 主窗口（核心UI入口，超大文件）
  ├─ farm_selection_page.py  # 牧场选择（数据导入入口）
  ├─ *_dialog.py      # 各种对话框
  └─ *_worker.py      # 后台工作线程（QThread）

core/                 # 业务逻辑层
  ├─ data/            # 数据处理（processor.py, uploader.py）
  ├─ breeding_calc/   # 育种计算（性状、指数）
  ├─ matching/        # 个体选配算法（最复杂模块）
  ├─ inbreeding/      # 近交系数计算（Wright通径法）
  ├─ grouping/        # 分组管理
  ├─ excel_report/    # Excel报告生成（20个Sheet）
  └─ ppt_report/      # PPT报告生成（基于模板填充）

api/                  # API客户端层
  ├─ api_client.py    # 主API通信（认证、数据、版本）
  └─ yqn_api_client.py # 伊起牛平台API

auth/                 # 认证层（JWT + 离线备用）
config/               # 配置管理
utils/                # 工具函数
```

### 关键数据流

1. **数据导入**: `gui/farm_selection_page.py` → `core/data/processor.py` → 标准化Excel
2. **多数据源**: processor.py 自动识别数据源（伊起牛/慧牧云/DC305）并应用对应的字段映射
3. **性状计算**: `core/breeding_calc/traits_calculation.py` → `index_calculation.py`
4. **个体选配**: `core/matching/complete_mating_executor.py` → `cycle_based_matcher.py`
5. **报告生成**: `core/excel_report/generator.py` 或 `core/ppt_report/generator.py`

### 多线程模式

UI线程只处理界面交互，所有耗时操作通过 Worker 线程执行。Worker 通过 `pyqtSignal` 与 UI 通信：
- `progress.emit(percent)` - 进度更新
- `finished.emit(result)` - 完成通知
- `error.emit(error_msg)` - 错误通知

### 个体选配 (core/matching/)

最复杂的核心模块：
- `cycle_based_matcher.py` - **当前主分配器**，基于周期和库存比例分配
- `matrix_recommendation_generator.py` - 推荐矩阵生成，计算所有母牛×公牛配对得分
- `complete_mating_executor.py` - 完整选配流程编排
- `allocation_utils.py` - 分配工具函数
- 已废弃：`individual_matcher.py`、`matching_worker.py`、`recommendation_generator.py`

关键参数：默认近交系数阈值 3.125%，支持成母牛/后备牛各三个分组（A/B/C）。

### 数据处理 (core/data/)

- `processor.py`（约97KB）- 核心数据标准化引擎
  - NAAB号格式化：去除XK/SEX/性控前后缀，品种码转换，站号补齐
  - 多选牧场时，牛号添加站号前缀避免重号
- `yqn_data_converter.py` - 伊起牛API数据 → 标准Excel格式
- `bull_library_downloader.py` - 公牛库从阿里云OSS下载（132MB，支持断点续传）

## 网络请求规范

所有 HTTP 请求必须禁用代理直连：

```python
session = requests.Session()
session.trust_env = False  # 不使用环境变量中的代理
session.proxies = {'http': None, 'https': None}
response = session.request(method, url, **kwargs)
```

## 环境配置

- API环境在 `config/api_config.json` 的 `current_environment` 字段切换
- 三个环境：`development`（localhost）、`production`、`production_domain`（当前激活）
- 生产API：`https://api.genepop.com`
- 认证：JWT Token，24小时过期，存储在 `auth/token_manager.py`

## 技术栈

- **GUI**: PyQt6 >= 6.4.0（强制浅色模式）
- **数据库**: SQLAlchemy + PyMySQL (阿里云 PolarDB)
- **本地缓存**: SQLite（血缘数据缓存）
- **数据处理**: pandas, numpy, scipy, scikit-learn
- **图表**: matplotlib, networkx (血缘图)
- **报告**: openpyxl (Excel), python-pptx (PPT)
- **认证**: PyJWT, keyring
- **云存储**: oss2（阿里云OSS，公牛库下载）

## 配置文件

- `config/settings.py` - 全局设置（单例模式）
- `config/api_config.json` - API端点和环境切换
- `config/trait_translations.json` - 性状中英文映射
- `config/field_mappings.json` - 多数据源字段映射规则
- `config/db_config.py` - 数据库连接配置
- `version.py` - 版本号和完整版本历史
