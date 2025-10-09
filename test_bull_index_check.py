"""
测试公牛育种指数缺失检查逻辑（只检查有库存的公牛）
"""

import pandas as pd
from pathlib import Path
import sys

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_bull_index_check():
    """测试公牛育种指数缺失检查"""
    print("=" * 60)
    print("测试公牛育种指数缺失检查逻辑")
    print("=" * 60)

    # 创建测试数据
    test_data = pd.DataFrame({
        'bull_id': ['001HO16890', '567HO11111', '567HO11112', '567HO11113', '567HO11114'],
        '支数': [100, 0, 0, 50, 0],  # 有库存和无库存的公牛
        'Index Score': [85.5, None, None, None, None]  # 有1个有指数，4个缺失指数
    })

    print("\n测试数据:")
    print(test_data)
    print()

    # 模拟检查逻辑
    stock_col = '支数'

    # 只检查有库存的公牛（支数 > 0）
    missing_bulls_with_stock = test_data[
        (test_data['Index Score'].isna()) &
        (test_data[stock_col] > 0)
    ]['bull_id'].tolist()

    # 统计没有库存的缺失公牛（不会报错，只记录日志）
    missing_bulls_no_stock = test_data[
        (test_data['Index Score'].isna()) &
        (test_data[stock_col] <= 0)
    ]['bull_id'].tolist()

    print("检查结果:")
    print(f"  - 缺失指数且有库存的公牛（会报错）: {missing_bulls_with_stock}")
    print(f"  - 缺失指数但无库存的公牛（跳过，不报错）: {missing_bulls_no_stock}")
    print()

    # 验证结果
    expected_with_stock = ['567HO11113']  # 只有这1头有库存但缺指数
    expected_no_stock = ['567HO11111', '567HO11112', '567HO11114']  # 这3头无库存

    if missing_bulls_with_stock == expected_with_stock:
        print("✓ 有库存公牛检查正确")
    else:
        print(f"✗ 有库存公牛检查错误，期望 {expected_with_stock}，实际 {missing_bulls_with_stock}")

    if missing_bulls_no_stock == expected_no_stock:
        print("✓ 无库存公牛检查正确")
    else:
        print(f"✗ 无库存公牛检查错误，期望 {expected_no_stock}，实际 {missing_bulls_no_stock}")

    print()
    print("=" * 60)
    print("测试总结:")
    print("  - 原来的逻辑会报错提示所有4头缺失指数的公牛")
    print("  - 修改后的逻辑只会报错提示1头有库存的公牛")
    print("  - 3头无库存的公牛会被跳过，不会触发错误提示")
    print("=" * 60)


if __name__ == "__main__":
    test_bull_index_check()
