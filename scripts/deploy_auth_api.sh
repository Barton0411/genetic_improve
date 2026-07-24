#!/bin/bash
# 认证API服务部署脚本
# 用于在服务器上部署认证API服务

set -e  # 遇到错误立即退出

echo "==================== 认证API服务部署脚本 ===================="

# 敏感值只从调用环境读取，不写入脚本或 Git 历史。
: "${DB_PASSWORD:?请先通过安全凭据存储设置 DB_PASSWORD}"
: "${JWT_SECRET:?请先通过安全凭据存储设置 JWT_SECRET}"
if [[ "${DB_PASSWORD}${JWT_SECRET}" == *$'\n'* || "${DB_PASSWORD}${JWT_SECRET}" == *$'\r'* ]]; then
    echo "错误：敏感环境变量不能包含换行符"
    exit 1
fi

# 配置变量
SERVICE_NAME="genetic-auth-api"
SERVICE_PORT="8081"
SERVICE_USER="ecs-user"
SERVICE_DIR="/home/${SERVICE_USER}/genetic_improve_auth"
PYTHON_ENV="${SERVICE_DIR}/venv"

# 检查是否在服务器上运行
if [[ $(whoami) != "${SERVICE_USER}" ]]; then
    echo "⚠️  警告: 建议使用 ${SERVICE_USER} 用户运行此脚本"
fi

# 1. 创建服务目录
echo "📁 创建服务目录..."
mkdir -p "${SERVICE_DIR}"
cd "${SERVICE_DIR}"

# 2. 复制API文件
echo "📋 复制API服务文件..."
if [[ -f "auth_api.py" ]]; then
    echo "auth_api.py 已存在，备份旧版本..."
    mv auth_api.py auth_api.py.backup.$(date +%Y%m%d_%H%M%S)
fi

# 这里需要手动复制 api/auth_api.py 文件到服务器
echo "请手动将以下文件复制到 ${SERVICE_DIR}:"
echo "  - api/auth_api.py"
echo "  - requirements.txt (可选，用于安装依赖)"

# 3. 设置环境变量
echo "🔧 配置环境变量..."
cat > "${SERVICE_DIR}/.env" << EOF
# 数据库配置 - 从hardcoded迁移而来
DB_HOST=defectgene-new.mysql.polardb.rds.aliyuncs.com
DB_PORT=3306
DB_USER=defect_genetic_checking
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=bull_library

# JWT配置
JWT_SECRET=${JWT_SECRET}
JWT_ALGORITHM=HS256

# 服务配置
API_HOST=0.0.0.0
API_PORT=8081
EOF

# 设置文件权限（仅所有者可读）
chmod 600 "${SERVICE_DIR}/.env"
echo "✅ 环境变量配置完成（${SERVICE_DIR}/.env）"

# 4. 创建虚拟环境（如果不存在）
if [[ ! -d "${PYTHON_ENV}" ]]; then
    echo "🐍 创建Python虚拟环境..."
    python3 -m venv "${PYTHON_ENV}"
fi

# 5. 激活虚拟环境并安装依赖
echo "📦 安装Python依赖..."
source "${PYTHON_ENV}/bin/activate"
pip install --upgrade pip
pip install fastapi uvicorn sqlalchemy pymysql pyjwt python-multipart

# 6. 创建systemd服务文件
echo "⚙️  创建systemd服务..."
sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" > /dev/null << EOF
[Unit]
Description=Genetic Improve Auth API Service
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${SERVICE_DIR}
Environment=PATH=${PYTHON_ENV}/bin
EnvironmentFile=${SERVICE_DIR}/.env
ExecStart=${PYTHON_ENV}/bin/uvicorn auth_api:app --host 0.0.0.0 --port ${SERVICE_PORT} --workers 2
Restart=always
RestartSec=3

# 安全设置
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${SERVICE_DIR}

[Install]
WantedBy=multi-user.target
EOF

# 7. 创建Nginx配置
echo "🌐 配置Nginx路由..."
NGINX_CONFIG="/etc/nginx/sites-available/genetic-improve-auth"
sudo tee "${NGINX_CONFIG}" > /dev/null << 'EOF'
# 认证API路由配置
location /api/auth/ {
    proxy_pass http://localhost:8081;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # 超时设置
    proxy_connect_timeout 10s;
    proxy_send_timeout 30s;
    proxy_read_timeout 30s;

    # 安全头
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
}

# 健康检查
location /health {
    proxy_pass http://localhost:8081;
    proxy_set_header Host $host;
    access_log off;
}
EOF

# 8. 重新加载systemd和启动服务
echo "🔄 重新加载systemd配置..."
sudo systemctl daemon-reload

echo "🚀 启动认证API服务..."
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl start "${SERVICE_NAME}"

# 9. 检查服务状态
echo "📊 检查服务状态..."
sleep 3
sudo systemctl status "${SERVICE_NAME}" --no-pager -l

# 10. 测试API
echo "🧪 测试API服务..."
if command -v curl &> /dev/null; then
    echo "测试健康检查接口..."
    curl -s "http://localhost:${SERVICE_PORT}/health" | python3 -m json.tool || echo "API未正常响应"
else
    echo "curl未安装，跳过API测试"
fi

# 11. 显示部署信息
echo ""
echo "==================== 部署完成 ===================="
echo "✅ 认证API服务已部署完成"
echo ""
echo "📋 服务信息:"
echo "  - 服务名称: ${SERVICE_NAME}"
echo "  - 服务端口: ${SERVICE_PORT}"
echo "  - 服务目录: ${SERVICE_DIR}"
echo "  - 环境变量: ${SERVICE_DIR}/.env"
echo ""
echo "🔧 管理命令:"
echo "  - 查看状态: sudo systemctl status ${SERVICE_NAME}"
echo "  - 启动服务: sudo systemctl start ${SERVICE_NAME}"
echo "  - 停止服务: sudo systemctl stop ${SERVICE_NAME}"
echo "  - 重启服务: sudo systemctl restart ${SERVICE_NAME}"
echo "  - 查看日志: sudo journalctl -u ${SERVICE_NAME} -f"
echo ""
echo "🌐 API访问地址:"
echo "  - 健康检查: https://api.genepop.com/health"
echo "  - 登录接口: https://api.genepop.com/api/auth/login"
echo "  - 注册接口: https://api.genepop.com/api/auth/register"
echo ""
echo "⚠️  下一步操作:"
echo "1. 将 api/auth_api.py 文件复制到 ${SERVICE_DIR}/"
echo "2. 更新Nginx主配置文件，包含认证路由"
echo "3. 重新加载Nginx配置: sudo nginx -t && sudo systemctl reload nginx"
echo "4. 测试完整API流程"

echo "==================== 脚本执行结束 ===================="
