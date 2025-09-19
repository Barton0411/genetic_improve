#!/usr/bin/env python3
"""模拟实际场景的测试"""

from pathlib import Path
import sys

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.breeding_calc.base_calculation import BaseCowCalculation

# 创建实例
calc = BaseCowCalculation()

# 模拟缺失的公牛数据
missing_bulls = ['779HO98765', '291HO22269']

# 调用上传方法
print(f"准备上传缺失公牛: {', '.join(missing_bulls)}")
success = calc.process_missing_bulls(
    missing_bulls=missing_bulls,
    source='bull_traits_calc',
    username='test_user'
)

if success:
    print("✅ 测试成功！缺失公牛记录已成功上传到云端数据库")
else:
    print("❌ 测试失败")