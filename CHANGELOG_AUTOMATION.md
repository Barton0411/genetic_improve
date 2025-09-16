# 自动生成Changelog工作流

## 概述

现在每次打包发布时，系统会自动从`version.py`中的`VERSION_HISTORY`生成changelog.txt文件，并上传到OSS，同时用于GitHub Release说明。

## 工作流程

### 1. 自动changelog生成
- 构建过程中自动运行`auto_generate_changelog.py`
- 从`version.py`的`VERSION_HISTORY`读取当前版本更新内容
- 生成格式化的`CHANGELOG_v{版本号}.txt`文件

### 2. OSS自动上传  
- changelog文件自动上传到OSS：`releases/v{版本号}/CHANGELOG.txt`
- 可通过URL访问：`https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v{版本号}/CHANGELOG.txt`

### 3. GitHub Release集成
- Release说明自动使用生成的changelog内容
- 不再需要手动编写Release Notes

## 使用步骤

### 更新版本时:

1. **修改版本信息**（在`version.py`中）:
```python
VERSION = "1.0.8"  # 更新版本号

VERSION_HISTORY = [
    {
        "version": "1.0.8", 
        "date": "2025-09-17",
        "author": "开发团队",
        "changes": [
            "🔥 新功能：添加xxx功能",
            "⚡ 性能优化：提升xxx速度", 
            "🛡️ 安全修复：修复xxx漏洞",
            "🎨 UI改进：优化xxx界面"
        ]
    },
    # ... 之前的版本历史
]
```

2. **触发构建**:
```bash
# 推送版本标签
git tag v1.0.8
git push origin v1.0.8

# 或手动触发workflow
```

3. **自动完成**:
- ✅ 自动生成`CHANGELOG_v1.0.8.txt`
- ✅ 上传到OSS `releases/v1.0.8/CHANGELOG.txt` 
- ✅ GitHub Release使用changelog内容
- ✅ API自动读取OSS中的changelog显示给用户

## 配置要求

### GitHub Secrets
需要配置以下secrets用于OSS上传:
- `ALIYUN_ACCESS_KEY_ID`: 阿里云AccessKey ID
- `ALIYUN_ACCESS_KEY_SECRET`: 阿里云AccessKey Secret

### OSS权限
确保AccessKey有以下权限:
- `oss:PutObject` - 上传changelog文件
- `oss:GetObject` - 验证上传结果

## 文件说明

- `auto_generate_changelog.py`: changelog生成脚本
- `.github/workflows/build-releases.yml`: 集成了changelog生成的构建工作流
- `CHANGELOG_v{版本}.txt`: 自动生成的changelog文件

## 优势

1. **完全自动化**: 无需手动维护changelog文件
2. **一致性**: 所有渠道（OSS API、GitHub Release）使用相同内容
3. **版本控制**: changelog与代码版本同步管理
4. **多平台支持**: Windows和macOS构建都会生成changelog
5. **备份保障**: changelog同时保存在GitHub和OSS

## 故障排除

如果changelog生成失败：
1. 检查`version.py`中的`VERSION_HISTORY`格式
2. 确认当前版本在`VERSION_HISTORY`中有对应条目
3. 查看GitHub Actions构建日志
4. 验证OSS访问密钥配置

## 示例输出

生成的changelog文件内容示例：
```
🔥 实现强制更新系统，确保关键更新必须安装
⚡ 新增应用内智能更新功能，无需手动下载安装包
🛡️ 增强更新安全性，支持完整文件替换和回滚机制
🎨 全新设计的更新对话框，支持深色/浅色模式自动适配
📦 智能路径检测，支持任意安装位置的程序更新
🔒 保护用户数据，更新过程中项目文件和配置安全不受影响
🚀 三阶段更新流程：准备→执行→验证，确保更新可靠性
💻 跨平台兼容，完美支持Windows、macOS和Linux系统
```