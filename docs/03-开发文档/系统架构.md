# 系统架构文档

## 📋 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         客户端应用                                │
│                   (PyQt6 Desktop App)                           │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  用户认证    │  │  数据处理    │  │  育种计算    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  选配推荐    │  │  报告生成    │  │  本地缓存    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                          │
                          │ HTTPS (api.genepop.com)
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Nginx 反向代理 (443)                          │
│                                                                 │
│  /api/auth/*  →  认证API (8081)                                │
│  /api/data/*  →  数据API (8082)                                │
└─────────────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ↓                               ↓
┌──────────────────┐            ┌──────────────────┐
│   认证API服务     │            │   数据API服务     │
│   (FastAPI)      │            │   (FastAPI)      │
│   Port: 8081     │            │   Port: 8082     │
│                  │            │                  │
│  - 用户登录      │            │  - 版本检查      │
│  - 用户注册      │            │  - 缺失公牛上传  │
│  - 令牌验证      │            │                  │
└──────────────────┘            └──────────────────┘
          │                               │
          └───────────────┬───────────────┘
                          ↓
              ┌──────────────────────┐
              │   PolarDB MySQL      │
              │                      │
              │  - id-pw (用户)      │
              │  - invitation_codes  │
              │  - miss_bull         │
              │  - bull_library      │
              │  - app_versions      │
              └──────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      阿里云 OSS 对象存储                          │
│                  (genetic-improve bucket)                       │
│                                                                 │
│  releases/bull_library/                                         │
│    ├── bull_library.db (132MB, 247,192条)                      │
│    └── bull_library_version.json                               │
│                                                                 │
│  releases/v1.2.0.4/                                            │
│    ├── 伊利奶牛选配_v1.2.0.4_win.exe                           │
│    ├── 伊利奶牛选配_v1.2.0.4_win.zip                           │
│    └── 伊利奶牛选配_v1.2.0.4_mac.dmg                           │
│                                                                 │
│  客户端直接下载 (公共读权限)                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 数据流向

### 1. 用户认证流程
```
客户端 → HTTPS → Nginx → 认证API (8081) → PolarDB
  ↓
JWT Token 返回
  ↓
后续请求携带 Token
```

### 2. 数据库下载流程（✅ 当前方案）
```
客户端启动
  ↓
检查本地数据库版本
  ↓
请求 OSS 版本文件 (bull_library_version.json)
  ↓
版本对比
  ↓
直接从 OSS 下载 bull_library.db (132MB)
  ↓
保存到本地缓存 (~/.genetic_improve/)
```

**优势:**
- ⚡ 下载速度快（OSS CDN加速）
- 💰 成本低（OSS流量费用低）
- 🔧 服务器压力小（无需通过API转发）
- 📦 支持断点续传

**已废弃方案:** ~~通过API下载~~
- ❌ 服务器带宽限制
- ❌ API性能瓶颈
- ❌ 成本高

### 3. 缺失公牛上传流程
```
用户上传公牛数据文件
  ↓
数据标准化处理
  ↓
检查本地数据库
  ↓
发现缺失公牛 (NAAB号不存在)
  ↓
POST /api/data/missing_bulls (无需认证)
  ↓
保存到 PolarDB miss_bull 表
  ↓
提示用户哪些公牛未找到
```

### 4. 选配计算流程
```
用户上传数据 → 本地处理
  ↓
数据标准化 (NAAB号、性状值)
  ↓
查询本地 bull_library.db
  ↓
育种指数计算
  ↓
近交系数计算 (6代系谱)
  ↓
智能选配推荐
  ↓
生成报告 (Excel/PPT)
```

---

## 🛠️ 技术栈

### 客户端
```yaml
框架: PyQt6
语言: Python 3.12
打包: PyInstaller + Inno Setup (Windows) / DMG (macOS)

核心库:
  - pandas: 数据处理
  - sqlalchemy: 数据库操作
  - openpyxl: Excel读写
  - python-pptx: PPT生成
  - requests: HTTP请求
  - oss2: 阿里云OSS
```

### 服务端
```yaml
框架: FastAPI
语言: Python 3.12
服务器: Ubuntu 24.04 LTS
Web服务器: Nginx 1.24.0
进程管理: systemd
SSL证书: Let's Encrypt (certbot)

核心库:
  - fastapi: Web框架
  - uvicorn: ASGI服务器
  - pymysql: MySQL连接
  - pyjwt: JWT认证
```

### 数据库
```yaml
生产数据库: PolarDB MySQL
本地缓存: SQLite 3
主表:
  - bull_library: 公牛遗传数据 (247,192条)
  - id-pw: 用户认证
  - invitation_codes: 邀请码
  - miss_bull: 缺失公牛记录
  - app_versions: 版本管理
```

### 云服务
```yaml
服务器: 阿里云ECS (2核2GB, 华北2北京)
对象存储: 阿里云OSS (100GB标准存储)
数据库: 阿里云PolarDB MySQL
域名: genepop.com
DNS: [域名服务商]
```

---

## 🔐 安全架构

### 认证机制
```
1. 用户注册/登录 → JWT Token (24小时有效期)
2. Token存储在本地配置文件
3. API请求携带 Authorization: Bearer {token}
4. 特殊接口无需认证: /api/data/missing_bulls
```

### 网络安全
```
- 全站HTTPS (SSL证书自动续期)
- SSH仅密钥认证 (密码登录禁用)
- 数据库限制IP访问 (仅ECS内网)
- OSS公共读权限 (仅数据库文件和安装包)
```

### 数据安全
```
- 用户密码加密存储 (PolarDB)
- JWT密钥配置 (环境变量)
- 敏感配置不提交Git (.gitignore)
```

---

## 📊 性能优化

### 客户端优化
```
1. 本地数据库缓存 (避免重复下载)
2. 系谱计算缓存 (pedigree_cache.pkl)
3. 多线程数据处理 (避免UI卡顿)
4. 增量更新机制 (仅下载变化部分)
```

### 服务端优化
```
1. Nginx反向代理 (负载均衡)
2. API服务独立部署 (端口隔离)
3. 数据库连接池 (减少连接开销)
4. OSS CDN加速 (提升下载速度60%)
```

### 数据库优化
```
1. 索引优化 (NAAB号、品种字段)
2. 查询缓存
3. 定期清理无用数据
```

---

## 🔄 数据同步机制

### 版本管理
```json
// OSS: releases/bull_library/bull_library_version.json
{
  "version": "1.2.2",
  "update_time": "2025-09-22T10:30:00",
  "file_size": 138412032,
  "record_count": 247192,
  "download_url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/bull_library/bull_library.db"
}
```

### 更新流程
```
1. 管理员更新 bull_library.db
2. 上传到 OSS
3. 更新 bull_library_version.json
4. 客户端自动检测新版本
5. 提示用户更新
6. 下载并替换本地数据库
```

---

## 📁 项目目录结构

```
genetic_improve/
├── api/                    # API客户端
│   ├── api_client.py       # 统一API调用
│   └── config.py           # API配置
├── core/                   # 核心业务逻辑
│   ├── breeding_calc/      # 育种计算
│   ├── data/              # 数据处理
│   └── reports/           # 报告生成
├── gui/                   # PyQt6界面
│   ├── main_window.py     # 主窗口
│   └── dialogs/           # 对话框
├── config/                # 配置文件
│   ├── api_config.json    # API配置
│   └── db_config.py       # 数据库配置
├── docs/                  # 📚 文档中心
└── utils/                 # 工具函数
```

---

## 🚀 部署架构

### 服务器部署
```
ECS服务器 (39.96.189.27)
├── /home/ecs-user/genetic_improve_auth/  # 认证API
│   ├── venv/
│   └── auth_api.py
├── /home/ecs-user/api/                   # 数据API
│   ├── venv/
│   └── data_api.py
└── /etc/nginx/                           # Nginx配置
    └── sites-available/default
```

### 服务管理
```bash
# 查看服务状态
sudo systemctl status genetic-auth-api
sudo systemctl status genetic-data-api
sudo systemctl status nginx

# 重启服务
sudo systemctl restart genetic-auth-api
sudo systemctl restart genetic-data-api
sudo systemctl reload nginx
```

---

## 📝 架构演进历史

### v1.0 - 初始架构
- 客户端直连PolarDB
- 无云存储
- 手动更新数据库

### v1.1 - API化
- 引入认证API
- 引入数据API
- 通过API下载数据库

### v1.2 - OSS优化（当前）
- ✅ 数据库下载改为OSS直接下载
- ✅ 缺失公牛通过API上传
- ✅ 性能提升60%

### 未来规划
- 📝 选配结果推送到牧场系统
- 📝 Web版本开发
- 📝 移动端支持

---

## 🔍 技术决策记录

### 为什么用OSS代替API下载？
```
问题: API下载132MB文件占用服务器带宽，速度慢
方案: 改用OSS直接下载
结果:
  - 下载速度提升60%
  - 服务器压力降低
  - 成本降低
  - 支持断点续传
```

### 为什么缺失公牛上传不需要认证？
```
原因:
  - 收集用户反馈数据，希望降低门槛
  - 数据本身不敏感（只是NAAB号）
  - 便于数据收集和完善
```

### 为什么用PyQt6而不是Web？
```
原因:
  - 桌面应用性能更好
  - 可离线使用
  - 数据隐私（本地处理）
  - 用户习惯（Excel/PPT导出）
```

---

最后更新: 2025-10-07
版本: v1.2.0.4
