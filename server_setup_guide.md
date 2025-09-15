# 正确的服务器配置指南

## 第一步：获取SSH访问权限

### 联系服务商
致电亿速云客服：400-100-2938

**说明需求：**
```
我购买的服务器需要用于部署Web应用，不需要远程桌面。

请提供：
1. 服务器SSH登录信息
   - IP地址
   - SSH端口（通常是22）
   - Root用户密码
2. 关闭向日葵远程桌面服务
3. 开放网络端口：22, 80, 443, 6080-6090
4. 安装纯净的Ubuntu 22.04系统（无桌面环境）
```

## 第二步：SSH连接服务器

### 从您的Mac连接
```bash
# 连接服务器
ssh root@YOUR_SERVER_IP

# 首次连接会提示确认，输入 yes
# 然后输入密码
```

### 验证服务器信息
```bash
# 查看系统信息
cat /etc/os-release

# 查看硬件配置
free -h                 # 内存
nproc                   # CPU核心数
df -h                   # 磁盘空间
ip addr show            # 网络信息
```

## 第三步：基础环境配置

### 系统更新
```bash
apt update && apt upgrade -y
```

### 安装必要软件
```bash
# Docker环境
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 其他工具
apt install -y nginx git htop tree unzip
```

### 配置防火墙
```bash
# Ubuntu防火墙配置
ufw allow 22            # SSH
ufw allow 80            # HTTP
ufw allow 443           # HTTPS
ufw allow 6080:6090/tcp # noVNC端口范围
ufw enable
```

## 第四步：上传和部署应用

### 方法1：Git方式（推荐）
```bash
# 克隆代码到服务器
cd /opt
git clone https://github.com/yourusername/genetic_improve.git
cd genetic_improve

# 执行部署
chmod +x deploy.sh
./deploy.sh
```

### 方法2：文件上传方式
```bash
# 在您的Mac上，打包代码
cd /Users/bozhenwang/projects/mating/genetic_improve
tar -czf genetic_improve.tar.gz .

# 上传到服务器
scp genetic_improve.tar.gz root@YOUR_SERVER_IP:/opt/

# 在服务器上解压和部署
ssh root@YOUR_SERVER_IP
cd /opt
tar -xzf genetic_improve.tar.gz
cd genetic_improve
./deploy.sh
```

## 第五步：访问应用

### Web界面访问
- 主地址：https://YOUR_SERVER_IP
- 实例1：http://YOUR_SERVER_IP:6080
- 实例2：http://YOUR_SERVER_IP:6081
- 实例3：http://YOUR_SERVER_IP:6082

### 验证部署成功
```bash
# 检查服务状态
docker-compose ps

# 查看日志
docker-compose logs -f app1

# 测试访问
curl http://localhost:6080
```

## 常见问题解决

### 1. 向日葵无法关闭
```bash
# 查找向日葵进程
ps aux | grep sunlogin

# 强制关闭
pkill -f sunlogin

# 禁用自动启动
systemctl disable sunloginclient
systemctl stop sunloginclient
```

### 2. 端口被占用
```bash
# 查看端口占用
netstat -tlnp | grep :80

# 关闭占用进程
kill -9 PROCESS_ID
```

### 3. Docker权限问题
```bash
# 将用户加入docker组
usermod -aG docker $USER

# 重新登录或执行
newgrp docker
```

## 对比：错误 vs 正确的方式

| 方面 | 向日葵方式（❌） | 正确方式（✅） |
|------|-----------------|---------------|
| 并发用户 | 1-2人 | 50+人 |
| 性能 | 延迟高、卡顿 | 流畅响应 |
| 安全性 | 第三方依赖 | 直接连接 |
| 稳定性 | 经常断线 | 24/7稳定 |
| 扩展性 | 无法扩展 | 容器化扩展 |
| 成本 | 资源浪费 | 资源优化 |

## 总结

**向日葵只是临时的管理工具，不是生产环境的解决方案。**

正确的流程应该是：
1. SSH连接服务器
2. 安装Docker环境  
3. 部署容器化应用
4. 通过Web界面访问

这样才能真正发挥服务器的性能和稳定性。