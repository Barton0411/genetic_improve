#!/usr/bin/env python3
"""
自动化部署脚本 - 部署认证API服务到生产服务器
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

# 服务器配置
SERVER_HOST = "39.96.189.27"
SERVER_USER = "ecs-user"
SSH_KEY = "~/Downloads/genetic_improvement.pem"

def run_local_command(command, description=None):
    """执行本地命令"""
    if description:
        print(f"🔧 {description}")

    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ 命令执行失败: {command}")
            print(f"错误输出: {result.stderr}")
            return False
        print(f"✅ {description or '命令执行成功'}")
        return True
    except Exception as e:
        print(f"❌ 执行命令时出错: {e}")
        return False

def run_ssh_command(command, description=None):
    """通过SSH执行远程命令"""
    if description:
        print(f"🔧 {description}")

    ssh_command = f'ssh -i {SSH_KEY} {SERVER_USER}@{SERVER_HOST} "{command}"'

    try:
        result = subprocess.run(ssh_command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ SSH命令执行失败: {command}")
            print(f"错误输出: {result.stderr}")
            return False
        print(f"✅ {description or 'SSH命令执行成功'}")
        if result.stdout.strip():
            print(f"输出: {result.stdout.strip()}")
        return True
    except Exception as e:
        print(f"❌ 执行SSH命令时出错: {e}")
        return False

def copy_file_to_server(local_path, remote_path, description=None):
    """复制文件到服务器"""
    if description:
        print(f"📋 {description}")

    scp_command = f'scp -i {SSH_KEY} "{local_path}" {SERVER_USER}@{SERVER_HOST}:{remote_path}'

    try:
        result = subprocess.run(scp_command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ 文件复制失败: {local_path} -> {remote_path}")
            print(f"错误输出: {result.stderr}")
            return False
        print(f"✅ {description or '文件复制成功'}")
        return True
    except Exception as e:
        print(f"❌ 复制文件时出错: {e}")
        return False

def deploy_auth_api():
    """部署认证API服务"""
    print("🚀 开始部署认证API服务到生产服务器")
    print("="*60)

    # 1. 检查本地文件
    project_root = Path(__file__).parent.parent
    auth_api_file = project_root / "api" / "auth_api.py"

    if not auth_api_file.exists():
        print(f"❌ 认证API文件不存在: {auth_api_file}")
        return False

    print(f"✅ 找到认证API文件: {auth_api_file}")

    # 2. 测试SSH连接
    if not run_ssh_command("echo 'SSH连接测试'", "测试SSH连接"):
        print("❌ 无法连接到服务器，请检查SSH密钥和网络连接")
        return False

    # 3. 创建服务目录
    if not run_ssh_command("mkdir -p ~/genetic_improve_auth", "创建服务目录"):
        return False

    # 4. 复制认证API文件
    if not copy_file_to_server(auth_api_file, "~/genetic_improve_auth/auth_api.py", "复制认证API文件"):
        return False

    # 5. 创建环境变量文件
    env_content = '''# 数据库配置
DB_HOST=defectgene-new.mysql.polardb.rds.aliyuncs.com
DB_PORT=3306
DB_USER=defect_genetic_checking
DB_PASSWORD=\${DB_PASSWORD:-"请设置环境变量"}
DB_NAME=bull_library

# JWT配置
JWT_SECRET=genetic-improve-api-secret-key-production-2025
JWT_ALGORITHM=HS256

# 服务配置
API_HOST=0.0.0.0
API_PORT=8081
'''

    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write(env_content)
        temp_env_file = f.name

    try:
        if not copy_file_to_server(temp_env_file, "~/genetic_improve_auth/.env", "复制环境变量文件"):
            return False
    finally:
        os.unlink(temp_env_file)

    # 6. 设置文件权限
    if not run_ssh_command("chmod 600 ~/genetic_improve_auth/.env", "设置环境变量文件权限"):
        return False

    # 7. 安装Python依赖
    print(f"📦 安装Python依赖...")
    commands = [
        "cd ~/genetic_improve_auth",
        "python3 -m venv venv",
        "source venv/bin/activate",
        "pip install --upgrade pip",
        "pip install fastapi uvicorn sqlalchemy pymysql pyjwt python-multipart"
    ]

    if not run_ssh_command(" && ".join(commands), "安装Python依赖"):
        return False

    # 8. 创建systemd服务文件
    service_content = '''[Unit]
Description=Genetic Improve Auth API Service
After=network.target

[Service]
Type=simple
User=ecs-user
WorkingDirectory=/home/ecs-user/genetic_improve_auth
Environment=PATH=/home/ecs-user/genetic_improve_auth/venv/bin
EnvironmentFile=/home/ecs-user/genetic_improve_auth/.env
ExecStart=/home/ecs-user/genetic_improve_auth/venv/bin/uvicorn auth_api:app --host 0.0.0.0 --port 8081 --workers 2
Restart=always
RestartSec=3

# 安全设置
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/ecs-user/genetic_improve_auth

[Install]
WantedBy=multi-user.target
'''

    # 创建临时服务文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.service', delete=False) as f:
        f.write(service_content)
        temp_service_file = f.name

    try:
        if not copy_file_to_server(temp_service_file, "~/genetic-auth-api.service", "复制systemd服务文件"):
            return False
    finally:
        os.unlink(temp_service_file)

    # 9. 安装和启动服务
    service_commands = [
        "sudo mv ~/genetic-auth-api.service /etc/systemd/system/",
        "sudo systemctl daemon-reload",
        "sudo systemctl enable genetic-auth-api",
        "sudo systemctl stop genetic-auth-api || true",  # 停止已存在的服务
        "sudo systemctl start genetic-auth-api"
    ]

    for cmd in service_commands:
        if not run_ssh_command(cmd, f"执行: {cmd.split()[-1]}"):
            return False

    # 10. 检查服务状态
    print(f"📊 检查服务状态...")
    run_ssh_command("sudo systemctl status genetic-auth-api --no-pager -l", "查看服务状态")

    # 11. 测试API
    print(f"🧪 测试API服务...")
    run_ssh_command("sleep 3 && curl -s http://localhost:8081/health | python3 -m json.tool || echo 'API测试失败'", "测试API健康检查")

    # 12. 配置Nginx (如果需要)
    nginx_config = '''
# 添加到现有的 server 块中
location /api/auth/ {
    proxy_pass http://localhost:8081;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 10s;
    proxy_send_timeout 30s;
    proxy_read_timeout 30s;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
}

location /health {
    proxy_pass http://localhost:8081;
    proxy_set_header Host $host;
    access_log off;
}
'''

    print("\n" + "="*60)
    print("🎉 认证API服务部署完成！")
    print("="*60)
    print("\n📋 部署信息:")
    print("  - 服务名称: genetic-auth-api")
    print("  - 服务端口: 8081")
    print("  - 服务目录: /home/ecs-user/genetic_improve_auth")
    print("\n🔧 管理命令:")
    print("  - 查看状态: sudo systemctl status genetic-auth-api")
    print("  - 重启服务: sudo systemctl restart genetic-auth-api")
    print("  - 查看日志: sudo journalctl -u genetic-auth-api -f")
    print("\n🌐 下一步操作:")
    print("1. 手动配置Nginx路由 (将以下配置添加到现有server块):")
    print(nginx_config)
    print("2. 重载Nginx: sudo nginx -t && sudo systemctl reload nginx")
    print("3. 测试完整API: https://api.genepop.com/health")

    return True

if __name__ == "__main__":
    try:
        success = deploy_auth_api()
        if success:
            print("\n✅ 部署成功完成！")
            sys.exit(0)
        else:
            print("\n❌ 部署过程中出现错误")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ 部署被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 部署过程中发生未知错误: {e}")
        sys.exit(1)