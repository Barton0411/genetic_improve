#!/bin/bash

echo "🧪 开始测试版本更新功能..."
echo "================================"

# 备份当前版本
cp version.py version.py.bak

# 修改为旧版本
sed -i '' 's/VERSION = "1.0.4"/VERSION = "1.0.3"/' version.py

echo "📌 设置本地版本为: 1.0.3"
echo "📡 检查服务器版本..."
echo ""

# 运行测试
python3 test_version_update.py

# 恢复版本
mv version.py.bak version.py

echo ""
echo "✅ 测试完成！版本已恢复为1.0.4"