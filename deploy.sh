#!/bin/bash

# 遗传改良系统部署脚本
# 使用方法: ./deploy.sh

set -e

echo "=== 遗传改良系统部署开始 ==="

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "安装Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

# 检查Docker Compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "安装Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# 创建必要的目录
echo "创建项目目录..."
mkdir -p {data,projects,nginx/ssl,logs}

# 设置权限
chmod -R 755 data projects
chmod -R 644 nginx/

# 生成SSL证书（自签名，生产环境请使用正式证书）
if [ ! -f nginx/ssl/cert.pem ]; then
    echo "生成SSL证书..."
    openssl req -x509 -newkey rsa:4096 -keyout nginx/ssl/key.pem -out nginx/ssl/cert.pem -days 365 -nodes \
        -subj "/C=CN/ST=State/L=City/O=Organization/CN=localhost"
fi

# 更新nginx配置中的域名
read -p "请输入您的域名 (留空使用localhost): " DOMAIN
DOMAIN=${DOMAIN:-localhost}
sed -i "s/your-domain.com/$DOMAIN/g" nginx/nginx.conf

# 构建镜像
echo "构建Docker镜像..."
docker-compose build

# 启动服务
echo "启动服务..."
docker-compose up -d

# 等待服务启动
echo "等待服务启动..."
sleep 30

# 检查服务状态
echo "检查服务状态..."
docker-compose ps

# 显示访问信息
echo ""
echo "=== 部署完成 ==="
echo "应用访问地址:"
echo "- HTTPS: https://$DOMAIN"
echo "- HTTP: http://$DOMAIN"
echo ""
echo "应用实例直接访问:"
for i in {1..5}; do
    port=$((6079+i))
    echo "- 实例$i: http://$DOMAIN:$port"
done
echo ""
echo "管理命令:"
echo "- 查看日志: docker-compose logs -f"
echo "- 重启服务: docker-compose restart"
echo "- 停止服务: docker-compose down"
echo "- 更新应用: git pull && docker-compose build && docker-compose up -d"
echo ""
echo "监控地址:"
echo "- 系统状态: https://$DOMAIN/health"
echo "- Redis状态: docker-compose exec redis redis-cli ping"
echo ""

# 设置定时备份
echo "设置定时备份..."
cat > /etc/cron.d/genetic-improve-backup << EOF
# 每天凌晨3点备份数据
0 3 * * * root cd $(pwd) && tar -czf backup/genetic-improve-\$(date +%Y%m%d).tar.gz data projects
# 每周日清理30天前的备份
0 4 * * 0 root find $(pwd)/backup -name "*.tar.gz" -mtime +30 -delete
EOF

mkdir -p backup

echo "部署完成！请访问 https://$DOMAIN 使用应用。"