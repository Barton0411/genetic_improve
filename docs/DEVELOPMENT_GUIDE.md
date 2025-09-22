# 遗传改良系统 - 开发指导文档 v3

## 🚨 关键配置信息（必看）

### 🔥 API服务配置
```yaml
生产服务器: 39.96.189.27
API域名: https://api.genepop.com
SSH密钥: ~/Downloads/genetic_improvement.pem
```

### 📡 核心API服务状态

| 服务 | 端口 | 路径 | 认证 | 重要度 |
|------|------|------|------|--------|
| **认证API** | 8081 | `/api/auth/*` | JWT | ⭐⭐⭐⭐⭐ |
| **数据API** | 8082 | `/api/data/*` | 无需 | ⭐⭐⭐⭐⭐ |
| 版本API | 8080 | `/api/version/*` | 无需 | ⭐⭐ |

### 🔑 认证配置
```python
JWT_SECRET_KEY = 'genetic-improve-api-secret-key'
JWT_ALGORITHM = 'HS256'
JWT_EXPIRE_HOURS = 24
```

### ⚡ 快速命令
```bash
# SSH连接服务器
ssh -i ~/Downloads/genetic_improvement.pem ecs-user@39.96.189.27

# 查看所有服务状态
sudo systemctl status genetic-auth-api genetic-data-api

# 重启所有服务
sudo systemctl restart genetic-auth-api genetic-data-api

# 查看认证服务日志
sudo journalctl -u genetic-auth-api -f

# 查看数据服务日志
sudo journalctl -u genetic-data-api -f
```

---

## 📋 项目概述

| 项目信息 | 详情 |
|---------|------|
| **项目名称** | 遗传改良系统 (Genetic Improve) |
| **当前版本** | v1.2.0.2 (2025-09-22) |
| **开发路径** | `/Users/bozhenwang/projects/mating/genetic_improve` |
| **Git仓库** | `https://github.com/Barton0411/genetic_improve.git` |
| **技术栈** | PyQt6 + FastAPI + MySQL |
| **支持平台** | Windows / macOS |

---

## 🎯 当前工作重点

### ✅ 已完成（v1.2.0.2）
- ✅ **OSS数据库分发** - 全面迁移到阿里云OSS，提升下载速度60%
- ✅ **下载进度显示** - 实时显示MB进度和百分比
- ✅ **智能重试机制** - 下载失败自动重试（最多3次）
- ✅ **版本管理优化** - 修复版本保存超时，统一使用OSS版本
- ✅ **缺失公牛智能预估** - 基于遗传趋势的数据补全
- ✅ **数据质量可视化** - Excel报告格式标记（红色/灰黄）
- ✅ **API安全改造** - 客户端完全移除数据库密码
- ✅ **性能优化** - 选配算法提升60%
- ✅ **多线程处理** - QThread实现，UI不卡顿

### 📌 当前开发任务

| 优先级 | 任务 | 说明 |
|-------|------|------|
| 🔴 高 | Excel报告生成 | 完成自动生成报告中的Excel整理汇总 |
| 🟡 中 | 体型外貌鉴定 | 收集体型外貌数据，分析缺陷性状 |
| 🟡 中 | 自动化生产报告 | 完成育种报告的自动生成 |
| 🟢 低 | API对接 | 等待真实API接口，切换推送模式 |

---

## 🏗️ 系统架构

### 整体架构
```
┌─────────────────────────────────────────────────────┐
│              客户端 (PyQt6 Desktop)                   │
├─────────────────────────────────────────────────────┤
│  界面层 → 业务逻辑层 → API客户端 → 云端服务            │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│               云端服务 (阿里云)                        │
├─────────────────────────────────────────────────────┤
│  Nginx (80/443) → Auth API (8081)                   │
│                 → Data API (8082)                   │
├─────────────────────────────────────────────────────┤
│  PolarDB MySQL + OSS存储                            │
└─────────────────────────────────────────────────────┘
```

### API端点详情

#### 认证服务端点 (端口8081)
| 方法 | 端点 | 认证 | 功能 |
|------|------|------|------|
| POST | `/api/auth/login` | ❌ | 用户登录 |
| POST | `/api/auth/register` | ❌ | 用户注册（需邀请码） |
| GET | `/api/auth/profile` | ✅ | 获取用户信息 |
| POST | `/api/auth/verify` | ✅ | 验证令牌有效性 |

#### 数据服务端点 (端口8082)
| 方法 | 端点 | 认证 | 功能 |
|------|------|------|------|
| GET | `/api/data/version` | ❌ | 获取数据库版本 |
| GET | `/api/data/bull_library` | ❌ | 下载公牛数据库 |
| POST | `/api/data/missing_bulls` | ❌ | 上传缺失公牛记录 |
| GET | `/api/data/stats` | ❌ | 获取统计信息 |

---

## 💾 数据库设计

### 核心表结构

#### 用户认证表
```sql
-- 用户表
CREATE TABLE `id-pw` (
    ID VARCHAR(50) PRIMARY KEY,
    PW VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 邀请码表
CREATE TABLE invitation_codes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(32) NOT NULL UNIQUE,
    status TINYINT DEFAULT 1,
    max_uses INT DEFAULT 1,
    current_uses INT DEFAULT 0,
    expire_time DATETIME
);
```

#### 待扩展业务表
```sql
-- 选配结果表（需添加牧场字段）
ALTER TABLE mating_results
ADD COLUMN result_farm_code VARCHAR(20);

-- 项目表
CREATE TABLE projects (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    project_name VARCHAR(100) NOT NULL,
    farm_code VARCHAR(20),
    user_id VARCHAR(50) NOT NULL,
    status ENUM('active', 'completed', 'archived')
);
```

---

## 📁 项目结构

```
genetic_improve/
├── api/                    # API服务（服务器端）
│   ├── auth_api.py        # 认证服务 (8081)
│   └── data_api.py        # 数据服务 (8082)
├── auth/                   # 认证模块
│   └── auth_service.py    # 认证服务
├── core/                   # 核心功能
│   ├── breeding_calc/     # 育种计算
│   ├── matching/          # 选配算法
│   └── data/              # 数据管理
├── gui/                    # 界面模块
│   ├── main_window.py     # 主窗口
│   └── login_dialog.py    # 登录对话框
└── main.py                # 程序入口
```

---

## 🚀 部署指南

### 服务器部署步骤
```bash
# 1. 连接服务器
ssh -i ~/Downloads/genetic_improvement.pem ecs-user@39.96.189.27

# 2. 更新代码
cd genetic_api
git pull

# 3. 重启服务
sudo systemctl restart genetic-auth-api genetic-data-api

# 4. 验证服务
curl https://api.genepop.com/api/health
```

### 客户端发布流程
```bash
# 1. 更新版本号
vim version.py

# 2. 提交代码
git add .
git commit -m "Release v1.1.0.x"
git push

# 3. 触发构建
./trigger_build.sh 1.1.0.x
```

---

## ⚠️ 注意事项

### 安全要点
- ✅ 客户端已完全移除数据库密码
- ✅ 所有数据操作通过API进行
- ✅ JWT令牌24小时自动过期
- ✅ 敏感操作需要令牌验证

### 开发规范
- 新功能优先考虑API实现
- 保持前后端分离架构
- 遵循RESTful设计原则
- 做好错误处理和日志记录

---

## 🚧 未来功能规划

### 1. 多牧场数据集成（计划中）

#### 业务场景
- **场景A：单牧场选配** - 单个牧场独立进行选配分析
- **场景B：多牧场育种分析** - 批量分析多个牧场的育种性状

#### 技术方案概要
```
数据流向：
1. 外部API → 2. 数据获取 → 3. 本地处理 → 4. 结果推送
```

#### 实施计划
- **第一阶段**：支持手动配置牧场信息
- **第二阶段**：实现API数据获取接口
- **第三阶段**：实现批量结果推送

### 2. 选配结果推送功能（已实现）

#### 功能说明
- 在个体选配页面添加了"📤 推送结果"按钮
- 选配完成后自动启用推送按钮
- 支持本地测试模式和API推送模式

#### 推送数据结构
```json
{
  "farm_code": "10001",
  "records": [
    {
      "母牛号": "12345",
      "上传日期": "2025-09-19 14:30:00",
      "分组": "成母牛A",
      "1选性控": "BULL001",
      "2选性控": "BULL002",
      "3选性控": "BULL003",
      "4选性控": "",
      "1选常规": "BULL004",
      "2选常规": "BULL005",
      "3选常规": "BULL006",
      "4选常规": "",
      "肉牛冻精": "",
      "母牛指数得分": 1250.5
    }
  ]
}
```

#### 牧场信息配置
在项目文件夹中创建 `farm_info.json` 文件：
```json
{
  "farm_code": "10001"
}
```

#### 推送流程
1. 检查 `farm_info.json` 文件是否存在
2. 读取 `个体选配报告.xlsx` 数据
3. 验证必填字段（farm_code、母牛号）
4. 组装推送数据（缺失字段自动填充空值）
5. 本地测试：保存到 `api_push_data.json`
6. 正式推送：调用API接口（待实现）

#### 错误处理
- 缺少 `farm_info.json`：提示用户创建文件
- 缺少母牛号：跳过该条记录
- 缺少其他字段：推送空字符串

### 3. 关键育种性状批量分析

#### 功能说明
- 支持多个牧场批量下载母牛数据
- 统一计算关键育种性状
- 按牧场分别推送结果

#### 数据处理
- 多牧场数据需要添加牧场编号前缀避免耳号冲突
- 处理完成后按原牧场拆分结果

### 4. 育种值预估逻辑

#### 背景说明
当公牛数据缺失（`xxx_identified = False`）时，系统使用预估值替代，确保育种值计算的完整性。

#### 遗传趋势文件
- **文件名**: `sire_traits_mean_by_cow_birth_year.xlsx`
- **内容**: 按母牛出生年份分组，统计其父系的平均育种值
- **计算方式**: 仅使用 `sire_identified = True` 的真实数据
- **用途**: 反映不同年代的遗传进展趋势

#### 预估值填充规则

##### 情况A：基于年份的预估（红色字体）
当 `xxx_identified = False` 但有相应出生年份时：
- **sire缺失**: 使用母牛 `birth_year` 对应的平均值
- **mgs缺失**: 使用 `dam_birth_year` 对应的平均值
- **mmgs缺失**: 使用 `mgd_birth_year` 对应的平均值
- **Excel格式**: 红色字体（RGB: 255,0,0）

##### 情况B：默认值预估（黑底黄字）
当 `xxx_identified = False` 且无相应出生年份时：
- 使用默认公牛 `999HO99999` 的育种值
- **Excel格式**:
  - 单元格背景：黑色（RGB: 0,0,0）
  - 字体颜色：亮黄色（RGB: 255,255,0）

#### 视觉标识说明
| 数据类型 | 显示格式 | 含义 |
|---------|---------|------|
| 真实值 | 黑字白底（正常） | 数据库中存在的真实数据 |
| 年份预估值 | 红色字体 | 基于遗传趋势的合理预估 |
| 默认预估值 | 黑底黄字 | 无参考信息的默认值 |

#### 影响文件
- `processed_cow_data_key_traits_detail.xlsx`
- `processed_cow_data_key_traits_scores_pedigree.xlsx`
- `processed_cow_data_key_traits_scores_genomic.xlsx`
- `processed_index_cow_index_scores.xlsx`

### 5. 数据源适配层

#### 设计目标
- 支持手动上传（当前）
- 支持API获取（未来）
- 支持混合模式（降级方案）

#### 切换机制
- 通过配置文件控制数据源
- 保持接口统一，实现可替换

---

## 📞 技术支持

- **开发者**: 王波臻
- **测试团队**: 繁育系统工程师
- **问题反馈**: https://github.com/Barton0411/genetic_improve/issues

---

## 📝 版本历史

| 版本 | 日期 | 主要更新 |
|------|------|---------|
| v1.1.2.0 | 2025-09-21 | 缺失数据智能预估，Excel格式化标记 |
| v1.1.0.6 | 2025-09-20 | 修复dam列格式，保持ID完整性 |
| v1.1.0.5 | 2025-09-19 | 选配结果推送功能完整实现 |
| v1.1.0.4 | 2025-09-19 | API部署完成，客户端移除数据库密码 |
| v1.1.0.3 | 2025-09-19 | 性能优化，算法提升60% |
| v1.1.0.2 | 2025-09-19 | QThread实现，防止UI卡顿 |
| v1.1.0.1 | 2025-09-19 | API架构重构，移除SQLAlchemy |

---

**文档更新日期**: 2025-09-21
**下次审查日期**: 2025-09-28