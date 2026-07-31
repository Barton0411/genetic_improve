# 云服务配置详情

## 🌩️ 阿里云 ECS 服务器

### 基本信息
```yaml
实例ID: i-2ze0wkrma5my2k7a7zba
实例名称: iZa5my2k7a7zbaZ
规格: ecs.e-c1m1.large (2核2GB)
公网IP: 39.96.189.27
内网IP: 172.23.188.168
地域: 华北2(北京) Zone G
操作系统: Ubuntu 24.04 LTS 64位
付费模式: 按量付费
到期时间: 2025-12-16
```

### SSH连接
```bash
# 使用密钥连接
ssh -i ~/Downloads/genetic_improvement.pem ecs-user@39.96.189.27

# 密钥权限设置
chmod 600 ~/Downloads/genetic_improvement.pem
```

---

## 📦 已安装软件

### 系统软件
```yaml
操作系统: Ubuntu 24.04 LTS
Python: 3.12.3
Nginx: 1.24.0
Certbot: (Let's Encrypt SSL证书)
Git: (版本控制)
```

### Python 虚拟环境
```yaml
认证API环境:
  路径: /home/ecs-user/genetic_improve_auth/venv
  Python版本: 3.12.3
  依赖: FastAPI, PyJWT, PyMySQL, uvicorn

数据API环境:
  路径: /home/ecs-user/venv
  Python版本: 3.12.3
  依赖: FastAPI, PyMySQL, uvicorn
```

---

## ⚙️ 系统服务

### 服务配置

#### 1. 认证API服务
```yaml
服务名: genetic-auth-api
端口: 8081
工作目录: /home/ecs-user/genetic_improve_auth
启动命令: venv/bin/python auth_api.py
配置文件: /etc/systemd/system/genetic-auth-api.service
```

**服务文件内容:**
```ini
[Unit]
Description=Genetic Improve Auth API
After=network.target

[Service]
Type=simple
User=ecs-user
WorkingDirectory=/home/ecs-user/genetic_improve_auth
ExecStart=/home/ecs-user/genetic_improve_auth/venv/bin/python auth_api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 2. 数据API服务
```yaml
服务名: genetic-data-api
端口: 8082
工作目录: /home/ecs-user/api
启动命令: venv/bin/python data_api.py
配置文件: /etc/systemd/system/genetic-data-api.service
```

**服务文件内容:**
```ini
[Unit]
Description=Genetic Improve Data API
After=network.target

[Service]
Type=simple
User=ecs-user
WorkingDirectory=/home/ecs-user/api
ExecStart=/home/ecs-user/venv/bin/python data_api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 服务管理命令

```bash
# 查看服务状态
sudo systemctl status genetic-auth-api
sudo systemctl status genetic-data-api
sudo systemctl status nginx

# 启动服务
sudo systemctl start genetic-auth-api
sudo systemctl start genetic-data-api
sudo systemctl start nginx

# 停止服务
sudo systemctl stop genetic-auth-api
sudo systemctl stop genetic-data-api

# 重启服务
sudo systemctl restart genetic-auth-api
sudo systemctl restart genetic-data-api
sudo systemctl reload nginx

# 设置开机自启
sudo systemctl enable genetic-auth-api
sudo systemctl enable genetic-data-api
sudo systemctl enable nginx

# 查看日志
sudo journalctl -u genetic-auth-api -f
sudo journalctl -u genetic-data-api -f
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

---

## 🌐 Nginx 配置

### 配置文件位置
```bash
主配置: /etc/nginx/nginx.conf
站点配置: /etc/nginx/sites-available/default
SSL证书: /etc/letsencrypt/live/api.genepop.com/
```

### 核心配置（简化版）

```nginx
server {
    listen 80;
    server_name api.genepop.com;

    # HTTP重定向到HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name api.genepop.com;

    # SSL证书配置
    ssl_certificate /etc/letsencrypt/live/api.genepop.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.genepop.com/privkey.pem;

    # 认证API (8081)
    location /api/auth/ {
        proxy_pass http://localhost:8081/api/auth/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 数据API (8082)
    location /api/data/ {
        proxy_pass http://localhost:8082/api/data/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 健康检查
    location /api/health {
        proxy_pass http://localhost:8082/api/health;
    }
}
```

### Nginx 管理命令
```bash
# 测试配置
sudo nginx -t

# 重新加载配置
sudo nginx -s reload
sudo systemctl reload nginx

# 重启Nginx
sudo systemctl restart nginx

# 查看错误日志
sudo tail -f /var/log/nginx/error.log

# 查看访问日志
sudo tail -f /var/log/nginx/access.log
```

---

## 🔒 SSL 证书管理

### Let's Encrypt 证书

```yaml
证书类型: Let's Encrypt (免费)
域名: api.genepop.com
证书路径: /etc/letsencrypt/live/api.genepop.com/
  - fullchain.pem (完整证书链)
  - privkey.pem (私钥)
有效期: 90天
自动续期: 是 (certbot定时任务)
```

### 证书管理命令

```bash
# 手动续期证书
sudo certbot renew

# 查看证书信息
sudo certbot certificates

# 强制续期
sudo certbot renew --force-renewal

# 续期后重新加载Nginx
sudo certbot renew && sudo systemctl reload nginx

# 查看certbot日志
sudo cat /var/log/letsencrypt/letsencrypt.log
```

### 自动续期任务

Certbot自动配置了systemd定时器:
```bash
# 查看定时器状态
sudo systemctl status certbot.timer

# 查看下次执行时间
sudo systemctl list-timers certbot
```

---

## 📦 阿里云 OSS 对象存储

### 基本信息
```yaml
Bucket名称: genetic-improve
区域: 华北2(北京) oss-cn-beijing.aliyuncs.com
访问权限: 公共读 (Public Read)
存储类型: 标准存储 (Standard)
套餐: 100GB 存储包
价格: ¥118.99/年
CDN加速: 未启用
```

### 访问地址
```
控制台: https://oss.console.aliyun.com/bucket/oss-cn-beijing/genetic-improve
外网访问: https://genetic-improve.oss-cn-beijing.aliyuncs.com
```

### 目录结构
```
genetic-improve/
├── releases/
│   ├── bull_library/
│   │   ├── bull_library.db (132MB, 247,192条记录)
│   │   └── bull_library_version.json
│   ├── v1.2.0.4/
│   │   ├── 伊利奶牛选配_v1.2.0.4_win.exe
│   │   ├── 伊利奶牛选配_v1.2.0.4_win.zip
│   │   └── 伊利奶牛选配_v1.2.0.4_mac.dmg
│   └── latest/
│       └── version.json
```

### OSS SDK 配置（Python）

```python
import oss2
import os

# 认证配置（从环境变量读取）
auth = oss2.Auth(
    access_key_id=os.getenv('OSS_ACCESS_KEY_ID'),
    access_key_secret=os.getenv('OSS_ACCESS_KEY_SECRET')
)

# 创建Bucket对象
bucket = oss2.Bucket(
    auth,
    'oss-cn-beijing.aliyuncs.com',
    'genetic-improve'
)

# 上传文件示例
bucket.put_object_from_file(
    'releases/bull_library/bull_library.db',
    '/path/to/local/bull_library.db'
)

# 下载文件示例
bucket.get_object_to_file(
    'releases/bull_library/bull_library.db',
    '/path/to/local/bull_library.db'
)
```

### 常用文件URL
```
# 数据库文件
https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/bull_library/bull_library.db

# 数据库版本信息
https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/bull_library/bull_library_version.json

# Windows安装包
https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.2.0.4/伊利奶牛选配_v1.2.0.4_win.exe
```

### 存储统计
```yaml
总存储量: ~500MB
主要文件:
  - bull_library.db: 132MB (数据库)
  - 应用安装包: ~250MB/版本

月度流量估算:
  - 下载流量: ~100GB (假设100个用户)
  - 上传流量: ~10MB (版本发布)
  - 流量费用: ~¥50/月
```

---

## 🗄️ 阿里云 PolarDB MySQL

### 基本信息
```yaml
实例类型: PolarDB MySQL
主库地址: defectgene-new.mysql.polardb.rds.aliyuncs.com
主库端口: 3306
公网IP: 8.147.221.122
内网IP: 172.x.x.x (ECS内网访问)
地域: 华北2(北京)
网络类型: 专有网络VPC
```

### 数据库连接

```bash
# 通过MySQL客户端连接
mysql -h defectgene-new.mysql.polardb.rds.aliyuncs.com \
      -P 3306 \
      -u defect_genetic_checking \
      -p'Jaybz@890411' \
      bull_library
```

### 数据库结构

```sql
-- 数据库
USE bull_library;

-- 核心表
SHOW TABLES;
/*
+------------------------+
| Tables_in_bull_library |
+------------------------+
| bull_library          |  -- 公牛遗传数据 (247,192条)
| id-pw                 |  -- 用户认证
| invitation_codes      |  -- 邀请码
| app_versions          |  -- 应用版本
| miss_bull             |  -- 缺失公牛记录
| report_push_logs      |  -- 报告推送日志
+------------------------+
*/

-- 查看公牛库记录数
SELECT COUNT(*) FROM bull_library;
-- 247192

-- 查看缺失公牛记录
SELECT * FROM miss_bull ORDER BY upload_time DESC LIMIT 10;
```

### Python连接示例

```python
import os
import pymysql

# 创建连接
connection = pymysql.connect(
    host='defectgene-new.mysql.polardb.rds.aliyuncs.com',
    port=3306,
    user='defect_genetic_checking',
    password=os.environ['BULL_LIBRARY_DB_PASSWORD'],
    database='bull_library',
    charset='utf8mb4'
)

try:
    with connection.cursor() as cursor:
        # 查询示例
        sql = "SELECT COUNT(*) FROM bull_library"
        cursor.execute(sql)
        result = cursor.fetchone()
        print(f"记录数: {result[0]}")
finally:
    connection.close()
```

### 访问控制
```yaml
白名单IP:
  - ECS服务器内网: 172.23.188.168
  - 其他授权IP: [如有需要添加]

数据库用户:
  - 用户名: defect_genetic_checking
  - 权限: SELECT, INSERT, UPDATE, DELETE
```

---

## 🌐 域名配置

### 域名信息
```yaml
主域名: genepop.com
注册商: [域名注册商]
到期时间: [记录到期时间]
```

### DNS记录
```
类型    主机记录    记录值
A       @          39.96.189.27
A       www        39.96.189.27
A       api        39.96.189.27
```

### 子域名配置
```yaml
www.genepop.com:
  - 指向: 39.96.189.27
  - 用途: 主站（未来）

api.genepop.com:
  - 指向: 39.96.189.27
  - 用途: API服务
  - SSL: Let's Encrypt
```

---

## 🔐 安全配置

### ECS 安全组规则

**入方向规则:**
```yaml
协议    端口范围    授权对象        说明
TCP     22         限制IP列表      SSH访问
TCP     80         0.0.0.0/0      HTTP (重定向到HTTPS)
TCP     443        0.0.0.0/0      HTTPS
```

**出方向规则:**
```yaml
协议    端口范围    授权对象        说明
ALL     ALL        0.0.0.0/0      允许所有出站流量
```

### 内部端口（仅localhost）
```yaml
8081: 认证API (仅localhost访问，通过Nginx反向代理)
8082: 数据API (仅localhost访问，通过Nginx反向代理)
```

### SSH 安全配置
```yaml
密码登录: 禁用
密钥认证: 启用
Root登录: 禁用
SSH端口: 22 (可考虑修改为非标准端口)
```

---

## 💰 成本统计

### 年度费用明细
```yaml
服务项目                    费用(年)      费用(月)
─────────────────────────────────────────
ECS服务器 (2核2GB)         ¥99          ¥8.25
域名 genepop.com           ¥55          ¥4.58
OSS存储 100GB              ¥118.99      ¥9.92
OSS流量 (估算)             ¥600         ¥50
PolarDB MySQL              ¥0*          ¥0
SSL证书 (Let's Encrypt)    ¥0           ¥0
─────────────────────────────────────────
总计                       ¥873         ¥72.75
```

*PolarDB为已有资源，不计入本项目成本

### 成本优化建议
```
1. OSS流量优化:
   - 启用CDN加速（可降低回源流量）
   - 设置缓存策略

2. ECS优化:
   - 考虑包年包月（更优惠）
   - 监控资源使用率，按需调整配置

3. 数据库优化:
   - 定期清理无用数据
   - 优化查询索引
```

---

## 📊 监控和日志

### 服务监控

```bash
# 查看系统资源使用
top
htop
df -h    # 磁盘使用
free -h  # 内存使用

# 查看服务状态
sudo systemctl status genetic-auth-api
sudo systemctl status genetic-data-api
sudo systemctl status nginx

# 查看端口监听
sudo netstat -tlnp | grep -E "8081|8082|80|443"
```

### 日志位置
```yaml
API服务日志:
  - journalctl -u genetic-auth-api
  - journalctl -u genetic-data-api

Nginx日志:
  - /var/log/nginx/access.log
  - /var/log/nginx/error.log

系统日志:
  - /var/log/syslog
  - /var/log/auth.log

SSL证书日志:
  - /var/log/letsencrypt/letsencrypt.log
```

### 阿里云监控
```
访问: https://cloudmonitor.console.aliyun.com/

监控指标:
  - ECS CPU使用率
  - ECS 内存使用率
  - ECS 磁盘使用率
  - ECS 网络流量
  - OSS 流量统计
  - OSS 存储量
```

---

## 🔧 常见运维任务

### 1. 部署新版本API
```bash
# 1. 连接服务器
ssh -i ~/Downloads/genetic_improvement.pem ecs-user@39.96.189.27

# 2. 备份当前版本
cd /home/ecs-user/api
cp data_api.py data_api.py.backup

# 3. 更新代码
git pull
# 或手动上传新文件

# 4. 重启服务
sudo systemctl restart genetic-data-api

# 5. 查看日志确认
sudo journalctl -u genetic-data-api -f
```

### 2. 更新数据库文件到OSS
```bash
# 使用OSS控制台上传
# 或使用ossutil命令行工具

# 1. 上传数据库文件
ossutil cp bull_library.db oss://genetic-improve/releases/bull_library/

# 2. 更新版本文件
ossutil cp bull_library_version.json oss://genetic-improve/releases/bull_library/
```

### 3. 续期SSL证书
```bash
# 自动续期（certbot定时器会自动执行）
# 手动续期（如需要）
sudo certbot renew
sudo systemctl reload nginx
```

### 4. 清理磁盘空间
```bash
# 查看磁盘使用
df -h

# 清理日志
sudo journalctl --vacuum-time=7d

# 清理apt缓存
sudo apt clean
sudo apt autoclean
```

---

## 📞 紧急联系

### 服务故障处理流程
```
1. 检查服务状态
   sudo systemctl status [服务名]

2. 查看日志
   sudo journalctl -u [服务名] -n 100

3. 尝试重启服务
   sudo systemctl restart [服务名]

4. 联系阿里云技术支持
   电话: 95187
   工单: https://workorder.console.aliyun.com/
```

---

最后更新: 2025-10-07
