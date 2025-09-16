#!/bin/bash

# Mac应用打包脚本
# 使用方法: ./build_mac.sh

set -e  # 遇到错误立即退出

echo "🚀 开始构建 Genetic Improve Mac 应用..."

# 检查是否在macOS上运行
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ 此脚本只能在 macOS 上运行"
    exit 1
fi

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# 获取版本号
VERSION=$(python3 -c "from version import get_version; print(get_version())")
echo "📦 构建版本: $VERSION"

# 清理之前的构建文件
echo "🧹 清理之前的构建文件..."
rm -rf build/
rm -rf dist/
rm -rf __pycache__/
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# 检查并安装构建依赖
echo "📋 检查构建依赖..."
if ! python3 -c "import pyinstaller" 2>/dev/null; then
    echo "📦 安装 PyInstaller..."
    pip3 install pyinstaller
fi

# 检查是否有应用图标
ICON_PATH="gui/icons/app_icon.icns"
if [[ ! -f "$ICON_PATH" ]]; then
    echo "⚠️  警告: 未找到应用图标 $ICON_PATH"
    echo "   将使用默认图标"
fi

# 运行 PyInstaller
echo "🔨 运行 PyInstaller..."
python3 -m PyInstaller GeneticImprove.spec --clean --noconfirm

# 检查构建结果
APP_PATH="dist/GeneticImprove.app"
if [[ ! -d "$APP_PATH" ]]; then
    echo "❌ 应用构建失败: 未找到 $APP_PATH"
    exit 1
fi

echo "✅ 应用构建完成: $APP_PATH"

# 验证应用结构
echo "🔍 验证应用结构..."
if [[ ! -f "$APP_PATH/Contents/MacOS/GeneticImprove" ]]; then
    echo "❌ 应用结构错误: 未找到可执行文件"
    exit 1
fi

# 显示应用大小
APP_SIZE=$(du -sh "$APP_PATH" | cut -f1)
echo "📏 应用大小: $APP_SIZE"

# 创建 DMG 安装包
echo "📦 创建 DMG 安装包..."

DMG_NAME="GeneticImprove_v${VERSION}_mac"
DMG_PATH="dist/${DMG_NAME}.dmg"

# 删除旧的 DMG
rm -f "$DMG_PATH"

# 创建临时目录用于 DMG 内容
DMG_DIR="dist/dmg_temp"
rm -rf "$DMG_DIR"
mkdir -p "$DMG_DIR"

# 复制应用到临时目录
cp -R "$APP_PATH" "$DMG_DIR/"

# 创建应用程序文件夹的符号链接
ln -s /Applications "$DMG_DIR/Applications"

# 使用 hdiutil 创建 DMG
echo "🔧 正在创建 DMG 文件..."
hdiutil create -volname "Genetic Improve" \
    -srcfolder "$DMG_DIR" \
    -ov -format UDZO \
    "$DMG_PATH"

# 清理临时目录
rm -rf "$DMG_DIR"

# 检查 DMG 是否创建成功
if [[ ! -f "$DMG_PATH" ]]; then
    echo "❌ DMG 创建失败"
    exit 1
fi

# 显示 DMG 大小
DMG_SIZE=$(du -sh "$DMG_PATH" | cut -f1)
echo "📏 DMG 大小: $DMG_SIZE"

# 验证 DMG
echo "🔍 验证 DMG..."
hdiutil verify "$DMG_PATH"

echo ""
echo "🎉 构建完成!"
echo "📱 应用文件: $APP_PATH"
echo "💿 安装包: $DMG_PATH"
echo ""
echo "📝 下一步:"
echo "   1. 测试安装包是否正常工作"
echo "   2. 如需代码签名，请运行: codesign -s 'Developer ID Application' '$APP_PATH'"
echo "   3. 上传到服务器或分发给用户"
echo ""

# 可选: 自动打开 dist 目录
if [[ -n "$OPEN_DIST" ]]; then
    open dist/
fi