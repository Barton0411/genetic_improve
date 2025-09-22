#!/usr/bin/env python3
"""
Mac连接测试脚本
用于诊断Mac上的网络连接问题
"""

import sys
import os
import logging
import platform
from pathlib import Path

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("=" * 60)
print("Mac连接测试脚本")
print("=" * 60)
print(f"Python版本: {sys.version}")
print(f"平台: {platform.system()} {platform.release()}")
print(f"是否打包应用: {getattr(sys, 'frozen', False)}")
print("=" * 60)

# 测试1: 检查网络基本连接
print("\n[测试1] 检查基本网络连接...")
import socket
try:
    # 尝试解析域名
    ip = socket.gethostbyname('api.genepop.com')
    print(f"✓ 域名解析成功: api.genepop.com -> {ip}")
except Exception as e:
    print(f"✗ 域名解析失败: {e}")

try:
    # 尝试解析IP
    ip = socket.gethostbyname('39.96.189.27')
    print(f"✓ IP地址可达: 39.96.189.27")
except Exception as e:
    print(f"✗ IP地址不可达: {e}")

# 测试2: 使用urllib测试HTTP连接
print("\n[测试2] 使用urllib测试HTTP连接...")
import urllib.request
import ssl

urls_to_test = [
    ('http://39.96.189.27:8081/api/health', 'HTTP+IP'),
    ('https://api.genepop.com/api/health', 'HTTPS+域名'),
]

for url, desc in urls_to_test:
    print(f"\n测试 {desc}: {url}")
    try:
        # 创建不验证证书的上下文
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'GeneticImprove-Test/1.0')

        if url.startswith('https'):
            response = urllib.request.urlopen(req, timeout=10, context=ctx)
        else:
            response = urllib.request.urlopen(req, timeout=10)

        print(f"✓ 连接成功, 状态码: {response.getcode()}")
        content = response.read().decode('utf-8')
        print(f"  响应内容前100字符: {content[:100]}")
    except Exception as e:
        print(f"✗ 连接失败: {type(e).__name__}: {e}")

# 测试3: 使用requests测试连接
print("\n[测试3] 使用requests测试连接...")
try:
    import requests
    print("✓ requests模块已安装")

    # 禁用SSL警告
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    session = requests.Session()
    session.trust_env = False  # 不使用系统代理

    for url, desc in urls_to_test:
        print(f"\n测试 {desc}: {url}")
        try:
            response = session.get(url, timeout=10, verify=False)
            print(f"✓ 连接成功, 状态码: {response.status_code}")
            print(f"  响应内容前100字符: {response.text[:100]}")
        except Exception as e:
            print(f"✗ 连接失败: {type(e).__name__}: {e}")

except ImportError:
    print("✗ requests模块未安装")

# 测试4: 检查系统代理设置
print("\n[测试4] 检查系统代理设置...")
proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NO_PROXY', 'no_proxy']
for var in proxy_vars:
    value = os.environ.get(var)
    if value:
        print(f"  {var} = {value}")
if not any(os.environ.get(var) for var in proxy_vars):
    print("  没有设置系统代理")

# 测试5: 检查防火墙和安全设置
print("\n[测试5] 检查安全设置...")
if platform.system() == 'Darwin':
    # Mac特定检查
    import subprocess
    try:
        # 检查防火墙状态
        result = subprocess.run(['sudo', '-n', 'pfctl', '-s', 'info'],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            print("  防火墙状态可查询")
        else:
            print("  需要sudo权限查看防火墙状态")
    except:
        print("  无法检查防火墙状态")

    # 检查是否有网络限制
    try:
        result = subprocess.run(['scutil', '--proxy'],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            print("  系统代理配置:")
            for line in result.stdout.split('\n')[:10]:
                if line.strip():
                    print(f"    {line}")
    except:
        print("  无法检查系统代理配置")

# 测试6: 测试API客户端
print("\n[测试6] 测试API客户端...")
try:
    # 添加项目路径
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))

    from api.api_client import APIClient

    print("✓ API客户端模块导入成功")

    # 创建客户端实例
    client = APIClient()
    print(f"  Base URL: {client.base_url}")
    print(f"  Timeout: {client.timeout}s")
    print(f"  SSL Verify: {client.verify_ssl}")

    # 测试健康检查
    print("\n  执行健康检查...")
    success, message = client.health_check()
    if success:
        print(f"  ✓ 健康检查成功: {message}")
    else:
        print(f"  ✗ 健康检查失败: {message}")

except Exception as e:
    print(f"✗ API客户端测试失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")
print("日志文件位置: ~/.genetic_improve/app_debug.log")
print("=" * 60)