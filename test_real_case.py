"""
实际案例测试脚本
母牛：22085，父号：151HO04221
配种公牛：551HO04221
"""

from core.inbreeding.path_inbreeding_calculator import PathInbreedingCalculator
from test_setup import setup_test_data

def test_real_case():
    """测试实际案例 - 母牛22085与公牛551HO04221的近交系数计算"""
    print("=" * 80)
    print("测试实际案例：母牛22085，父号151HO04221，配种公牛551HO04221")
    print("=" * 80)
    
    # 设置测试数据
    pedigree_db = setup_test_data()
    
    # 初始化计算器
    calculator = PathInbreedingCalculator()
    
    # 测试案例IDs
    mother_cow_id = '22085'         # 母牛ID
    father_bull_id = '151HO04221'   # 父亲ID
    mating_bull_id = '551HO04221'   # 配种公牛ID
    
    # 打印系谱信息
    print("\n步骤1：检查系谱信息")
    print(f"母牛ID: {mother_cow_id}")
    cow_info = pedigree_db.pedigree.get(mother_cow_id, {})
    print(f"母牛父亲: {cow_info.get('sire', 'unknown')}")
    print(f"母牛母亲: {cow_info.get('dam', 'unknown')}")
    
    print(f"\n父亲ID: {father_bull_id}")
    father_info = pedigree_db.pedigree.get(father_bull_id, {})
    print(f"父亲的父亲: {father_info.get('sire', 'unknown')}")
    print(f"父亲的母亲: {father_info.get('dam', 'unknown')}")
    
    print(f"\n配种公牛ID: {mating_bull_id}")
    mating_bull_info = pedigree_db.pedigree.get(mating_bull_id, {})
    print(f"配种公牛的父亲: {mating_bull_info.get('sire', 'unknown')}")
    print(f"配种公牛的母亲: {mating_bull_info.get('dam', 'unknown')}")
    
    # 分析系谱中的共同祖先
    print("\n步骤2：手动分析可能的共同祖先")
    if father_info.get('sire') == mating_bull_info.get('sire'):
        common_ancestor = father_info.get('sire')
        print(f"找到共同祖先: {common_ancestor} (父亲与配种公牛有同一个父亲)")
    
    # 计算后代近交系数
    print("\n步骤3：计算后代近交系数")
    print(f"计算 {mating_bull_id} 与 {mother_cow_id} 后代的近交系数...")
    inbreeding, contributions, paths = calculator.calculate_potential_offspring_inbreeding(mating_bull_id, mother_cow_id)
    
    # 打印结果
    print(f"\n后代近交系数: {inbreeding*100:.4f}%")
    print(f"共同祖先数量: {len(contributions)}")
    
    if contributions:
        print("\n共同祖先列表:")
        for i, (ancestor, contribution) in enumerate(sorted(contributions.items(), key=lambda x: x[1], reverse=True)):
            print(f"{i+1}. {ancestor}: {contribution*100:.4f}%")
            
        # 获取贡献最大的祖先的路径
        top_ancestor = max(contributions.items(), key=lambda x: x[1])[0]
        print(f"\n贡献最大的祖先 {top_ancestor} 的路径:")
        for i, (path_str, path_contrib) in enumerate(paths.get(top_ancestor, [])[:3]):
            print(f"{i+1}. 贡献: {path_contrib*100:.4f}%")
            print(f"   {path_str}")
    else:
        print("未发现共同祖先")
    
    print("\n测试完成!")

if __name__ == "__main__":
    test_real_case() 