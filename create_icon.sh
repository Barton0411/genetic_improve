#!/bin/bash

# 创建 macOS 应用图标 (.icns) 的脚本
# 使用方法: ./create_icon.sh input.png

if [[ $# -eq 0 ]]; then
    echo "使用方法: $0 <input.png>"
    echo "示例: $0 app_icon.png"
    exit 1
fi

INPUT_PNG="$1"
ICON_DIR="gui/icons"
ICONSET_DIR="$ICON_DIR/app_icon.iconset"

# 检查输入文件
if [[ ! -f "$INPUT_PNG" ]]; then
    echo "❌ 错误: 文件 '$INPUT_PNG' 不存在"
    exit 1
fi

# 创建图标目录
mkdir -p "$ICON_DIR"
mkdir -p "$ICONSET_DIR"

echo "🖼️  正在创建 macOS 应用图标..."

# 生成各种尺寸的图标
sips -z 16 16     "$INPUT_PNG" --out "$ICONSET_DIR/icon_16x16.png"
sips -z 32 32     "$INPUT_PNG" --out "$ICONSET_DIR/icon_16x16@2x.png"
sips -z 32 32     "$INPUT_PNG" --out "$ICONSET_DIR/icon_32x32.png"
sips -z 64 64     "$INPUT_PNG" --out "$ICONSET_DIR/icon_32x32@2x.png"
sips -z 128 128   "$INPUT_PNG" --out "$ICONSET_DIR/icon_128x128.png"
sips -z 256 256   "$INPUT_PNG" --out "$ICONSET_DIR/icon_128x128@2x.png"
sips -z 256 256   "$INPUT_PNG" --out "$ICONSET_DIR/icon_256x256.png"
sips -z 512 512   "$INPUT_PNG" --out "$ICONSET_DIR/icon_256x256@2x.png"
sips -z 512 512   "$INPUT_PNG" --out "$ICONSET_DIR/icon_512x512.png"
sips -z 1024 1024 "$INPUT_PNG" --out "$ICONSET_DIR/icon_512x512@2x.png"

# 创建 .icns 文件
iconutil -c icns "$ICONSET_DIR" -o "$ICON_DIR/app_icon.icns"

# 清理临时文件
rm -rf "$ICONSET_DIR"

echo "✅ 图标创建完成: $ICON_DIR/app_icon.icns"