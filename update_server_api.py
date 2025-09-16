#!/usr/bin/env python3
"""
更新服务器API代码，支持强制更新字段
"""

SERVER_API_CODE = '''#!/usr/bin/env python3
"""
版本管理API服务器 - 增强版，支持强制更新
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pymysql
import json
from datetime import datetime, date
import uvicorn
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Genetic Improve Version API", version="1.1.0")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据库配置
DB_CONFIG = {
    'host': 'defectgene-new.mysql.polardb.rds.aliyuncs.com',
    'port': 3306,
    'user': 'defect_genetic_checking',
    'password': 'Jaybz@890411',
    'database': 'bull_library',
    'charset': 'utf8mb4'
}

def get_db_connection():
    """获取数据库连接"""
    try:
        return pymysql.connect(**DB_CONFIG)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

class DateTimeEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理datetime对象"""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        return super().default(obj)

@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "service": "version-api", "version": "1.1.0"}

@app.get("/api/version/latest")
async def get_latest_version():
    """获取最新版本信息 - 支持强制更新"""
    connection = get_db_connection()
    try:
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # 查询最新版本，包含所有字段
        query = """
        SELECT id, version, release_date, is_latest, changes, 
               mac_download_url, win_download_url, linux_download_url,
               force_update, security_update, min_supported_version,
               package_size, mac_md5, win_md5, created_at, updated_at
        FROM app_versions 
        WHERE is_latest = 1 
        ORDER BY created_at DESC 
        LIMIT 1
        """
        
        cursor.execute(query)
        version_data = cursor.fetchone()
        
        if not version_data:
            raise HTTPException(status_code=404, detail="No version found")
        
        # 处理changes字段（可能是JSON字符串）
        changes = version_data.get('changes', '')
        if changes:
            try:
                # 尝试解析JSON
                changes_list = json.loads(changes)
                if isinstance(changes_list, list):
                    version_data['changes'] = changes_list
                else:
                    version_data['changes'] = [changes]
            except (json.JSONDecodeError, TypeError):
                # 如果不是JSON，按行分割
                version_data['changes'] = [line.strip() for line in changes.split('\\n') if line.strip()]
        else:
            version_data['changes'] = []
        
        # 确保布尔字段的类型正确
        version_data['is_latest'] = bool(version_data.get('is_latest', 0))
        version_data['force_update'] = bool(version_data.get('force_update', 0))
        version_data['security_update'] = bool(version_data.get('security_update', 0))
        
        # 处理None值
        for key, value in version_data.items():
            if value is None:
                version_data[key] = ""
        
        cursor.close()
        
        response = {
            "success": True,
            "data": version_data
        }
        
        # 使用自定义编码器处理datetime
        return json.loads(json.dumps(response, cls=DateTimeEncoder))
        
    except Exception as e:
        logger.error(f"Get latest version failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connection.close()

@app.get("/api/version/{version}")
async def get_version_info(version: str):
    """获取指定版本信息"""
    connection = get_db_connection()
    try:
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        query = """
        SELECT id, version, release_date, is_latest, changes, 
               mac_download_url, win_download_url, linux_download_url,
               force_update, security_update, min_supported_version,
               package_size, mac_md5, win_md5, created_at, updated_at
        FROM app_versions 
        WHERE version = %s
        """
        
        cursor.execute(query, (version,))
        version_data = cursor.fetchone()
        
        if not version_data:
            raise HTTPException(status_code=404, detail=f"Version {version} not found")
        
        # 处理changes字段
        changes = version_data.get('changes', '')
        if changes:
            try:
                changes_list = json.loads(changes)
                version_data['changes'] = changes_list
            except:
                version_data['changes'] = [line.strip() for line in changes.split('\\n') if line.strip()]
        
        # 确保布尔字段类型
        version_data['is_latest'] = bool(version_data.get('is_latest', 0))
        version_data['force_update'] = bool(version_data.get('force_update', 0))
        version_data['security_update'] = bool(version_data.get('security_update', 0))
        
        cursor.close()
        
        response = {
            "success": True,
            "data": version_data
        }
        
        return json.loads(json.dumps(response, cls=DateTimeEncoder))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get version info failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connection.close()

@app.get("/api/versions")
async def list_versions():
    """获取所有版本列表"""
    connection = get_db_connection()
    try:
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        query = """
        SELECT version, release_date, is_latest, force_update, security_update
        FROM app_versions 
        ORDER BY created_at DESC
        """
        
        cursor.execute(query)
        versions = cursor.fetchall()
        
        for version in versions:
            version['is_latest'] = bool(version.get('is_latest', 0))
            version['force_update'] = bool(version.get('force_update', 0))
            version['security_update'] = bool(version.get('security_update', 0))
        
        cursor.close()
        
        response = {
            "success": True,
            "data": versions
        }
        
        return json.loads(json.dumps(response, cls=DateTimeEncoder))
        
    except Exception as e:
        logger.error(f"List versions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connection.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''

def update_server_api():
    """更新服务器API代码"""
    print("🚀 准备更新服务器端API代码...")
    
    # 将更新的API代码保存到文件
    with open('/tmp/updated_api_server.py', 'w', encoding='utf-8') as f:
        f.write(SERVER_API_CODE)
    
    print("✅ 更新的API代码已保存到 /tmp/updated_api_server.py")
    print()
    print("📋 下一步操作（需要手动执行）:")
    print("1. 将此文件上传到服务器:")
    print("   scp /tmp/updated_api_server.py ecs-user@39.96.189.27:/home/ecs-user/api_server.py")
    print()
    print("2. 重启API服务:")
    print("   ssh ecs-user@39.96.189.27 'sudo systemctl restart genetic-api'")
    print()
    print("3. 检查服务状态:")
    print("   ssh ecs-user@39.96.189.27 'sudo systemctl status genetic-api'")
    
    return True

if __name__ == '__main__':
    update_server_api()