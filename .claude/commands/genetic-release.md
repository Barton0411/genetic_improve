---
description: 发布新版本，更新版本号、提交、打tag、监控构建、验证OSS
---

# 版本发布流程

版本号 `主.次.修订.构建`，默认末位 +1。全程用变量，别硬编码版本号：

```bash
git fetch origin --tags --force
# PREV = git 远程最新版本号（不信本地，本地可能落后）
PREV=$(git ls-remote --tags origin | grep -oE 'v[0-9.]+$' | sed 's/v//' | sort -V | tail -1)
NEW=<PREV 末位+1>            # 自己算，例如 PREV=1.2.3.6 → NEW=1.2.3.7
echo "PREV=$PREV  NEW=$NEW"
git log --oneline HEAD..origin/main   # 必须为空；非空说明本地落后，先 git pull --rebase
```

## 步骤

1. **改 version.py**：`VERSION="$NEW"`；`VERSION_HISTORY` 开头插入新记录（date 先跑 `date +%Y-%m-%d`）。
2. **改 version.json**（❗和 version.py 是两个文件，最易漏）：`version`、`mac_download_url`、`win_download_url`、`changes` 四处都改成 `$NEW`；段落间用 `""` 分隔。
3. **提交**（add 和 commit 串一条命令，确认暂存数 >0；不加 AI 署名）：
   ```bash
   git add version.py version.json <本次改动文件> \
    && echo "暂存 $(git diff --cached --name-only|wc -l) 个" \
    && git commit -m "v$NEW: 简短描述"
   git push origin main
   ```
4. **打 tag 并核对指向**（重发版先删干净同名 tag）：
   ```bash
   git push origin ":refs/tags/v$NEW" 2>/dev/null; git tag -d "v$NEW" 2>/dev/null
   git tag -a "v$NEW" -m "Release v$NEW" && git push origin "v$NEW"
   # 核对：tag commit 必须 == HEAD，tag 里 version.json 必须 == $NEW
   git rev-parse "v$NEW^{commit}" HEAD
   git show "v$NEW:version.json" | python3 -c "import json,sys;print(json.load(sys.stdin)['version'])"
   ```
5. **监控**（确认有 run 跑在目标 commit 上、全 success，约 10-15 分钟，别被旧 failure run 迷惑）：
   ```bash
   gh run list --workflow=build-releases.yml --limit 5 --json databaseId,headSha,status,conclusion \
     -q '.[]|"\(.databaseId) \(.headSha[0:8]) \(.status)/\(.conclusion//"-")"'
   ```
6. **验证 OSS**（客户端读这个，必须是 `$NEW`）：
   ```bash
   curl -s --noproxy '*' "https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/latest/version.json?t=$(date +%s)" \
     | python3 -c "import json,sys;print('OSS=',json.load(sys.stdin)['version'])"
   ```
   若不是 `$NEW`，兜底手动传（路径是 `releases/latest/`，不是 `latest/`）：
   `/usr/local/bin/ossutil cp version.json oss://genetic-improve/releases/latest/version.json -f`

## 关键防坑

- **PREV 取 git 远程最新**，不取本地（本地可能落后/上次没推全）。
- **version.py 和 version.json 必须同步改**，漏 version.json → App 收不到更新。
- **打 tag 后必核对** tag commit==HEAD 且 tag 里 version.json==$NEW（曾多次指错 commit、构建出旧包）。
- **git add 可能静默失效**：commit 前确认暂存数 >0（用上面 `&&` 串联写法）。
- CI 的 version.json 上传已根治（workflow 里 `git checkout HEAD -- version.json` 防 artifact 污染），正常无需手动补；OSS 不是新版就用第6步兜底。
