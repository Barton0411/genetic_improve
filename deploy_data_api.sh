#!/bin/bash

# 部署data_api.py到服务器的脚本

echo "准备部署data_api.py到服务器..."

# 服务器信息
SERVER="ecs-user@39.96.189.27"
REMOTE_PATH="/home/ecs-user/api/data_api.py"
LOCAL_PATH="./api/data_api.py"

# 上传文件
echo "上传data_api.py到服务器..."
scp $LOCAL_PATH $SERVER:$REMOTE_PATH

if [ $? -eq 0 ]; then
    echo "✓ 文件上传成功"

    # 重启服务
    echo "重启data_api服务..."
    ssh $SERVER "cd /home/ecs-user/api && pm2 restart data_api"

    if [ $? -eq 0 ]; then
        echo "✓ 服务重启成功"
        echo ""
        echo "部署完成！data_api.py已更新，数据API端点现在无需认证。"
        echo ""
        echo "更新内容："
        echo "- /api/data/version - 获取数据库版本（无需认证）"
        echo "- /api/data/bull_library - 获取公牛库数据（无需认证）"
        echo "- /api/data/missing_bulls - 上传缺失公牛记录（无需认证）"
    else
        echo "✗ 服务重启失败，请手动检查"
    fi
else
    echo "✗ 文件上传失败，请检查SSH连接"
fi