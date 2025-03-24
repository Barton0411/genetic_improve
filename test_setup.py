from core.data.update_manager import get_pedigree_db

def setup_test_data():
    """设置测试数据"""
    print("开始设置测试数据...")
    
    # 获取系谱库实例
    pedigree_db = get_pedigree_db()
    
    # 添加测试系谱数据
    test_data = {
        # 母牛信息
        '22085': {
            'id': '22085',
            'type': 'cow',
            'sire': '151HO04221',  # 父亲
            'dam': 'unknown',      # 母亲
            'generation': 0
        },
        # 父亲信息
        '151HO04221': {
            'id': '151HO04221',
            'type': 'bull',
            'sire': 'HOFA001',     # 外祖父
            'dam': 'HODAM001',     # 外祖母
            'generation': 1,
            'gib': 0.06            # 模拟GIB值
        },
        # 配种公牛
        '551HO04221': {
            'id': '551HO04221',
            'type': 'bull',
            'sire': 'HOFA001',     # 与母牛父亲有共同父亲
            'dam': 'HODAM002',     # 不同的母亲
            'generation': 1,
            'gib': 0.05            # 模拟GIB值  
        },
        # 共同祖先
        'HOFA001': {
            'id': 'HOFA001',
            'type': 'bull',
            'sire': 'HOGRANDFA',
            'dam': 'HOGRANDDAM',
            'generation': 2,
            'gib': 0.04
        },
        # 其他祖先
        'HODAM001': {
            'id': 'HODAM001',
            'type': 'cow',
            'sire': 'HOGRANDFA',  # 与公共父亲有同一个父亲
            'dam': 'HOGRANDDAM2',
            'generation': 2
        },
        'HODAM002': {
            'id': 'HODAM002',
            'type': 'cow',
            'sire': 'HOGRANDFA2', 
            'dam': 'HOGRANDDAM2',
            'generation': 2
        },
        # 更远的祖先
        'HOGRANDFA': {
            'id': 'HOGRANDFA',
            'type': 'bull',
            'sire': 'unknown',
            'dam': 'unknown',
            'generation': 3,
            'gib': 0.03
        },
        'HOGRANDDAM': {
            'id': 'HOGRANDDAM',
            'type': 'cow',
            'sire': 'unknown',
            'dam': 'unknown',
            'generation': 3
        },
        'HOGRANDFA2': {
            'id': 'HOGRANDFA2',
            'type': 'bull',
            'sire': 'unknown',
            'dam': 'unknown',
            'generation': 3,
            'gib': 0.02
        },
        'HOGRANDDAM2': {
            'id': 'HOGRANDDAM2',
            'type': 'cow',
            'sire': 'unknown',
            'dam': 'unknown', 
            'generation': 3
        }
    }
    
    # 将数据添加到系谱库
    for animal_id, animal_info in test_data.items():
        pedigree_db.pedigree[animal_id] = animal_info
        print(f"添加 {animal_id} 到系谱库")
    
    print(f"系谱库现在包含 {len(pedigree_db.pedigree)} 个动物")
    
    # 移除错误的ID映射尝试
    # 检查PedigreeDB是否有standardize_animal_id方法
    if hasattr(pedigree_db, 'standardize_animal_id'):
        print("测试标准化ID:")
        print(f"551HO04221 -> {pedigree_db.standardize_animal_id('551HO04221', 'bull')}")
        print(f"151HO04221 -> {pedigree_db.standardize_animal_id('151HO04221', 'bull')}")
    
    print("测试数据设置完成!")
    return pedigree_db

if __name__ == "__main__":
    setup_test_data()
    print("\n系谱库设置完成，请运行test_inbreeding.py测试近交系数计算!") 