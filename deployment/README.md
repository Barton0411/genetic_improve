# Genetic Improve 部署文档

## 项目架构

### 系统架构图
```
客户端软件 → ECS API服务器 → PolarDB数据库
                ↓
            OSS对象存储
                ↓  
         牧场管理系统(第三方)
```

## 云服务资源

### 阿里云ECS服务器
- **实例ID**: `i-2ze0wkrma5my2k7a7zba` (iZa5my2k7a7zbaZ)
- **规格**: ecs.e-c1m1.large (2核2GB)
- **公网IP**: `39.96.189.27`
- **内网IP**: `172.23.188.168`
- **有效期**: 2025-09-16 ~ 2025-12-16 (3个月试用)
- **系统**: Ubuntu 24.04 64位 ✅
- **地域**: 华北2(北京) G
- **SSH密钥**: genetic_improvement.pem
- **状态**: 运行中 ✅
- **环境配置**: ✅ 已完成基础软件安装和防火墙配置

### 阿里云OSS对象存储
- **套餐**: 标准-本地冗余存储 100GB (¥118.99/年)
- **Bucket名称**: `genetic-improve`
- **地域**: 华北2(北京) `oss-cn-beijing.aliyuncs.com`
- **用途**: 存储应用安装包和版本文件
- **访问权限**: 公共读（允许匿名下载）
- **状态**: 🔄 待配置

#### OSS目录结构
```
genetic-improve/
└── releases/
    ├── v1.0.4/
    │   ├── GeneticImprove_v1.0.4_win.exe    # Windows安装版
    │   ├── GeneticImprove_v1.0.4_win.zip    # Windows便携版
    │   └── GeneticImprove_v1.0.4_mac.dmg    # macOS安装包
    ├── v1.0.5/
    │   ├── GeneticImprove_v1.0.5_win.exe
    │   ├── GeneticImprove_v1.0.5_win.zip
    │   └── GeneticImprove_v1.0.5_mac.dmg
    └── latest/
        └── version.json                      # 最新版本信息
```

#### 访问URL格式
```
安装包URL: https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v{version}/{filename}
版本信息: https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/latest/version.json
```

#### OSS配置步骤 ✅
1. ✅ 已创建OSS配置模块：`config/oss_config.py`
2. 🔄 需要在阿里云控制台创建Bucket
3. 🔄 需要配置访问密钥环境变量
4. 🔄 需要设置Bucket权限为公共读
5. 🔄 需要配置CORS（跨域访问）
6. 🔄 需要创建版本管理API接口

### PolarDB数据库
- **Host**: `defectgene-new.mysql.polardb.rds.aliyuncs.com`
- **IP**: `8.147.221.122`
- **Port**: `3306`
- **数据库**: `bull_library`
- **用户**: `defect_genetic_checking`

## 功能模块

### 1. 版本更新系统
**流程**:
1. 客户端启动检查版本
2. 调用API获取最新版本信息
3. 如有更新显示下载对话框
4. 从OSS下载新版本安装包

**API端点**:
- `GET /api/version/latest` - 获取最新版本
- `GET /api/version/{version}/download/{platform}` - 获取下载链接

### 2. 选配报告推送系统
**流程**:
1. 用户在本地软件生成选配报告
2. 调用API推送报告数据
3. API转发给牧场管理系统
4. 记录推送日志

**API端点**:
- `POST /api/reports/submit` - 提交选配报告
- `GET /api/reports/status/{id}` - 查询推送状态

## API服务详情

### 访问地址
- **基础URL**: `http://39.96.189.27:8080`
- **版本检查**: `http://39.96.189.27:8080/api/version/latest`
- **健康检查**: `http://39.96.189.27:8080/api/health`
- **服务状态**: 系统服务运行中（systemd管理）

### 服务管理命令
```bash
# 查看服务状态
sudo systemctl status genetic-api

# 启动服务
sudo systemctl start genetic-api

# 停止服务
sudo systemctl stop genetic-api

# 重启服务
sudo systemctl restart genetic-api

# 查看日志
sudo journalctl -u genetic-api -f

# 查看最近50条日志
sudo journalctl -u genetic-api -n 50
```

### API应用文件
- **工作目录**: `/home/ecs-user/genetic_api/`
- **主程序**: `main.py`
- **配置文件**: `config.py`
- **虚拟环境**: `venv/`
- **Python版本**: 3.12.3
- **框架**: FastAPI + Uvicorn

## 数据库表设计

### 版本管理表 ✅
```sql
CREATE TABLE app_versions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    version VARCHAR(20) NOT NULL UNIQUE,
    release_date DATETIME NOT NULL,
    is_latest BOOLEAN DEFAULT FALSE,
    changes TEXT,
    mac_download_url VARCHAR(500),
    win_download_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 报告推送记录表 ✅
```sql
CREATE TABLE report_push_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    report_id VARCHAR(100) NOT NULL,
    farm_system_url VARCHAR(500),
    push_status ENUM('pending', 'success', 'failed') DEFAULT 'pending',
    push_time DATETIME,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 部署步骤

### 1. 服务器环境配置 ✅
1. ✅ 已选择Ubuntu 24.04 64位系统
2. ✅ 已配置安全组开放端口：22, 80, 443, 8080
3. ✅ 已安装Python 3.12.3, nginx, git, curl, wget
4. ✅ 已配置防火墙规则
5. 配置SSL证书和域名解析

### SSH连接信息
```bash
# SSH连接命令
ssh -i ~/Downloads/genetic_improvement.pem ecs-user@39.96.189.27

# 已安装软件版本
- Python: 3.12.3
- Nginx: 1.24.0
- 防火墙: 已启用，开放端口 22,80,443,8080
```

### 2. API应用部署 ✅
1. ✅ 已部署FastAPI应用
2. ✅ 已配置数据库连接
3. ✅ 已设置systemd系统服务
4. ✅ 已配置开机自启动
5. 待配置OSS访问密钥

### 3. 域名和SSL
1. 注册域名 (推荐.com域名)
2. 配置DNS解析到ECS IP
3. 申请SSL证书(Let's Encrypt免费证书)
4. 配置Nginx反向代理

## GitHub Actions自动构建

### 触发方式
1. **标签触发**: 推送形如`v1.0.5`的版本标签
2. **手动触发**: GitHub Actions页面手动运行

### 构建产物
- **Windows**: `GeneticImprove_v{version}_win.zip` (OneDir模式，快速启动)
- **macOS**: `GeneticImprove_v{version}_mac.dmg` (标准.app应用)

### 使用方法
```bash
# 触发新版本构建
./trigger_build.sh 1.0.5

# 或手动执行
git tag -a "v1.0.5" -m "Release v1.0.5"
git push origin "v1.0.5"
```

### 构建结果
- GitHub Release页面自动创建
- 安装包自动上传到Release
- 可下载用于测试或分发

## OSS详细配置指南

### 1. 阿里云控制台配置
1. **创建Bucket**:
   - 登录阿里云OSS控制台
   - 创建Bucket：`genetic-improve`
   - 选择地域：华北2(北京)
   - 存储类型：标准存储
   - 读写权限：公共读

2. **配置CORS（跨域访问）**:
   ```xml
   <CORSRule>
     <AllowedOrigin>*</AllowedOrigin>
     <AllowedMethod>GET</AllowedMethod>
     <AllowedMethod>HEAD</AllowedMethod>
     <AllowedHeader>*</AllowedHeader>
   </CORSRule>
   ```

3. **获取访问密钥**:
   - 创建子用户，授予OSS读写权限
   - 记录AccessKey ID和AccessKey Secret

### 2. 服务器环境变量配置
在ECS服务器上设置环境变量：
```bash
# 编辑环境变量文件
sudo nano /etc/environment

# 添加以下内容
OSS_ACCESS_KEY_ID="your_access_key_id"
OSS_ACCESS_KEY_SECRET="your_access_key_secret"

# 重新加载环境变量
source /etc/environment
```

### 3. 版本文件示例 (version.json)
```json
{
  "version": "1.0.5",
  "release_date": "2025-09-16",
  "changes": [
    "修复Mac应用图标显示问题",
    "优化Windows构建完整性",
    "更新应用名称为伊利奶牛选配"
  ],
  "downloads": {
    "windows_installer": {
      "url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.5/GeneticImprove_v1.0.5_win.exe",
      "size": "300MB",
      "checksum": "sha256:..."
    },
    "windows_portable": {
      "url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.5/GeneticImprove_v1.0.5_win.zip", 
      "size": "350MB",
      "checksum": "sha256:..."
    },
    "macos": {
      "url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.5/GeneticImprove_v1.0.5_mac.dmg",
      "size": "280MB", 
      "checksum": "sha256:..."
    }
  }
}
```

## 更新版本流程（含OSS）

### 开发完成新版本后:
1. 更新`version.py`中的版本号
2. 更新版本历史记录
3. 提交代码到GitHub
4. 运行`git tag -a "v{version}" -m "Release v{version}"`触发构建
5. 等待GitHub Actions完成构建
6. **从GitHub Release下载构建好的安装包**
7. **上传安装包到OSS对应目录** (releases/v{version}/)
8. **更新version.json文件并上传到OSS** (releases/latest/version.json)
9. 在PolarDB中插入新版本记录：
   ```sql
   INSERT INTO app_versions (version, release_date, is_latest, changes, mac_download_url, win_download_url)
   VALUES ('1.0.5', NOW(), TRUE, '更新说明', 
           'https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.5/GeneticImprove_v1.0.5_mac.dmg',
           'https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.5/GeneticImprove_v1.0.5_win.exe');
   
   -- 将旧版本标记为非最新
   UPDATE app_versions SET is_latest = FALSE WHERE version != '1.0.5';
   ```
10. 测试版本更新功能：访问 http://39.96.189.27:8080/api/version/latest

## 成本估算

- **ECS服务器**: ¥99/年 (试用期后)
- **域名**: ¥55/年 (.com域名)
- **OSS存储**: ¥118.99/年 (已购买)
- **流量费**: 按量计费 (¥0.5/GB)
- **SSL证书**: 免费 (Let's Encrypt)

**总计约**: ¥273/年 (月均¥23)

## 联系信息

- **GitHub仓库**: https://github.com/Barton0411/genetic_improve
- **开发团队**: Genetic Improve Team
- **技术支持**: 详见项目文档