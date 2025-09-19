#!/bin/bash

# 数据API服务部署脚本
# 完全API化 - 处理所有数据库操作

echo "==================== 部署数据API服务 ===================="

# 检查环境变量
if [ -z "$DB_PASSWORD" ]; then
    echo "错误：请设置环境变量 DB_PASSWORD"
    echo "export DB_PASSWORD='your_actual_password'"
    exit 1
fi

# 创建API目录
mkdir -p ~/api

# 安装Python依赖
echo "安装依赖包..."
pip3 install fastapi uvicorn PyJWT sqlalchemy pymysql pandas

# 创建systemd服务文件
echo "创建systemd服务..."
sudo tee /etc/systemd/system/genetic-data-api.service > /dev/null <<EOF
[Unit]
Description=Genetic Improve Data API Service
After=network.target

[Service]
Type=simple
User=ecs-user
WorkingDirectory=/home/ecs-user
Environment="DB_HOST=defectgene-new.mysql.polardb.rds.aliyuncs.com"
Environment="DB_PORT=3306"
Environment="DB_USER=defect_genetic_checking"
Environment="DB_PASSWORD=$DB_PASSWORD"
Environment="DB_NAME=bull_library"
Environment="JWT_SECRET=genetic-improve-api-secret-key-production-2025"
ExecStart=/usr/bin/python3 /home/ecs-user/api/data_api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 重新加载systemd
sudo systemctl daemon-reload

# 启动服务
echo "启动数据API服务..."
sudo systemctl start genetic-data-api
sudo systemctl enable genetic-data-api

# 配置Nginx
echo "配置Nginx路由..."
sudo tee -a /etc/nginx/sites-available/default > /dev/null <<'NGINX'

    # 数据API路由 (端口8082)
    location /api/data/ {
        proxy_pass http://localhost:8082;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
NGINX

# 测试Nginx配置
sudo nginx -t

# 重载Nginx
sudo systemctl reload nginx

# 检查服务状态
echo "==================== 服务状态 ===================="
sudo systemctl status genetic-data-api --no-pager

# 测试API
echo "==================== 测试API ===================="
sleep 3
curl -s http://localhost:8082/health | python3 -m json.tool

echo "==================== 部署完成 ===================="
echo "数据API服务已部署在: https://api.genepop.com/api/data/*"
echo "健康检查: https://api.genepop.com/api/data/health"
echo ""
echo "客户端配置："
echo "1. 确保已登录获取JWT令牌"
echo "2. 所有数据库操作将自动通过API进行"
echo "3. 不再需要数据库密码"