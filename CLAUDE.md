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

# 安装依赖
pip install -r requirements.txt

# 打包 Mac 版本
pyinstaller GeneticImprove.spec

# 打包 Windows 版本
pyinstaller GeneticImprove_win.spec
```

注意：项目没有正式的测试框架或测试套件。`scripts/` 下有手动测试脚本。

## 版本管理

- 版本号格式：`主版本号.次版本号.修订号.构建号`（如 1.2.2.7）
- 版本定义在 `version.py` 的 `VERSION` 变量和 `VERSION_HISTORY` 列表
- 发布时使用 `/genetic-release` 斜杠命令（自动递增版本号、更新文件、提交推送、监控构建、上传OSS）
- 发布流程详见 `docs/版本发布提示词模板.md`，文档更新规则详见 `docs/文档维护规则.md`

## CI/CD

- GitHub Actions 工作流：`.github/workflows/build-releases.yml`
- 触发条件：推送 `v*.*.*` 格式的 Git 标签
- Python 3.9 + PyInstaller
- Windows：OneDir + Inno Setup 安装包（.exe）
- macOS：.app + DMG（**不打包数据库**，首次运行从 OSS 下载）
- 构建时排除 torch/torchvision/pyarrow（减小体积）
- 阿里云 OSS：上传安装包 + `version.json`（供软件检查更新）+ changelog

## 核心架构

### 分层结构

```
gui/                  # PyQt6 界面层
  ├─ main_window.py   # 主窗口（核心UI入口，超大文件）
  ├─ farm_selection_page.py  # 牧场选择（数据导入入口）
  ├─ progress.py      # 进度对话框（支持子任务并行显示、时间估算）
  ├─ *_dialog.py      # 各种对话框
  └─ *_worker.py      # 后台工作线程（QThread）

core/                 # 业务逻辑层
  ├─ data/            # 数据处理（processor.py, uploader.py）
  ├─ breeding_calc/   # 育种计算（性状、指数），基类 base_calculation.py
  ├─ matching/        # 个体选配算法（最复杂模块）
  ├─ inbreeding/      # 近交系数计算（Wright通径法）
  ├─ grouping/        # 分组管理
  ├─ excel_report/    # Excel报告生成（20个Sheet）
  ├─ ppt_report/      # PPT报告生成（基于模板填充，25个slide builder）
  └─ auto_analysis_runner.py  # 无GUI依赖的分析引擎

api/                  # API客户端层
  ├─ api_client.py    # 主API通信（认证、数据、版本）
  └─ yqn_api_client.py # 伊起牛平台API

auth/                 # 认证层（JWT + 离线备用）
config/               # 配置管理
utils/                # 工具函数
```

### 关键数据流

1. **数据导入**: `gui/farm_selection_page.py` → `core/data/processor.py` → 标准化Excel
2. **多数据源**: processor.py 自动识别数据源（伊起牛/慧牧云/DC305）并应用对应的字段映射（`config/field_mappings.json`）
3. **性状计算**: `core/breeding_calc/traits_calculation.py` → `index_calculation.py`
4. **个体选配**: `core/matching/complete_mating_executor.py` → `cycle_based_matcher.py`
5. **报告生成**: `core/excel_report/generator.py` 或 `core/ppt_report/generator.py`
6. **自动化流程**: `gui/auto_report_worker.py` → `core/auto_analysis_runner.py`（数据下载→分析→Excel→PPT一键完成）
7. **选配推送**: `core/api/mating_result_pusher.py` → `api/yqn_api_client.py` batchAdd 接口（中文字段→API英文字段映射，分批200条推送）

### 多线程模式

UI线程只处理界面交互，所有耗时操作通过 Worker 线程执行。Worker 通过 `pyqtSignal` 与 UI 通信：
- `progress.emit(percent, message)` - 进度更新
- `finished.emit(result)` - 完成通知
- `error.emit(error_msg)` - 错误通知

主要 Worker 线程：

| Worker | 功能 |
|--------|------|
| `auto_report_worker.py` | 自动报告完整流程（4阶段：下载→分析→Excel→PPT，支持并行分析） |
| `matching_worker.py` | 个体选配计算 |
| `recommendation_worker.py` | 推荐矩阵生成 |
| `excel_report_worker.py` | Excel 报告生成 |
| `ppt_report_worker.py` | PPT 报告生成 |
| `db_update_worker.py` | 数据库更新下载 |

### 计算模块基类

`core/breeding_calc/base_calculation.py` 的 `BaseCowCalculation`：
- 提供数据库连接管理（SQLAlchemy + SQLite）、数据检查、带重试的文件保存
- 子类需定义 `required_columns` 和 `output_prefix`

### 个体选配 (core/matching/)

最复杂的核心模块：
- `cycle_based_matcher.py` - **当前主分配器**，基于周期和库存比例分配
- `matrix_recommendation_generator.py` - 推荐矩阵生成，计算所有母牛×公牛配对得分
- `complete_mating_executor.py` - 完整选配流程编排
- `allocation_utils.py` - 分配工具函数
- 已废弃：`individual_matcher.py`、`matching_worker.py`、`recommendation_generator.py`

关键参数：默认近交系数阈值 3.125%，支持成母牛/后备牛各三个分组（A/B/C）。

### 选配推送 (core/api/)

- `mating_result_pusher.py` - 读取选配报告 → 转换为API格式 → 调用伊起牛 batchAdd 接口
- 字段映射：`母牛号→earNum`、`1选性控→sexedSemen1`、`母牛指数得分→indexScore` 等
- 每条记录包含 `farmCode`、`updateBy`、`updateTime`
- `push_records()` 分批推送，返回 `failed_records` 供重试
- 牧场信息从 `project_metadata.json`（`FileManager.save_project_metadata` 生成）读取，兼容旧 `farm_info.json`
- 仅 `login_type == 'yqn'` 时可用推送功能

### 数据处理 (core/data/)

- `processor.py`（约97KB）- 核心数据标准化引擎
  - NAAB号格式化：去除XK/SEX/性控前后缀，品种码转换，站号补齐
  - 多选牧场时，牛号添加站号前缀避免重号
- `yqn_data_converter.py` - 伊起牛API数据 → 标准Excel格式
- `bull_library_downloader.py` - 公牛库从阿里云OSS下载（132MB，支持断点续传）

### PPT Slide Builder 模式

- 基于模板填充架构（模板：`牧场牧场育种分析报告-模版.pptx`）
- `core/ppt_report/slide_builders/` 下 25 个 builder，每个负责一个章节
- 流程：从 Excel 特定 Sheet 读取数据 → 填充 PPT 表格/图表/文本框
- 支持动态页数（如 `part4_genetics.py` 根据性状数量生成）
- `template_slide_copier.py` 负责模板页复制

### 应用启动流程 (main.py)

1. 日志初始化（Windows `%APPDATA%/GeneticImprove/logs`，macOS `~/.genetic_improve/logs`）
2. 强制浅色模式（QPalette 覆盖系统深色模式）
3. 延迟导入重量级模块（`lazy_import()`）
4. 启动画面（`VideoSplashScreen` 播放 startup.mp4）
5. 登录验证（`LoginDialog`，支持选配软件账号/伊起牛账号两种方式）
6. 版本检查（用户 `cs` 跳过检查，强制更新时退出）
7. 主窗口显示（Windows 需 `show()` 后 `showMaximized()` 特殊处理）

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

## 依赖管理

- `requirements.txt` - 主依赖清单
- `requirements.linux.txt` - Linux 特定依赖
- `build_requirements.txt` - 构建工具依赖
- 平台特定依赖：`pywin32` (Windows)、`pyobjc-framework-Cocoa` (macOS)

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
- `config/field_mappings.json` - 多数据源字段映射规则（`normalize_mappings` 输入→标准列名，`display_mappings` 标准→中文显示名）
- `config/db_config.py` - 数据库连接配置
- `version.py` - 版本号和完整版本历史
- `version.json` - 客户端更新检查文件（同步到 OSS `latest/version.json`）
- `project_metadata.json`（项目内） - 牧场信息（由 `FileManager.save_project_metadata` 在数据导入时生成）
