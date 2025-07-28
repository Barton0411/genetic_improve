# 阿里云账号验证登录模块

这是一个从奶牛育种项目中提取的阿里云数据库账号验证登录功能模块，可以独立使用在其他项目中。

## 功能特点

- ✅ 支持阿里云 MySQL PolarDB 数据库连接
- ✅ 用户账号密码验证
- ✅ 数据库连接信息加密存储
- ✅ 现代化 PyQt6 登录界面
- ✅ 异步登录处理，避免界面卡顿
- ✅ 完整的错误处理和用户提示
- ✅ 模块化设计，易于集成

## 文件结构

```
阿里云登录模块/
├── database_config.py    # 数据库配置（包含加密功能）
├── auth_service.py       # 用户认证服务
├── login_dialog.py       # 登录对话框组件
├── example_usage.py      # 使用示例
├── requirements.txt      # 依赖清单
└── README.md            # 说明文档
```

## 数据库信息

### 连接参数
- **主机**: `defectgene-new.mysql.polardb.rds.aliyuncs.com`
- **端口**: `3306`
- **用户名**: `defect_genetic_checking`
- **密码**: `Jaybz@890411`
- **数据库**: `bull_library`

### 用户表结构
用户账号信息存储在 `id-pw` 表中：
- `ID`: 用户名
- `PW`: 密码

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 方法1：使用便捷函数

```python
from login_dialog import show_login_dialog

# 显示登录对话框
success, username = show_login_dialog(title="系统登录", use_encryption=True)

if success:
    print(f"登录成功，用户：{username}")
else:
    print("登录失败或取消")
```

### 方法2：使用对话框对象

```python
from login_dialog import LoginDialog
from PyQt6.QtWidgets import QApplication

app = QApplication([])
login_dialog = LoginDialog(title="自定义登录", use_encryption=True)

if login_dialog.exec() == LoginDialog.DialogCode.Accepted:
    username = login_dialog.get_username()
    print(f"登录成功，用户：{username}")
```

### 方法3：单独使用认证服务

```python
from auth_service import AuthService

auth = AuthService(use_encryption=True)
if auth.authenticate_user("用户名", "密码"):
    print("认证成功")
else:
    print("认证失败")
```

## 配置选项

### 加密模式（推荐）
```python
# 使用加密的数据库连接信息
success, username = show_login_dialog(use_encryption=True)
```

### 明文模式（测试用）
```python
# 使用明文数据库连接信息（不推荐生产环境使用）
success, username = show_login_dialog(use_encryption=False)
```

## 安全说明

1. **加密存储**: 数据库连接信息使用 Fernet 对称加密存储
2. **密码保护**: 登录界面密码输入框使用掩码显示
3. **连接安全**: 支持 SSL 加密的数据库连接
4. **错误处理**: 完善的异常处理，不暴露敏感信息

## 定制化

### 修改数据库连接
编辑 `database_config.py` 文件中的连接参数：

```python
CLOUD_DB_HOST = '你的数据库主机'
CLOUD_DB_PORT = 3306
CLOUD_DB_USER = '你的用户名'
CLOUD_DB_PASSWORD_RAW = '你的密码'
CLOUD_DB_NAME = '你的数据库名'
```

### 修改界面样式
编辑 `login_dialog.py` 中的 `_setup_styles()` 方法来自定义界面外观。

### 自定义认证逻辑
继承 `AuthService` 类并重写 `authenticate_user` 方法：

```python
class CustomAuthService(AuthService):
    def authenticate_user(self, username, password):
        # 自定义认证逻辑
        return super().authenticate_user(username, password)
```

## 运行示例

```bash
python example_usage.py
```

## 注意事项

1. 确保网络能够访问阿里云数据库
2. 首次使用时会连接远程数据库验证用户
3. 建议在生产环境中使用加密模式
4. 数据库连接信息请妥善保管

## 故障排除

### 常见问题

1. **导入错误**: 确保安装了所有依赖包
2. **连接超时**: 检查网络连接和防火墙设置
3. **认证失败**: 确认用户名密码正确，检查数据库中的用户数据

### 日志调试

启用详细日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 许可证

此模块从原奶牛育种项目中提取，仅供学习和参考使用。 
