"""
认证API服务
用于替换硬编码数据库连接的安全API接口
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt
from sqlalchemy import create_engine, text
import hashlib

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 从环境变量获取配置
DB_HOST = os.getenv('DB_HOST', 'defectgene-new.mysql.polardb.rds.aliyuncs.com')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER', 'defect_genetic_checking')
DB_PASSWORD = os.getenv('DB_PASSWORD')  # 必须从环境变量获取
DB_NAME = os.getenv('DB_NAME', 'bull_library')
JWT_SECRET = os.getenv('JWT_SECRET', 'genetic-improve-api-secret-key')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRE_HOURS = 24

if not DB_PASSWORD:
    raise ValueError("DB_PASSWORD environment variable is required")

# 数据库连接
import urllib.parse
DB_PASSWORD_ENCODED = urllib.parse.quote_plus(DB_PASSWORD)
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD_ENCODED}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

app = FastAPI(
    title="伊利奶牛选配系统 - 认证API",
    description="提供用户认证、注册等安全接口",
    version="1.0.0"
)

security = HTTPBearer()

# 请求/响应模型
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    employee_id: str
    password: str
    invite_code: str
    name: str

class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: int

class TokenData(BaseModel):
    username: str
    exp: int

def get_db_engine():
    """获取数据库引擎"""
    return create_engine(DATABASE_URL, echo=False)

def create_access_token(username: str) -> str:
    """创建JWT访问令牌"""
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    to_encode = {
        "sub": username,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """验证JWT令牌"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已过期"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌"
        )

def hash_password(password: str) -> str:
    """简单密码哈希（与现有系统兼容）"""
    # 注意：这里保持与现有系统相同的密码存储方式
    # 在实际生产环境中应使用更安全的哈希方法如 bcrypt
    return password

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return APIResponse(
        success=True,
        message="认证API服务运行正常",
        timestamp=int(datetime.utcnow().timestamp())
    )

@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """用户登录接口"""
    try:
        engine = get_db_engine()

        with engine.connect() as connection:
            # 验证用户名密码
            result = connection.execute(
                text("SELECT ID, PW, name FROM `id-pw` WHERE ID=:username AND PW=:password"),
                {"username": request.username, "password": request.password}
            ).fetchone()

            if not result:
                return APIResponse(
                    success=False,
                    message="用户名或密码错误",
                    timestamp=int(datetime.utcnow().timestamp())
                )

            # 生成JWT令牌
            token = create_access_token(request.username)

            return APIResponse(
                success=True,
                message="登录成功",
                data={
                    "token": token,
                    "user_id": result[0],
                    "name": result[2] if len(result) > 2 else None,
                    "expires_in": JWT_EXPIRE_HOURS * 3600
                },
                timestamp=int(datetime.utcnow().timestamp())
            )

    except Exception as e:
        logger.error(f"登录失败: {e}")
        return APIResponse(
            success=False,
            message=f"登录失败: {str(e)}",
            timestamp=int(datetime.utcnow().timestamp())
        )

@app.post("/api/auth/register")
async def register(request: RegisterRequest):
    """用户注册接口"""
    try:
        engine = get_db_engine()

        with engine.connect() as connection:
            # 检查用户是否已存在
            result = connection.execute(
                text("SELECT ID FROM `id-pw` WHERE ID=:employee_id"),
                {"employee_id": request.employee_id}
            ).fetchone()

            if result:
                return APIResponse(
                    success=False,
                    message="用户名已存在",
                    timestamp=int(datetime.utcnow().timestamp())
                )

            # 检查邀请码
            invite_result = connection.execute(
                text("""
                    SELECT code, status, max_uses, current_uses, expire_time
                    FROM invitation_codes
                    WHERE code = :invite_code
                """),
                {"invite_code": request.invite_code}
            ).fetchone()

            if not invite_result:
                return APIResponse(
                    success=False,
                    message="邀请码不存在",
                    timestamp=int(datetime.utcnow().timestamp())
                )

            code, status, max_uses, current_uses, expire_time = invite_result

            # 检查状态
            if status != 1:
                return APIResponse(
                    success=False,
                    message="邀请码已失效",
                    timestamp=int(datetime.utcnow().timestamp())
                )

            # 检查过期时间
            if expire_time and datetime.now() > expire_time:
                return APIResponse(
                    success=False,
                    message="邀请码已过期",
                    timestamp=int(datetime.utcnow().timestamp())
                )

            # 检查使用次数
            if current_uses >= max_uses:
                return APIResponse(
                    success=False,
                    message="邀请码使用次数已达上限",
                    timestamp=int(datetime.utcnow().timestamp())
                )

            # 开始事务
            trans = connection.begin()
            try:
                # 创建用户
                connection.execute(
                    text("INSERT INTO `id-pw` (ID, PW, name) VALUES (:employee_id, :password, :name)"),
                    {
                        "employee_id": request.employee_id,
                        "password": hash_password(request.password),
                        "name": request.name
                    }
                )

                # 更新邀请码使用次数
                connection.execute(
                    text("""
                        UPDATE invitation_codes
                        SET current_uses = current_uses + 1
                        WHERE code = :invite_code
                    """),
                    {"invite_code": request.invite_code}
                )

                trans.commit()

                return APIResponse(
                    success=True,
                    message="注册成功",
                    timestamp=int(datetime.utcnow().timestamp())
                )

            except Exception as e:
                trans.rollback()
                raise e

    except Exception as e:
        logger.error(f"注册失败: {e}")
        return APIResponse(
            success=False,
            message=f"注册失败: {str(e)}",
            timestamp=int(datetime.utcnow().timestamp())
        )

@app.get("/api/auth/profile")
async def get_profile(current_user: str = Depends(verify_token)):
    """获取当前用户信息"""
    try:
        engine = get_db_engine()

        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT ID, name FROM `id-pw` WHERE ID=:username"),
                {"username": current_user}
            ).fetchone()

            if not result:
                return APIResponse(
                    success=False,
                    message="用户不存在",
                    timestamp=int(datetime.utcnow().timestamp())
                )

            return APIResponse(
                success=True,
                message="获取用户信息成功",
                data={
                    "user_id": result[0],
                    "name": result[1] if len(result) > 1 else None
                },
                timestamp=int(datetime.utcnow().timestamp())
            )

    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        return APIResponse(
            success=False,
            message=f"获取用户信息失败: {str(e)}",
            timestamp=int(datetime.utcnow().timestamp())
        )

@app.post("/api/auth/verify")
async def verify_token_endpoint(current_user: str = Depends(verify_token)):
    """验证令牌有效性"""
    return APIResponse(
        success=True,
        message="令牌有效",
        data={"user_id": current_user},
        timestamp=int(datetime.utcnow().timestamp())
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")