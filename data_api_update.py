#!/usr/bin/env python3
"""
数据API服务 - 处理所有数据库操作
完全API化架构，客户端不需要数据库密码
更新：移除认证要求，简化API调用
"""

import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any, List
import logging
import urllib.parse

# FastAPI imports
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pandas as pd

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# ==================== 请求/响应模型 ====================
# 注意：数据API不需要认证，方便下载公牛数据库和上传缺失记录

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
async def get_database_version():
    """获取数据库版本（无需认证）"""
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
async def get_bull_library():
    """获取公牛库数据（无需认证）"""
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
async def upload_missing_bulls(request: MissingBullRequest):
    """上传缺失公牛记录（无需认证）"""
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

        logger.info(f"上传了 {len(request.bulls)} 条缺失公牛记录")

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

# ==================== 管理端点 ====================

@app.get("/api/data/stats")
async def get_statistics():
    """获取数据统计（无需认证）"""
    try:
        with engine.connect() as conn:
            # 统计公牛数量
            bull_count = conn.execute(text("SELECT COUNT(*) FROM bull_library")).fetchone()[0]

            # 统计缺失公牛数量
            missing_count = conn.execute(text("SELECT COUNT(*) FROM miss_bull")).fetchone()[0]

            # 获取最新更新时间
            version_info = conn.execute(text("SELECT version, update_time FROM db_version ORDER BY id DESC LIMIT 1")).fetchone()

            return APIResponse(
                success=True,
                data={
                    "bull_count": bull_count,
                    "missing_bull_count": missing_count,
                    "database_version": version_info[0] if version_info else None,
                    "last_update": str(version_info[1]) if version_info else None
                }
            )
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 启动服务 ====================

if __name__ == "__main__":
    import uvicorn
    # 在生产环境中使用环境变量配置
    port = int(os.getenv('DATA_API_PORT', '8082'))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )