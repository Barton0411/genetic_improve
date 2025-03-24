from core.inbreeding.path_inbreeding_calculator import PathInbreedingCalculator
# 导入并运行测试数据设置
from test_setup import setup_test_data

def test_inbreeding():
    print("开始测试近交系数计算...")
    
    # 设置测试数据
    setup_test_data()
    
    # 初始化计算器
    calculator = PathInbreedingCalculator()
    
    # 测试案例
    bull_id = '551HO04221'
    cow_id = '22085'
    
    # 检查公牛、母牛以及父号的关系
    print(f"检查配种关系: 母牛={cow_id}, 公牛={bull_id}")
    
    # 获取系谱库实例
    from core.data.update_manager import get_pedigree_db
    pedigree_db = get_pedigree_db()
    
    # 获取母牛父亲信息
    cow_info = pedigree_db.pedigree.get(cow_id, {})
    cow_father = cow_info.get('sire', 'unknown')
    print(f"母牛父亲: {cow_father}")
    
    # 检查是否是直系血亲
    is_direct_relative = (cow_father == bull_id)
    print(f"是否直系血亲: {is_direct_relative}")
    
    # 打印预期的共同祖先
    print("\n预期共同祖先验证:")
    # 获取公牛和母牛父亲的系谱
    bull_info = pedigree_db.pedigree.get(bull_id, {})
    sire_info = pedigree_db.pedigree.get(cow_father, {})
    
    # 检查父亲
    bull_father = bull_info.get('sire', 'unknown')
    sire_father = sire_info.get('sire', 'unknown')
    if bull_father == sire_father:
        print(f"共同祖先1: {bull_father} (双方父亲相同)")
    
    # 检查更远的祖先
    if bull_father != 'unknown' and sire_father != 'unknown':
        bull_gf = pedigree_db.pedigree.get(bull_father, {}).get('sire', 'unknown')
        sire_gf = pedigree_db.pedigree.get(sire_father, {}).get('sire', 'unknown')
        if bull_gf == sire_gf:
            print(f"共同祖先2: {bull_gf} (双方祖父相同)")
    
    # 计算潜在后代的近交系数
    print(f"\n计算 {bull_id} 与 {cow_id} 后代的近交系数...")
    inbreeding, contributions, paths = calculator.calculate_potential_offspring_inbreeding(bull_id, cow_id)
    
    # 打印基本结果
    print(f"后代近交系数: {inbreeding*100:.4f}%")
    print(f"共同祖先数量: {len(contributions)}")
    
    # 打印共同祖先列表
    print("\n共同祖先贡献排名:")
    for i, (ancestor, contribution) in enumerate(sorted(contributions.items(), key=lambda x: x[1], reverse=True)):
        print(f"{i+1}. {ancestor}: {contribution*100:.4f}%")
        if i < 3 and paths.get(ancestor):  # 只打印前3个祖先的路径示例
            print(f"   路径示例: {paths[ancestor][0][0]}")
    
    # 只打印前几个路径
    if contributions:
        # 获取贡献最大的祖先
        top_ancestor = max(contributions.items(), key=lambda x: x[1])[0]
        print(f"\n贡献最大的祖先 {top_ancestor} 的路径:")
        for i, (path_str, path_contrib) in enumerate(paths.get(top_ancestor, [])[:3]):
            print(f"{i+1}. 贡献: {path_contrib*100:.4f}%")
            print(f"   {path_str}")
    
    print("\n测试完成!")

if __name__ == "__main__":
    test_inbreeding() 