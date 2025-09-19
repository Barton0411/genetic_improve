import sys
sys.path.insert(0, '.')

from api.data_client import get_data_client

client = get_data_client()
success, version, update_time, message = client.get_database_version_with_time()

print(f"成功: {success}")
print(f"版本: {version}")
print(f"更新时间: {update_time}")
print(f"消息: {message}")
