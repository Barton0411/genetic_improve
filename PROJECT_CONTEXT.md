# 伊利奶牛选配系统 - 项目上下文提示词

## 📍 项目基本信息

**项目位置**: `/Users/bozhenwang/projects/mating/genetic_improve`
**Git仓库**: `https://github.com/Barton0411/genetic_improve.git`
**当前版本**: v1.1.0.0 (2025-09-17)
**主要分支**: main

## 🎯 项目概述

伊利奶牛选配系统是一个专业的奶牛遗传改良和选配管理系统，集成了数据分析、遗传评估、选配推荐等功能。基于PyQt6开发，支持Windows和macOS双平台。

## 🏗️ 核心架构

```
genetic_improve/
├── core/                    # 核心功能模块
│   ├── config/             # 配置管理
│   ├── data_processor/     # 数据处理器
│   ├── genetics/           # 遗传学计算
│   ├── mating/             # 选配算法
│   ├── reports/            # 报告生成
│   └── update/             # 版本更新系统 ✅ 已完成
├── gui/                    # 用户界面
│   ├── main_window.py      # 主窗口
│   ├── login_dialog.py     # 登录对话框 🔄 需要添加注册功能
│   ├── splash_screen.py    # 启动画面
│   └── components/         # UI组件
├── database/               # 数据库相关 🔄 需要API化
│   ├── connection.py       # 数据库连接 (硬编码，需要改为API)
│   ├── models/             # 数据模型
│   └── migrations/         # 数据库迁移
├── utils/                  # 工具模块
├── assets/                 # 静态资源
├── deployment/             # 部署配置
└── docs/                   # 文档
```

## ✅ 已完成功能 (v1.1.0.0)

### 自动更新系统 (完整实现)
- ✅ 强制更新机制，确保关键更新必须安装
- ✅ 应用内智能更新功能，无需手动下载
- ✅ 跨平台支持 (Windows/macOS)
- ✅ 完整的更新对话框和用户交互
- ✅ 基于阿里云OSS的版本管理
- ✅ 文件位置: `core/update/` 模块

### 核心业务功能
- ✅ 育种项目管理
- ✅ 数据上传功能 (母牛、公牛、配种记录等)
- ✅ 关键育种性状分析
- ✅ 近交系数计算 (6代系谱通经法)
- ✅ 隐性基因分析
- ✅ 个体选配推荐和自动分组
- ✅ 选配备注系统 (详细说明约束过滤情况)
- ✅ 冻精分配管理

### 技术基础设施
- ✅ PyQt6现代化界面
- ✅ 阿里云PolarDB数据库集成
- ✅ 完整的构建和部署流程 (GitHub Actions)

## 🔄 当前需要实现的功能

### 📋 接下来的6个主要任务

#### 🎯 **高优先级任务**

**1. 在登录窗口添加账号注册功能** 
- ✅ 已发现protein_screening项目中的完整注册功能实现
- 📁 参考文件：`/Users/bozhenwang/projects/protein_screening/auth_module/register_dialog.py`
- 🔧 需要移植到：`/Users/bozhenwang/projects/mating/genetic_improve/gui/login_dialog.py`
- 🆕 包含邀请码验证、工号注册、完整的UI界面

**2. API化改造 - 替换硬编码数据库连接**
- 🚨 当前问题：数据库连接信息硬编码在 `core/data/update_manager.py`
- 🎯 目标：开发API接口，客户端通过API访问数据
- 🔒 提升安全性和维护性
- 💡 建议技术栈：FastAPI或Flask + JWT认证

**3. 开发选配结果API + 添加牧场站号字段**
- 🔗 为大平台对接准备REST API接口
- 🆕 在结果表中添加 `result_farm_code` 列
- 🏢 支持多牧场数据区分
- 📊 提供标准化的选配结果数据交换格式

#### 🎯 **中优先级任务**

**4. 完成体型外貌鉴定数据分析模块**
- 📊 在v1.1.0.0中标记为"暂未开放，重构中"
- 🔄 需要重新实现自动分析功能
- 📈 集成可视化和报告生成
- 🧬 包含体型评分、外貌指标分析

**5. 完成自动报告系统 - PPT及Excel格式**
- 📋 当前只有PPT报告，需要添加Excel格式
- ⚡ 优化报告生成性能和内容完整性
- 📊 涉及文件：`core/reports/` 模块
- 📈 支持多种导出格式和模板定制

**6. 其他改进项**
- 🔧 代码优化和性能提升
- 📚 文档完善
- 🧪 测试覆盖率提升

### 技术实现细节

#### 用户认证升级
```python
# 从protein_screening移植的功能：
- RegisterDialog类：完整的注册界面
- 邀请码验证机制
- 工号作为登录账号
- 密码强度验证
- 与现有AuthService集成
```

#### API化架构设计
```
当前架构: 客户端 -> 直连数据库 (硬编码连接)
目标架构: 客户端 -> API服务器 -> 数据库
- API网关: 统一认证和路由
- 数据安全: 加密传输和存储
- 负载均衡: 支持横向扩展
```

#### 数据库扩展
```sql
-- 新增牧场标识字段
ALTER TABLE mating_results 
ADD COLUMN result_farm_code VARCHAR(20) COMMENT '牧场站号';

-- 创建索引提升查询性能
CREATE INDEX idx_farm_code ON mating_results(result_farm_code);
```

## 🛠️ 技术栈

### 前端
- **GUI框架**: PyQt6
- **图表**: matplotlib, plotly
- **界面**: 现代化设计，支持深色/浅色模式

### 后端
- **语言**: Python 3.9+
- **数据库**: 阿里云PolarDB MySQL
- **云存储**: 阿里云OSS
- **API框架**: 需要选择 (Flask/FastAPI)

### 部署
- **构建**: PyInstaller
- **CI/CD**: GitHub Actions
- **平台**: Windows (.exe), macOS (.dmg)

## 🔗 相关项目

### protein_screening项目
**位置**: `/Users/bozhenwang/projects/protein_screening`
**关联**: 包含已实现的用户注册功能，需要移植到当前项目

## 📋 数据库当前状态

### 连接方式
- **当前**: 硬编码数据库连接信息
- **问题**: 安全性低，难以维护
- **目标**: API化，统一接口管理

### 主要数据表
- 母牛数据表
- 公牛数据表
- 配种记录表
- 选配结果表 (需要添加 result_farm_code 字段)
- 用户认证表

## 🎯 下一步工作优先级

1. **高优先级**: API化改造 (解决硬编码问题)
2. **高优先级**: 选配结果API + 数据库字段添加
3. **中优先级**: 用户注册功能移植
4. **中优先级**: 体型外貌鉴定模块重构
5. **低优先级**: 报告系统增强 (PPT/Excel)

## 📝 开发注意事项

### 代码规范
- 保持现有的代码风格和架构
- 使用现有的配置管理系统
- 遵循PyQt6最佳实践

### 数据安全
- API接口需要认证机制
- 敏感数据加密存储
- 日志记录和错误处理

### 兼容性
- 保持与现有功能的兼容性
- 支持数据迁移
- 向后兼容的API设计

## 🚀 快速启动指南

```bash
# 进入项目目录
cd /Users/bozhenwang/projects/mating/genetic_improve

# 激活虚拟环境 (如果存在)
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 运行程序
python main.py

# 构建应用 (如果需要)
python build_scripts/build_mac.py  # macOS
python build_scripts/build_windows.py  # Windows
```

---

**使用说明**: 这个文档用于新对话框的上下文初始化，确保AI助手了解项目的完整状态和当前需求。