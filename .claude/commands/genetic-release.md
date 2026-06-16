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

## 第4步：更新 version.json（❗易漏，漏了客户端收不到更新）

文件位置：`version.json`

⚠️ **这是和 `version.py` 不同的另一个文件，必须同步更新！** 客户端检查更新读的是
OSS 上的 version.json（内容来自此文件），不是 version.py。只改 version.py 而漏掉
version.json，安装包会正常构建上传，但 version 号不变 → App 检查不到更新。

务必同步更新：`version`、`mac_download_url`、`win_download_url` 里的版本号，以及 `changes`。

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
# 提交发布改动。⚠️ 不要用 git add -A（工作区可能有无关脏文件）；精确 add 本次发布相关文件。
# 至少包含 version.py 和 version.json，外加本次功能改动的文件。
git add version.py version.json  # + 本次改动的其他文件
git commit -m "v1.2.2.5: 简短描述

1. 功能：xxx
2. 优化：xxx"

# 创建tag并推送（tag 必须以 v 开头才能触发 GitHub Actions）
git tag -a v1.2.2.5 -m "Release v1.2.2.5: 简短描述"
git push origin main
git push origin v1.2.2.5
```

> commit message 不加 AI 署名（全局已禁用 attribution）。
>
> **若该版本号 tag 已存在需重新发布**（如修了 workflow 要重跑）：
> ```bash
> git push origin :refs/tags/v1.2.2.5   # 删除远程 tag
> git tag -d v1.2.2.5                    # 删除本地 tag
> git tag v1.2.2.5 && git push origin v1.2.2.5   # 重打并推送，触发完整重建
> ```

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

## 第7步：更新OSS版本文件（决定客户端能否收到更新）

**构建成功后**，上传version.json到OSS让用户收到更新提示。

⚠️ **路径必须是 `releases/latest/version.json`**——这是客户端 `core/update/version_manager.py:87`
（`{server_url}/releases/latest/version.json`）实际读取的地址，也是 CI workflow 上传的地址。
**不要写成 `latest/version.json`**（旧文档曾写错，客户端读不到，会导致 App 检查不到更新）。

```bash
/usr/local/bin/ossutil cp version.json oss://genetic-improve/releases/latest/version.json -f
```

验证上传成功（确认版本号已是新版本）：
```bash
curl -s --noproxy '*' "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/latest/version.json" \
  | python3 -c "import json,sys; print('OSS version =', json.load(sys.stdin)['version'])"
```

> 说明：CI 的 upload-to-oss job 也会上传 version.json 到 releases/latest/，但它上传的是
> **仓库里的 version.json 文件**。若第4步漏改 version.json，CI 传上去的仍是旧版本号，
> 客户端就收不到更新——所以第4步和本步缺一不可。

## 注意事项

- version.json 中使用 `""` 空字符串作为段落分隔符
- version.py 中必须使用单引号 `'` 而非中文引号
- tag 必须以 `v` 开头才能触发 GitHub Actions
- **version.py 和 version.json 必须同步更新**（第3、4步），缺一不可
- 构建完成后**立即**更新 OSS 版本文件到 `releases/latest/version.json`（第7步）

## 故障排查

- **构建成功但 App 检查不到更新**：八成是 version.json 没更新或上传到了错误路径。
  确认 `releases/latest/version.json` 的 version 已是新版本（见第7步验证命令）。
- **upload-to-oss / create-release 失败，报 "Unable to download artifact(s) ... after 5 retries"**：
  GitHub 自 2026-06-16 起强制 Node20→Node24，老版 `actions/download-artifact@v4` 在 runner 上
  下载大文件（数百MB 安装包）会失败。workflow 已改用 runner 预装的 `gh run download` + 30s 间隔
  重试规避（见 `.github/workflows/build-releases.yml` 的 upload-to-oss / create-release）。
  若仍失败，可重跑该 job：`gh run rerun <run-id> --failed`。
- **安装包已在 OSS 但 version.json 是旧的**：无需重新构建，本地直接改 version.json 后执行第7步上传即可。
