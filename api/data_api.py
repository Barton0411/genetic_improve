#!/usr/bin/env python3
"""
数据API服务 - 处理所有数据库操作
完全API化架构，客户端不需要数据库密码
"""

import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any, List
import logging
import urllib.parse

# FastAPI imports
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pandas as pd
import jwt

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# JWT配置
JWT_SECRET = os.getenv('JWT_SECRET', 'genetic-improve-api-secret-key-production-2025')
JWT_ALGORITHM = 'HS256'

# 数据库配置 - 只在服务器端使用
DB_HOST = os.getenv('DB_HOST', 'defectgene-new.mysql.polardb.rds.aliyuncs.com')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER', 'defect_genetic_checking')
DB_PASSWORD = os.getenv('DB_PASSWORD')  # 必须从环境变量获取
DB_NAME = os.getenv('DB_NAME', 'bull_library')

# 创建FastAPI应用
app = FastAPI(title="伊利奶牛选配系统数据API", version="2.0.0")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 数据库连接 ====================

def get_db_engine():
    """获取数据库引擎"""
    if not DB_PASSWORD:
        raise ValueError("数据库密码未配置，请设置环境变量 DB_PASSWORD")

    db_password_encoded = urllib.parse.quote_plus(DB_PASSWORD)
    db_uri = f"mysql+pymysql://{DB_USER}:{db_password_encoded}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    return create_engine(db_uri, pool_pre_ping=True, pool_size=10, max_overflow=20)

# 初始化数据库引擎
try:
    engine = get_db_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("数据库引擎初始化成功")
except Exception as e:
    logger.error(f"数据库引擎初始化失败: {e}")
    engine = None

# ==================== JWT认证 ====================

def verify_token(authorization: str = Header(None)) -> Dict:
    """验证JWT令牌"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供有效的认证令牌")

    token = authorization.replace("Bearer ", "")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="令牌已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的令牌")

# ==================== 请求/响应模型 ====================

class APIResponse(BaseModel):
    """统一响应格式"""
    success: bool
    message: str = ""
    data: Optional[Dict[str, Any]] = None
    timestamp: int = None

    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = int(datetime.now().timestamp())
        super().__init__(**data)

class MissingBullRequest(BaseModel):
    """上传缺失公牛记录请求"""
    bulls: List[Dict[str, Any]]

class DatabaseVersionResponse(BaseModel):
    """数据库版本响应"""
    version: str
    update_time: str

# ==================== API端点 ====================

@app.get("/health")
async def health_check():
    """健康检查"""
    return APIResponse(
        success=True,
        message="数据API服务运行正常",
        data={
            "service": "data_api",
            "version": "2.0.0",
            "database": "connected" if engine else "disconnected"
        }
    )

@app.get("/api/data/version")
async def get_database_version(user=Depends(verify_token)):
    """获取数据库版本"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version, update_time FROM db_version ORDER BY id DESC LIMIT 1")).fetchone()

            if result:
                return APIResponse(
                    success=True,
                    data={
                        "version": result[0],
                        "update_time": str(result[1])
                    }
                )
            else:
                return APIResponse(
                    success=False,
                    message="版本信息不存在"
                )
    except Exception as e:
        logger.error(f"获取数据库版本失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data/bull_library")
async def get_bull_library(user=Depends(verify_token)):
    """获取公牛库数据"""
    try:
        query = "SELECT * FROM bull_library"
        df = pd.read_sql(query, engine)

        # 过滤表头行
        if 'BULL NAAB' in df.columns:
            df = df[df['BULL NAAB'] != 'BULL NAAB']

        # 转换为JSON格式
        data = df.to_dict(orient='records')

        return APIResponse(
            success=True,
            message=f"成功获取{len(data)}条公牛记录",
            data={
                "total": len(data),
                "records": data
            }
        )
    except Exception as e:
        logger.error(f"获取公牛库数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/data/missing_bulls")
async def upload_missing_bulls(request: MissingBullRequest, user=Depends(verify_token)):
    """上传缺失公牛记录"""
    try:
        if not request.bulls:
            return APIResponse(
                success=False,
                message="没有要上传的公牛记录"
            )

        # 转换为DataFrame
        df = pd.DataFrame(request.bulls)

        # 上传到数据库
        df.to_sql('miss_bull', engine, if_exists='append', index=False)

        logger.info(f"用户 {user.get('username')} 上传了 {len(request.bulls)} 条缺失公牛记录")

        return APIResponse(
            success=True,
            message=f"成功上传{len(request.bulls)}条缺失公牛记录",
            data={
                "uploaded_count": len(request.bulls)
            }
        )
    except Exception as e:
        logger.error(f"上传缺失公牛记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/data/sync_bull_library")
async def sync_bull_library(user=Depends(verify_token)):
    """同步公牛库数据（替代原check_and_update_database）"""
    try:
        # 获取云端数据
        query = "SELECT * FROM bull_library"
        df = pd.read_sql(query, engine)

        # 过滤表头行
        if 'BULL NAAB' in df.columns:
            initial_count = len(df)
            df = df[df['BULL NAAB'] != 'BULL NAAB']
            filtered_count = len(df)
            if initial_count != filtered_count:
                logger.info(f"过滤掉 {initial_count - filtered_count} 条表头记录")

        # 获取版本信息
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version FROM db_version ORDER BY id DESC LIMIT 1")).fetchone()
            version = result[0] if result else "1.0.0"

        return APIResponse(
            success=True,
            message=f"成功同步{len(df)}条公牛记录",
            data={
                "total_records": len(df),
                "version": version,
                "records": df.to_dict(orient='records')
            }
        )
    except Exception as e:
        logger.error(f"同步公牛库数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data/invitation_codes")
async def get_invitation_codes(user=Depends(verify_token)):
    """获取邀请码列表（管理员功能）"""
    try:
        query = """
            SELECT id, code, status, max_uses, current_uses, expire_time
            FROM invitation_codes
            ORDER BY id DESC
        """
        df = pd.read_sql(query, engine)

        return APIResponse(
            success=True,
            data={
                "codes": df.to_dict(orient='records')
            }
        )
    except Exception as e:
        logger.error(f"获取邀请码列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 主程序入口 ====================

if __name__ == "__main__":
    import uvicorn

    # 检查数据库密码
    if not DB_PASSWORD:
        logger.error("错误：未设置数据库密码环境变量 DB_PASSWORD")
        sys.exit(1)

    # 测试数据库连接
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("数据库连接测试成功")
    except Exception as e:
        logger.error(f"数据库连接测试失败: {e}")
        sys.exit(1)

    # 启动服务
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8082,
        log_level="info"
    )