#!/bin/bash
# macOS应用代码签名脚本

set -e

APP_PATH="$1"
DEVELOPER_ID="$2"

if [ -z "$APP_PATH" ] || [ -z "$DEVELOPER_ID" ]; then
    echo "用法: $0 <应用路径> <开发者ID>"
    echo "示例: $0 /path/to/GeneticImprove.app \"Developer ID Application: Your Name (XXXXXXXXXX)\""
    exit 1
fi

echo "🔐 开始对应用进行代码签名..."
echo "应用路径: $APP_PATH"
echo "开发者ID: $DEVELOPER_ID"

# 检查应用是否存在
if [ ! -d "$APP_PATH" ]; then
    echo "❌ 错误: 应用路径不存在: $APP_PATH"
    exit 1
fi

# 递归签名所有框架和库
echo "📝 签名框架和库文件..."
find "$APP_PATH" -type f \( -name "*.dylib" -o -name "*.so" -o -name "*.framework" \) -exec codesign --force --verify --verbose --sign "$DEVELOPER_ID" {} \;

# 签名Python解释器（如果存在）
if [ -f "$APP_PATH/Contents/MacOS/python" ]; then
    echo "🐍 签名Python解释器..."
    codesign --force --verify --verbose --sign "$DEVELOPER_ID" "$APP_PATH/Contents/MacOS/python"
fi

# 签名主可执行文件
EXECUTABLE=$(find "$APP_PATH/Contents/MacOS" -type f -perm +111 | head -n 1)
if [ -n "$EXECUTABLE" ]; then
    echo "⚡ 签名主可执行文件: $EXECUTABLE"
    codesign --force --verify --verbose --sign "$DEVELOPER_ID" "$EXECUTABLE"
fi

# 签名整个应用包
echo "📦 签名整个应用包..."
codesign --force --verify --verbose --sign "$DEVELOPER_ID" "$APP_PATH"

# 验证签名
echo "✅ 验证代码签名..."
codesign --verify --deep --strict --verbose=2 "$APP_PATH"
spctl --assess --type execute --verbose "$APP_PATH"

echo "🎉 代码签名完成！"
echo "应用现在可以通过macOS Gatekeeper验证。"