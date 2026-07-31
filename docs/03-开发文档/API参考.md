# API 参考文档

## 📋 基本信息

```yaml
API域名: https://api.genepop.com
协议: HTTPS
认证方式: JWT Bearer Token
内容类型: application/json
```

---

## 🔐 认证 API

**Base URL:** `https://api.genepop.com/api/auth`

### 1. 用户注册

**接口:** `POST /api/auth/register`

**认证:** 不需要

**请求体:**
```json
{
  "username": "user123",
  "password": "<PASSWORD>",
  "invitation_code": "INVITE2024"
}
```

**成功响应:** `200 OK`
```json
{
  "success": true,
  "message": "注册成功",
  "data": {
    "username": "user123",
    "token": "<TOKEN>",
    "expires_in": 86400
  }
}
```

**错误响应:** `400 Bad Request`
```json
{
  "success": false,
  "message": "邀请码无效",
  "error_code": "INVALID_INVITATION_CODE"
}
```

**可能的错误:**
- `INVALID_INVITATION_CODE` - 邀请码无效或已使用
- `USERNAME_EXISTS` - 用户名已存在
- `INVALID_INPUT` - 输入参数格式错误

---

### 2. 用户登录

**接口:** `POST /api/auth/login`

**认证:** 不需要

**请求体:**
```json
{
  "username": "user123",
  "password": "<PASSWORD>"
}
```

**成功响应:** `200 OK`
```json
{
  "success": true,
  "message": "登录成功",
  "data": {
    "username": "user123",
    "token": "<TOKEN>",
    "expires_in": 86400
  }
}
```

**错误响应:** `401 Unauthorized`
```json
{
  "success": false,
  "message": "用户名或密码错误",
  "error_code": "INVALID_CREDENTIALS"
}
```

---

### 3. 验证令牌

**接口:** `POST /api/auth/verify`

**认证:** 需要 JWT Token

**请求头:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**成功响应:** `200 OK`
```json
{
  "success": true,
  "message": "令牌有效",
  "data": {
    "username": "user123",
    "expires_at": "2025-10-08T10:30:00Z"
  }
}
```

**错误响应:** `401 Unauthorized`
```json
{
  "success": false,
  "message": "令牌无效或已过期",
  "error_code": "INVALID_TOKEN"
}
```

---

### 4. 获取用户信息

**接口:** `GET /api/auth/user`

**认证:** 需要 JWT Token

**请求头:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**成功响应:** `200 OK`
```json
{
  "success": true,
  "data": {
    "username": "user123",
    "created_at": "2025-09-15T08:20:00Z",
    "last_login": "2025-10-07T09:15:00Z"
  }
}
```

---

## 📊 数据 API

**Base URL:** `https://api.genepop.com/api/data`

### 1. 查询数据库版本

**接口:** `GET /api/data/version`

**认证:** 不需要

**成功响应:** `200 OK`
```json
{
  "success": true,
  "data": {
    "version": "1.2.2",
    "update_time": "2025-09-22T10:30:00Z",
    "record_count": 247192,
    "file_size": 138412032,
    "download_url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/bull_library/bull_library.db"
  }
}
```

**说明:**
- `version`: 数据库版本号
- `update_time`: 数据库更新时间（ISO 8601格式）
- `record_count`: 公牛记录总数
- `file_size`: 数据库文件大小（字节）
- `download_url`: OSS下载地址（客户端直接从OSS下载）

---

### 2. 上传缺失公牛记录

**接口:** `POST /api/data/missing_bulls`

**认证:** ⚠️ 不需要（公开接口）

**请求体:**
```json
{
  "bulls": [
    {
      "naab": "001HO12345",
      "source": "user_upload",
      "time": "2025-10-07T14:30:00",
      "user": "user123"
    },
    {
      "naab": "007HO67890",
      "source": "calculation",
      "time": "2025-10-07T14:30:00",
      "user": "user123"
    }
  ]
}
```

**字段说明:**
- `naab`: 公牛NAAB号（必填）
- `source`: 来源（user_upload/calculation）
- `time`: 时间戳（ISO 8601格式）
- `user`: 用户名（可选）

**成功响应:** `200 OK`
```json
{
  "success": true,
  "message": "成功上传缺失公牛记录",
  "data": {
    "uploaded_count": 2,
    "duplicate_count": 0
  }
}
```

**错误响应:** `400 Bad Request`
```json
{
  "success": false,
  "message": "请求数据格式错误",
  "error_code": "INVALID_FORMAT"
}
```

**设计原因:**
- 此接口不需要认证，目的是方便收集用户反馈的缺失公牛数据
- 数据本身不敏感（只是NAAB号），不会造成安全风险
- 降低门槛，便于完善数据库

---

### 3. 查询应用版本（未来）

**接口:** `GET /api/data/app_version`

**认证:** 不需要

**成功响应:** `200 OK`
```json
{
  "success": true,
  "data": {
    "version": "1.2.0.4",
    "release_date": "2025-09-30",
    "download_url": {
      "windows_exe": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.2.0.4/伊利奶牛选配_v1.2.0.4_win.exe",
      "windows_zip": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.2.0.4/伊利奶牛选配_v1.2.0.4_win.zip",
      "macos_dmg": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.2.0.4/伊利奶牛选配_v1.2.0.4_mac.dmg"
    },
    "changelog": "修复了选配系统bug，优化了性能"
  }
}
```

---

## 🔄 客户端调用示例

### Python 示例

```python
import requests
from api.api_client import get_api_client

# 使用统一的API客户端
api_client = get_api_client()

# 1. 用户登录
success = api_client.login("user123", "password123")
if success:
    print("登录成功")

# 2. 验证令牌
is_valid = api_client.verify_token()
if is_valid:
    print("令牌有效")

# 3. 查询数据库版本
version_info = api_client.get_db_version()
print(f"数据库版本: {version_info['version']}")

# 4. 上传缺失公牛
missing_bulls = [
    {
        'naab': '001HO12345',
        'source': 'user_upload',
        'time': '2025-10-07T14:30:00',
        'user': 'user123'
    }
]
success = api_client.upload_missing_bulls(missing_bulls)
if success:
    print("上传成功")
```

### 直接HTTP调用示例

```python
import requests

BASE_URL = "https://api.genepop.com"

# 登录
response = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={
        "username": "user123",
        "password": "<PASSWORD>"
    }
)
data = response.json()
token = data['data']['token']

# 验证令牌
response = requests.post(
    f"{BASE_URL}/api/auth/verify",
    headers={
        "Authorization": f"Bearer {token}"
    }
)
print(response.json())

# 上传缺失公牛（无需认证）
response = requests.post(
    f"{BASE_URL}/api/data/missing_bulls",
    json={
        "bulls": [
            {
                "naab": "001HO12345",
                "source": "user_upload",
                "time": "2025-10-07T14:30:00",
                "user": "user123"
            }
        ]
    }
)
print(response.json())
```

---

## ⚠️ 错误码说明

### 通用错误码
```
400 Bad Request          - 请求参数错误
401 Unauthorized         - 未授权（令牌无效或过期）
403 Forbidden            - 禁止访问
404 Not Found            - 资源不存在
500 Internal Server Error - 服务器内部错误
503 Service Unavailable  - 服务暂时不可用
```

### 业务错误码
```
INVALID_CREDENTIALS       - 用户名或密码错误
INVALID_TOKEN            - 令牌无效或已过期
USERNAME_EXISTS          - 用户名已存在
INVALID_INVITATION_CODE  - 邀请码无效
INVALID_FORMAT           - 数据格式错误
DATABASE_ERROR           - 数据库错误
```

---

## 🔒 安全说明

### JWT Token 配置
```yaml
算法: HS256
密钥: genetic-improve-api-secret-key
过期时间: 24小时
刷新机制: 需重新登录
```

### 安全建议
```
1. Token应安全存储在客户端本地配置文件
2. 不要在日志中打印完整Token
3. Token过期后提示用户重新登录
4. 生产环境应使用更强的JWT密钥（至少32位随机字符串）
```

---

## 📈 API限流（未来实现）

```yaml
认证API:
  - 登录: 10次/分钟/IP
  - 注册: 5次/分钟/IP

数据API:
  - 版本查询: 100次/分钟/用户
  - 缺失公牛上传: 50次/分钟/用户
```

---

## 🧪 测试环境

### 使用 curl 测试

```bash
# 1. 测试登录
curl -X POST https://api.genepop.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"<PASSWORD>"}'

# 2. 测试数据库版本查询
curl https://api.genepop.com/api/data/version

# 3. 测试缺失公牛上传
curl -X POST https://api.genepop.com/api/data/missing_bulls \
  -H "Content-Type: application/json" \
  -d '{
    "bulls": [
      {
        "naab": "001HO12345",
        "source": "test",
        "time": "2025-10-07T14:30:00",
        "user": "test"
      }
    ]
  }'

# 4. 测试健康检查
curl https://api.genepop.com/api/health
```

---

## 📝 API变更历史

### v1.2.0 (2025-09-30)
- ✅ 缺失公牛上传接口改为无需认证
- ✅ API地址统一为 https://api.genepop.com
- ⚠️ 废弃数据库下载API（改用OSS直接下载）

### v1.1.0 (2025-08-15)
- ✅ 新增数据API服务 (8082端口)
- ✅ 新增缺失公牛上传接口

### v1.0.0 (2025-07-01)
- ✅ 初始版本
- ✅ 用户认证API (登录、注册、验证)

---

## 🔮 未来规划

### 计划中的接口
```
POST /api/data/mating_result    - 选配结果推送
GET  /api/data/bull_info        - 查询公牛详细信息
POST /api/data/feedback         - 用户反馈提交
GET  /api/data/statistics       - 使用统计查询
```

---

最后更新: 2025-10-07
API版本: v1.2.0
