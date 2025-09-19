# 伊利奶牛选配系统 - 开发指导文档 v2

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
| **项目名称** | 伊利奶牛选配系统 (Genetic Improve) |
| **当前版本** | v1.1.0.4 (2025-09-19) |
| **开发路径** | `/Users/bozhenwang/projects/mating/genetic_improve` |
| **Git仓库** | `https://github.com/Barton0411/genetic_improve.git` |
| **技术栈** | PyQt6 + FastAPI + MySQL |
| **支持平台** | Windows / macOS |

---

## 🎯 当前工作重点

### ✅ 已完成（v1.1.0.4）
- ✅ **API安全改造** - 客户端完全移除数据库密码
- ✅ **性能优化** - 选配算法提升60%
- ✅ **多线程处理** - QThread实现，UI不卡顿
- ✅ **缺失公牛上传** - API认证问题已解决

### 📌 下一步任务

| 优先级 | 任务 | 工期 | 说明 |
|-------|------|------|------|
| 🔴 高 | 选配结果API | 2-3天 | 支持多牧场数据管理 |
| 🔴 高 | Excel报告生成 | 2-3天 | 补充导出功能 |
| 🟡 中 | 体型外貌鉴定 | 4-5天 | 恢复v1.1.0.0功能 |
| 🟡 中 | 自动化生产报告 | 3-4天 | 恢复v1.1.0.0功能 |

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

## 📞 技术支持

- **开发者**: 王波臻
- **测试团队**: 繁育系统工程师
- **问题反馈**: https://github.com/Barton0411/genetic_improve/issues

---

## 📝 版本历史

| 版本 | 日期 | 主要更新 |
|------|------|---------|
| v1.1.0.4 | 2025-09-19 | API部署完成，客户端移除数据库密码 |
| v1.1.0.3 | 2025-09-19 | 性能优化，算法提升60% |
| v1.1.0.2 | 2025-09-19 | QThread实现，防止UI卡顿 |
| v1.1.0.1 | 2025-09-19 | API架构重构，移除SQLAlchemy |

---

**文档更新日期**: 2025-09-19
**下次审查日期**: 2025-09-25