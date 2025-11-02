---
description: 发布新版本，自动更新所有文档和版本号
---

# 版本发布自动化流程

用户要发布版本：{version}

## 第0步：确认信息

首先询问用户（如果没有提供）：
1. 版本号是什么？（如：v1.2.0.19）
2. 是否需要清理测试文件？（默认：是）

## 第1步：分析变更内容

使用TodoWrite创建任务清单：
```json
[
  {"content": "分析git变更内容", "status": "in_progress"},
  {"content": "扫描测试文件", "status": "pending"},
  {"content": "更新文档", "status": "pending"},
  {"content": "更新版本号", "status": "pending"},
  {"content": "Git操作", "status": "pending"},
  {"content": "生成报告", "status": "pending"}
]
```

执行以下命令分析变更：
```bash
# 1. 找出上一个版本标签
git describe --tags --abbrev=0

# 2. 获取从上个版本到现在的所有commit
git log <上个版本>..HEAD --oneline --pretty=format:"%s"

# 3. 获取修改的文件列表
git diff --name-only <上个版本>..HEAD
```

根据commit message和文件变更，分类为：
- **新功能**：feat:开头的commit，或新增功能相关文件
- **Bug修复**：fix:开头的commit
- **性能改进**：perf:开头的commit
- **文档更新**：docs:开头的commit

## 第2步：扫描需要清理的文件

如果用户要求清理测试文件，执行：
```bash
# 扫描test目录下7天未修改的文件
find test -type f -mtime +7

# 扫描临时文件
find . -name "*.log" -o -name "*.tmp" -o -name "*.cache" -mtime +7
```

列出文件清单，**等待用户确认后再删除**。

## 第3步：更新所有文档

按照`docs/文档维护规则.md`中的检查清单，更新以下文档：

### 必须更新的文档：
1. `docs/05-项目管理/版本历史.md`
   - 在顶部添加新版本条目
   - 格式：
     ```markdown
     ## [v1.2.0.19] - 2025-11-03

     ### ✨ 新功能
     - [从git分析得到]

     ### 🐛 Bug修复
     - [从git分析得到]

     ### 🔧 改进
     - [从git分析得到]
     ```

2. `docs/05-项目管理/已完成任务.md`
   - 标记已完成的功能
   - 更新完成度百分比
   - 更新"最后更新"日期

3. `docs/05-项目管理/项目路线图.md`
   - 将已完成的任务从高优先级移除
   - 调整剩余任务优先级
   - 更新"当前版本"和日期

4. `docs/README.md`
   - 更新版本号（文件头部和"当前版本"两处）
   - 更新完成度
   - 在"已完成"部分添加新功能
   - 更新版本历史表格
   - 更新"最后更新"日期

### 可选更新的文档（根据变更内容）：
5. `docs/01-快速开始/快速入门指南.md`（如有重大功能更新）
6. `docs/01-快速开始/常见问题FAQ.md`（如有新的常见问题）
7. `docs/02-用户手册/` 下创建或更新功能文档（如有新功能）
8. `docs/03-开发文档/API参考.md`（如有API变更）

### 更新所有修改过的文档的日期：
搜索并替换所有文档中的"更新时间"或"最后更新"字段为今天日期。

## 第4步：更新代码版本号

**重要：必须严格按照以下顺序更新所有文件！**

### 4.1 更新 version.py
文件位置：`/version.py`

必须更新内容：
1. `VERSION` 变量（格式：`"1.2.0.19"`，不带v前缀）
2. `VERSION_HISTORY` 列表（在最前面添加新版本记录）

新版本记录格式：
```python
{
    "version": "1.2.0.19",
    "date": "2025-11-03",  # 今天日期
    "author": "Development Team",
    "changes": [
        # 从version.json的changes原样复制过来
    ]
}
```

**重要规则：**
- `VERSION_HISTORY`的`changes`必须与`version.json`的`changes`完全一致
- 不使用emoji，使用"序号. <b>分类</b>：描述"格式
- 常用分类：界面、功能、修复、优化、性能

### 4.2 更新 version.json
文件位置：`/version.json`

**这是最容易遗漏的文件！客户端依赖此文件检查更新！**

必须更新内容：
```json
{
  "version": "v1.2.0.19",  // 带v前缀
  "mac_download_url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.2.0.19/伊利奶牛选配_v1.2.0.19_macOS.dmg",
  "win_download_url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.2.0.19/伊利奶牛选配_v1.2.0.19_Windows.exe",
  "changes": [
    "1. <b>界面</b>：具体描述",
    "2. <b>修复</b>：具体描述",
    "3. <b>优化</b>：具体描述"
  ],
  "force_update": false
}
```

**changes编写规则（严格遵守）：**
- ❌ 不使用emoji表情符号
- ❌ 不出现颜色代码（#456ba0、rgba等）
- ❌ 不出现CSS属性名（gradient、padding等）
- ❌ 不出现代码文件名（main_window.py等）
- ❌ 不出现具体数值参数
- ❌ 不出现技术术语（QSS、QPalette等）
- ✅ 使用"序号. <b>分类</b>：描述"格式
- ✅ 使用HTML `<b>`标签加粗分类
- ✅ 使用专业但用户可理解的语言

示例：
- ❌ 错误："🎨 全新导航栏渐变蓝设计：从#456ba0到#2c5282"
- ✅ 正确："1. <b>界面</b>：优化导航栏配色方案，提升视觉体验"

### 4.3 更新 CHANGELOG.md
文件位置：`/CHANGELOG.md`

在文件第6行之后添加新版本条目：
```markdown
## [1.2.0.19] - 2025-11-03 📋 简短描述

### 🎨 界面优化（或其他分类）
- 详细说明1
- 详细说明2

### 🔧 问题修复
- 详细说明
```

### 版本更新检查清单（必须全部确认）

在继续下一步之前，确认：
- [ ] version.py 的 VERSION 已更新（无v前缀）
- [ ] version.py 的 VERSION_HISTORY 已添加新条目
- [ ] version.json 的 version 已更新（带v前缀）
- [ ] version.json 的 mac_download_url 已更新版本号
- [ ] version.json 的 win_download_url 已更新版本号
- [ ] version.json 的 changes 列表已更新（无emoji）
- [ ] version.py 和 version.json 的 changes 完全一致
- [ ] CHANGELOG.md 已添加新版本条目
- [ ] 所有文件的版本号一致

## 第5步：执行Git操作

**重要：严格按照以下顺序执行，每一步都要等待前一步成功后再执行下一步**

### 5.1 检查状态和添加文件

```bash
# 1. 查看所有变更
git status

# 2. 添加版本相关文件（必须包含这3个文件）
git add version.py CHANGELOG.md version.json

# 3. 添加文档变更
git add docs/

# 4. 添加其他修改的源代码文件
git add [其他修改的文件]
```

### 5.2 创建提交

使用规范的commit message格式（按照.clinerules规范）：

```bash
git commit -m "🎨 v1.2.0.19: [简短标题]

### [分类emoji + 标题]
- 更新点1
- 更新点2
- 更新点3

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Emoji使用规范：**
- 🎨 界面优化、设计改进
- ✨ 新功能
- 🔧 问题修复、技术改进
- 📊 数据相关、图表优化
- 🎯 用户体验改进
- 🔄 重构、流程优化
- 🐛 Bug修复
- 📝 文档更新
- 🚀 性能优化

### 5.3 推送到main分支

**先推送代码到main分支：**
```bash
git push origin main
```

等待推送成功。

### 5.4 创建并推送版本标签

**重要：推送标签会触发GitHub Actions自动构建！**

```bash
# 1. 创建版本标签
git tag -a v1.2.0.19 -m "v1.2.0.19: [简短描述]"

# 2. 查看标签是否创建成功
git tag -l | tail -5

# 3. 推送标签（这会触发GitHub Actions）
git push origin v1.2.0.19
```

### 5.5 确认推送成功

```bash
# 查看最近的commit
git log -1

# 查看远程分支状态
git branch -vv
```

**提示用户：**
```
✅ Git操作完成

已执行：
1. ✅ 提交所有变更到本地仓库
2. ✅ 推送到main分支
3. ✅ 创建版本标签 v1.2.0.19
4. ✅ 推送标签（触发GitHub Actions）

GitHub Actions状态：
https://github.com/[用户名]/genetic_improve/actions

请检查GitHub Actions构建状态。
```

## 第6步：生成完整报告

总结所有操作，格式如下：

```markdown
✅ 版本 v1.2.0.19 发布完成

## 📊 版本信息
- 版本号：v1.2.0.19
- 发布日期：2025-11-03
- 完成度：[X]% → [Y]%

## 📝 本次变更
### ✨ 新功能
- [列表]

### 🐛 Bug修复
- [列表]

### 🔧 性能改进
- [列表]

## 📄 已更新的文档
1. ✅ docs/05-项目管理/版本历史.md
2. ✅ docs/05-项目管理/已完成任务.md
3. ✅ docs/05-项目管理/项目路线图.md
4. ✅ docs/README.md
5. ✅ version.json
6. ✅ version.py
[其他更新的文档...]

## 🗑️ 清理的文件
- [列表，如果有]

## 📦 Git操作
- ✅ Commit: [commit hash]
- ✅ Tag: v1.2.0.19
- ✅ Pushed to GitHub
- ✅ GitHub Actions: https://github.com/[用户名]/genetic_improve/actions

## 🎯 下一步建议
1. 检查GitHub Actions构建状态
2. 测试新版本功能
3. 通知相关人员版本更新
```

## 错误处理

如果任何步骤失败：
1. 立即停止后续操作
2. 显示错误信息
3. 提供回滚建议（如git reset等）
4. 询问用户如何处理

## 注意事项

- 所有Git操作执行前，先git status检查状态
- 推送前务必询问用户确认
- 不要自动删除文件，必须列出清单让用户确认
- 如果缺少必要信息，主动询问用户
- 使用TodoWrite工具实时显示进度
