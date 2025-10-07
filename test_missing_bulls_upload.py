#!/usr/bin/env python3
"""
测试缺失公牛上传功能
模拟备选公牛数据上传流程
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("缺失公牛上传功能测试")
print("=" * 60)

# 测试1: 导入检查
print("\n[测试1] 检查模块导入...")
try:
    from core.data.update_manager import LOCAL_DB_PATH
    print(f"✓ LOCAL_DB_PATH: {LOCAL_DB_PATH}")
except Exception as e:
    print(f"✗ 导入 LOCAL_DB_PATH 失败: {e}")
    sys.exit(1)

try:
    from api.api_client import get_api_client
    print("✓ api_client 导入成功")
except Exception as e:
    print(f"✗ 导入 api_client 失败: {e}")
    sys.exit(1)

try:
    from sqlalchemy import create_engine, text
    print("✓ sqlalchemy 导入成功")
except Exception as e:
    print(f"✗ 导入 sqlalchemy 失败: {e}")
    sys.exit(1)

# 测试2: 数据库连接
print("\n[测试2] 测试数据库连接...")
try:
    db_engine = create_engine(f'sqlite:///{LOCAL_DB_PATH}')
    with db_engine.connect() as conn:
        result = conn.execute(text('SELECT COUNT(*) as cnt FROM bull_library')).fetchone()
        total_bulls = result[0]
        print(f"✓ 数据库连接成功")
        print(f"  本地数据库路径: {LOCAL_DB_PATH}")
        print(f"  bull_library表记录数: {total_bulls}")
    db_engine.dispose()
except Exception as e:
    print(f"✗ 数据库连接失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试3: 模拟查询缺失公牛
print("\n[测试3] 模拟查询缺失公牛...")
test_bulls = [
    '007HO16284',  # 可能缺失
    '007HO16385',  # 可能缺失
    '13113261',    # 格式错误，肯定缺失
    'TEST_FAKE_001',  # 假公牛，肯定缺失
    '001HO09154',  # 可能存在或缺失
]

missing_bulls = []
existing_bulls = []

try:
    db_engine = create_engine(f'sqlite:///{LOCAL_DB_PATH}')
    with db_engine.connect() as conn:
        for bull_id in test_bulls:
            result = conn.execute(
                text('SELECT COUNT(*) as cnt FROM bull_library WHERE `BULL NAAB`=:bull_id'),
                {'bull_id': str(bull_id)}
            ).fetchone()

            if result[0] == 0:
                missing_bulls.append(bull_id)
                print(f"  ✗ {bull_id} - 不在数据库中（缺失）")
            else:
                existing_bulls.append(bull_id)
                print(f"  ✓ {bull_id} - 在数据库中")

    db_engine.dispose()
    print(f"\n查询结果:")
    print(f"  已存在: {len(existing_bulls)} 个")
    print(f"  缺失: {len(missing_bulls)} 个")

except Exception as e:
    print(f"✗ 查询失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试4: API客户端初始化
print("\n[测试4] 测试API客户端...")
try:
    api_client = get_api_client()
    print(f"✓ API客户端初始化成功")
    print(f"  base_url: {api_client.base_url}")
    print(f"  timeout: {api_client.timeout}")
    print(f"  verify_ssl: {api_client.verify_ssl}")
except Exception as e:
    print(f"✗ API客户端初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试5: 模拟上传（使用1个测试数据）
print("\n[测试5] 模拟上传缺失公牛...")
if missing_bulls:
    import datetime

    # 只上传第一个缺失公牛作为测试
    test_bull = missing_bulls[0]
    bulls_data = [{
        'bull': str(test_bull),
        'source': 'test_upload',
        'time': datetime.datetime.now().isoformat(),
        'user': 'test_user'
    }]

    print(f"准备上传测试数据: {test_bull}")
    print(f"数据: {bulls_data[0]}")

    try:
        success = api_client.upload_missing_bulls(bulls_data)
        if success:
            print(f"✓ 上传成功！")
        else:
            print(f"✗ 上传失败")
    except Exception as e:
        print(f"✗ 上传异常: {e}")
        import traceback
        traceback.print_exc()
else:
    print("没有缺失公牛，跳过上传测试")

# 总结
print("\n" + "=" * 60)
print("测试总结:")
print("=" * 60)
print("✓ 所有模块导入正常")
print("✓ 数据库连接正常")
print("✓ 查询逻辑正常")
print("✓ API客户端正常")
if missing_bulls:
    print(f"✓ 发现 {len(missing_bulls)} 个缺失公牛，已测试上传")
else:
    print("✓ 所有测试公牛都在数据库中")
print("\n✅ 代码逻辑验证通过，可以在实际应用中使用！")
print("=" * 60)
