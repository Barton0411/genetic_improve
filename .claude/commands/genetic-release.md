---
description: 发布新版本，自动更新所有文档和版本号
---

# 版本发布自动化流程

版本号自动增加0.0.0.1（例如：1.2.2.4 → 1.2.2.5）

## 第0步：创建任务清单

使用TodoWrite创建任务清单，实时追踪进度。

## 第1步：清理测试文件

检查根目录是否有test*.py文件需要清理：
```bash
ls -la test*.py 2>/dev/null || echo "No test files in root"
```

## 第2步：分析变更内容

```bash
# 1. 读取当前版本号
cat version.json | python3 -c "import json,sys; print(json.load(sys.stdin)['version'])"

# 2. 获取从上个版本到现在的修改文件
git diff v{上个版本}..HEAD --name-only
```

根据修改的文件，编写变更说明，分类为：
- **功能**：新增功能
- **优化**：改进优化
- **修复**：Bug修复
- **文档**：文档更新

## 第3步：更新 version.py

文件位置：`version.py`

1. 更新 `VERSION` 变量（无v前缀）
2. 在 `VERSION_HISTORY` 列表开头添加新版本记录

```python
VERSION = "1.2.2.5"  # 新版本号

VERSION_HISTORY = [
    {
        "version": "1.2.2.5",
        "date": "2025-12-19",  # 今天日期
        "author": "Development Team",
        "changes": [
            "1. <b>功能</b>：具体描述",
            "   - 详细说明",
            "2. <b>优化</b>：具体描述"
        ]
    },
    # 保留旧版本记录...
]
```

## 第4步：更新 version.json

文件位置：`version.json`

**重要：使用空字符串 "" 实现换行分隔！**

```json
{
  "version": "1.2.2.5",
  "force_update": false,
  "mac_download_url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.2.2.5/伊利奶牛选配_v1.2.2.5_mac.dmg",
  "win_download_url": "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.2.2.5/伊利奶牛选配_v1.2.2.5_win.exe",
  "changes": [
    "1. <b>功能</b>：主功能描述",
    "   - 详细说明1",
    "   - 详细说明2",
    "",
    "2. <b>优化</b>：第二项描述",
    "   - 详细说明"
  ]
}
```

## 第5步：提交并推送

```bash
# 提交所有更改
git add -A && git commit -m "$(cat <<'EOF'
v1.2.2.5: 简短描述

1. 功能：xxx
2. 优化：xxx

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"

# 创建tag并推送
git tag -a v1.2.2.5 -m "Release v1.2.2.5: 简短描述"
git push origin main --tags
```

## 第6步：监控GitHub Actions构建

使用以下命令检查构建状态：
```bash
curl -s "https://api.github.com/repos/Barton0411/genetic_improve/actions/runs?per_page=3" | python3 -c "
import json, sys
data = json.load(sys.stdin)
runs = data.get('workflow_runs', [])
for r in runs:
    print(f\"{r['status']:12} {r['conclusion'] or 'running':12} {r['name'][:30]:30} {r['head_branch']:15} {r['created_at'][:19]}\")"
```

等待构建完成（约10-15分钟），确保状态为 `completed success`。

## 第7步：更新OSS版本文件

**构建成功后**，上传version.json到OSS让用户收到更新提示：

```bash
/usr/local/bin/ossutil cp version.json oss://genetic-improve/latest/version.json -f
```

验证上传成功：
```bash
/usr/local/bin/ossutil cat oss://genetic-improve/latest/version.json
```

## 注意事项

- version.json 中使用 `""` 空字符串作为段落分隔符
- version.py 中必须使用单引号 `'` 而非中文引号
- tag 必须以 `v` 开头才能触发 GitHub Actions
- 构建完成后**立即**更新 OSS 版本文件
