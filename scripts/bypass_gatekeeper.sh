#!/bin/bash
# 绕过macOS Gatekeeper验证的安装脚本

set -e

APP_PATH="$1"

if [ -z "$APP_PATH" ]; then
    echo "用法: $0 <应用路径>"
    echo "示例: $0 /Applications/GeneticImprove.app"
    exit 1
fi

echo "🔓 处理macOS安全验证..."

# 方法1: 移除隔离属性
echo "📝 移除隔离属性..."
sudo xattr -r -d com.apple.quarantine "$APP_PATH" 2>/dev/null || true

# 方法2: 添加到安全白名单
echo "📋 添加到安全白名单..."
sudo spctl --add "$APP_PATH" 2>/dev/null || true

# 方法3: 标记为已验证
echo "✅ 标记为已验证..."
sudo xattr -w com.apple.security.cs.allow-jit 1 "$APP_PATH" 2>/dev/null || true

# 方法4: 创建自定义验证规则
echo "🛡️ 创建验证规则..."
APP_NAME=$(basename "$APP_PATH" .app)
sudo spctl --add --label "$APP_NAME" "$APP_PATH" 2>/dev/null || true
sudo spctl --enable --label "$APP_NAME" 2>/dev/null || true

echo "🎉 处理完成！应用现在应该可以正常启动。"
echo "如果仍有问题，请右键点击应用选择'打开'。"