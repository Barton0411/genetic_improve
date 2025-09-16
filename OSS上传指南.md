# OSS安装包上传指南

## 准备工作

### 1. 获取安装包文件
从GitHub Release页面下载最新构建的安装包：
- `GeneticImprove_v1.0.5_win.exe` - Windows安装版
- `GeneticImprove_v1.0.5_win.zip` - Windows便携版  
- `GeneticImprove_v1.0.5_mac.dmg` - macOS安装包

### 2. 确认OSS Bucket配置
- Bucket名称：`genetic-improve`
- 地域：华北2(北京)
- 权限：公共读

## 上传方式选择

### 🌐 方式A：网页控制台上传（推荐）

1. **登录OSS控制台**
   ```
   https://oss.console.aliyun.com/
   ```

2. **进入Bucket**
   - 选择华北2(北京)地域
   - 点击 `genetic-improve` bucket

3. **创建目录结构**
   ```
   releases/
   └── v1.0.5/
   ```

4. **上传文件**
   - 进入 `releases/v1.0.5/` 目录
   - 点击"上传文件"
   - 拖拽或选择3个安装包文件
   - 确认上传

### 💻 方式B：使用Python脚本上传

1. **安装依赖**
   ```bash
   pip install oss2
   ```

2. **设置环境变量**
   ```bash
   export OSS_ACCESS_KEY_ID="your_access_key_id"
   export OSS_ACCESS_KEY_SECRET="your_access_key_secret"
   ```

3. **运行上传脚本**
   ```bash
   python scripts/upload_to_oss.py
   ```

### 📱 方式C：使用阿里云CLI

1. **安装阿里云CLI**
   ```bash
   # macOS
   brew install aliyun-cli
   
   # Windows
   # 从官网下载安装包
   ```

2. **配置认证**
   ```bash
   aliyun configure
   ```

3. **上传文件**
   ```bash
   # 上传Windows安装版
   aliyun oss cp GeneticImprove_v1.0.5_win.exe oss://genetic-improve/releases/v1.0.5/
   
   # 上传Windows便携版  
   aliyun oss cp GeneticImprove_v1.0.5_win.zip oss://genetic-improve/releases/v1.0.5/
   
   # 上传macOS版本
   aliyun oss cp GeneticImprove_v1.0.5_mac.dmg oss://genetic-improve/releases/v1.0.5/
   ```

## 验证上传结果

### 检查文件访问URL
上传成功后，文件应该可以通过以下URL访问：

```
https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.5/GeneticImprove_v1.0.5_win.exe
https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.5/GeneticImprove_v1.0.5_win.zip  
https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.5/GeneticImprove_v1.0.5_mac.dmg
```

### 创建版本信息文件
在 `releases/latest/` 目录创建 `version.json` 文件：

```json
{
  "version": "1.0.5",
  "release_date": "2025-09-16",
  "changes": [
    "修复Mac应用图标显示问题",
    "优化Windows构建完整性",
    "更新应用名称为伊利奶牛选配"
  ],
  "downloads": {
    "windows_installer": {
      "url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.5/GeneticImprove_v1.0.5_win.exe",
      "size": "300MB"
    },
    "windows_portable": {
      "url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.5/GeneticImprove_v1.0.5_win.zip",
      "size": "350MB"  
    },
    "macos": {
      "url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.5/GeneticImprove_v1.0.5_mac.dmg",
      "size": "280MB"
    }
  }
}
```

## 常见问题

### Q1: 上传后无法访问文件
**A:** 检查Bucket权限是否设置为"公共读"

### Q2: 访问URL返回403错误  
**A:** 确认文件路径正确，检查CORS配置

### Q3: 文件上传失败
**A:** 检查网络连接，确认AccessKey权限足够

## 下一步

上传完成后需要：
1. ✅ 更新数据库中的版本信息
2. ✅ 测试版本检查API
3. ✅ 验证自动更新功能

---

💡 **推荐使用方式A（网页控制台）**进行首次上传，简单直观！