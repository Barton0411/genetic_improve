import sys
sys.path.insert(0, '.')

from core.data.update_manager import check_and_update_database

print("开始数据库更新测试...")
check_and_update_database()
print("更新完成")

# 验证结果
from core.data.update_manager import get_local_db_version_with_time
version, time = get_local_db_version_with_time()
print(f"本地数据库版本: {version}")
print(f"更新时间: {time}")
