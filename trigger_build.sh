#!/bin/bash

# 触发GitHub Actions构建的脚本
# 使用方法: ./trigger_build.sh [version]

VERSION=${1:-$(python3 -c "from version import get_version; print(get_version())")}

echo "🚀 准备触发 GitHub Actions 构建..."
echo "📦 版本: v$VERSION"

# 检查是否有未提交的更改
if ! git diff-index --quiet HEAD --; then
    echo "⚠️  警告: 检测到未提交的更改"
    echo "是否要先提交这些更改? (y/n)"
    read -r answer
    if [[ $answer == "y" || $answer == "Y" ]]; then
        git add .
        git commit -m "准备发布 v$VERSION"
    fi
fi

# 创建并推送标签
echo "🏷️  创建版本标签..."
git tag -a "v$VERSION" -m "Release v$VERSION"

echo "📤 推送到 GitHub..."
git push origin main
git push origin "v$VERSION"

echo ""
echo "✅ 构建已触发!"
echo "🔗 查看构建进度: https://github.com/Barton0411/genetic_improve/actions"
echo ""
echo "构建完成后，安装包将可在以下位置下载:"
echo "📦 Release页面: https://github.com/Barton0411/genetic_improve/releases"
echo "📦 Artifacts: https://github.com/Barton0411/genetic_improve/actions (临时下载)"