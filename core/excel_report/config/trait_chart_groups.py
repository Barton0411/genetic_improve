"""
性状折线图分组配置

根据性状的业务含义和数值范围，将性状分组以生成合理的折线图。
同类型且Y轴范围相近的性状可以合并到一个图中（多条折线）。

数值范围参考：
- 经济指数: NM$, CM$, FM$, GM$ 约 -200 到 1000
- TPI: 约 1500 到 3000
- MILK: 约 -500 到 2000
- 乳成分产量 (FAT, PROT): 约 -20 到 100
- 乳成分百分比 (FAT%, PROT%): 约 -0.10 到 0.15
- SCS: 约 2.0 到 3.5 (越低越好)
- 繁殖性状百分比: 约 -5.0 到 5.0
- PL: 约 -5.0 到 10.0
- 产犊性状: 约 -10.0 到 10.0
- 体型综合: 约 -3.0 到 3.0
- 体型细节: 约 -3.0 到 3.0
- 健康性状: 约 -2.0 到 2.0
- 饲料效率: 约 -200 到 200
- RFI: 约 -3.0 到 3.0
"""

# 性状中文翻译（从cow_traits_calc.py导入）
from core.breeding_calc.cow_traits_calc import TRAITS_TRANSLATION

# 折线图分组配置
# 每个分组包含：
#   - name: 分组名称
#   - traits: 性状列表（可以包含多个相关性状）
#   - description: 说明
#   - y_axis_label: Y轴标签
#   - range: Y轴范围 (min, max)
#   - invert: 是否为反向指标（越低越好）
TRAIT_CHART_GROUPS = [
    # ========== 经济与综合指数 ==========
    {
        'name': '经济指数',
        'traits': ['NM$', 'CM$', 'FM$', 'GM$'],
        'description': '净利润值、奶酪净值、液奶净值、放牧净值',
        'y_axis_label': '经济指数 ($)',
        'range': (-200, 1000)
    },
    {
        'name': '育种综合指数',
        'traits': ['TPI'],
        'description': '综合育种价值指标',
        'y_axis_label': 'TPI (指数)',
        'range': (1500, 3000)
    },

    # ========== 产奶性状 ==========
    {
        'name': '产奶量',
        'traits': ['MILK'],
        'description': '产奶量育种值',
        'y_axis_label': 'MILK (磅)',
        'range': (-500, 2000)
    },
    {
        'name': '乳成分产量',
        'traits': ['FAT', 'PROT'],
        'description': '乳脂量、乳蛋白量',
        'y_axis_label': '乳成分产量 (磅)',
        'range': (-20, 100)
    },
    {
        'name': '乳成分百分比',
        'traits': ['FAT %', 'PROT%'],
        'description': '乳脂率、乳蛋白率',
        'y_axis_label': '乳成分百分比 (%)',
        'range': (-0.10, 0.15)
    },
    {
        'name': '体细胞指数',
        'traits': ['SCS'],
        'description': '体细胞数指标（越低越好）',
        'y_axis_label': 'SCS (指数)',
        'range': (2.0, 3.5),
        'invert': True
    },

    # ========== 繁殖性状 ==========
    {
        'name': '繁殖性状-怀孕率与受胎率',
        'traits': ['DPR', 'HCR', 'CCR'],
        'description': '女儿怀孕率、青年牛受胎率、成母牛受胎率',
        'y_axis_label': '繁殖性状 (%)',
        'range': (-5, 5)
    },
    {
        'name': '生产寿命',
        'traits': ['PL'],
        'description': '生产寿命',
        'y_axis_label': 'PL (月)',
        'range': (-5, 10)
    },
    {
        'name': '产犊性状',
        'traits': ['SCE', 'DCE', 'SSB', 'DSB'],
        'description': '配种产犊难易度、女儿产犊难易度、配种死胎率、女儿死淘率',
        'y_axis_label': '产犊性状 (%)',
        'range': (-10, 10)
    },
    {
        'name': '妊娠与产犊月龄',
        'traits': ['GL', 'EFC'],
        'description': '妊娠长度、首次产犊月龄',
        'y_axis_label': '时间 (天/月)',
        'range': (-5, 5)
    },

    # ========== 体型综合指数 ==========
    {
        'name': '体型综合指数',
        'traits': ['PTAT', 'UDC', 'FLC', 'BDC'],
        'description': '体型综合、乳房综合、肢蹄综合、体重综合',
        'y_axis_label': '综合指数',
        'range': (-3, 3)
    },

    # ========== 体型细节-体躯 ==========
    {
        'name': '体型-体躯',
        'traits': ['ST', 'SG', 'BD', 'DF'],
        'description': '体高、强壮度、体深、乳用特征',
        'y_axis_label': '体型评分',
        'range': (-3, 3)
    },

    # ========== 体型细节-尻部与后肢 ==========
    {
        'name': '体型-尻部与后肢',
        'traits': ['RA', 'RW', 'LS', 'LR'],
        'description': '尻角度、尻宽、后肢侧视、后肢后视',
        'y_axis_label': '体型评分',
        'range': (-3, 3)
    },

    # ========== 体型细节-肢蹄 ==========
    {
        'name': '体型-肢蹄',
        'traits': ['FA', 'FLS'],
        'description': '蹄角度、肢蹄评分',
        'y_axis_label': '体型评分',
        'range': (-3, 3)
    },

    # ========== 体型细节-乳房结构 ==========
    {
        'name': '体型-乳房结构',
        'traits': ['FU', 'UH', 'UW', 'UC', 'UD'],
        'description': '前方附着、后房高度、后方宽度、悬韧带、乳房深度',
        'y_axis_label': '体型评分',
        'range': (-3, 3)
    },

    # ========== 体型细节-乳头 ==========
    {
        'name': '体型-乳头',
        'traits': ['FT', 'RT', 'TL'],
        'description': '前乳头位置、后乳头位置、乳头长度',
        'y_axis_label': '体型评分',
        'range': (-3, 3)
    },

    # ========== 饲料效率 ==========
    {
        'name': '饲料效率',
        'traits': ['FE', 'FS'],
        'description': '饲料效率指数、饲料节约指数',
        'y_axis_label': '饲料效率 (指数)',
        'range': (-200, 200)
    },
    {
        'name': '剩余饲料采食量',
        'traits': ['RFI'],
        'description': '剩余饲料采食量（越低越好）',
        'y_axis_label': 'RFI (磅/天)',
        'range': (-3, 3),
        'invert': True
    },

    # ========== 健康性状 ==========
    {
        'name': '综合健康指数',
        'traits': ['FI', 'HI'],
        'description': '繁殖力指数、健康指数',
        'y_axis_label': '健康指数',
        'range': (-2, 2)
    },
    {
        'name': '存活率',
        'traits': ['LIV', 'HLiv'],
        'description': '存活率、后备牛存活率',
        'y_axis_label': '存活率 (%)',
        'range': (-5, 5)
    },
    {
        'name': '疾病抗性-乳房与生殖',
        'traits': ['MAST', 'MET', 'RP'],
        'description': '乳房炎抗病性、子宫炎抗病性、胎衣不下抗病性',
        'y_axis_label': '抗病性指数',
        'range': (-2, 2)
    },
    {
        'name': '疾病抗性-代谢病',
        'traits': ['KET', 'DA', 'MFV'],
        'description': '酮病抗病性、变胃抗病性、产后瘫抗病性',
        'y_axis_label': '抗病性指数',
        'range': (-2, 2)
    },

    # ========== 其他 ==========
    {
        'name': '排乳速度',
        'traits': ['Milk Speed'],
        'description': '排乳速度',
        'y_axis_label': 'Milk Speed (指数)',
        'range': (-2, 2)
    }
]


def get_chart_groups_for_traits(available_traits):
    """
    根据实际存在的性状，返回需要创建的图表分组

    Args:
        available_traits: 实际数据中存在的性状列表

    Returns:
        list: 需要创建的图表分组列表
    """
    result_groups = []

    for group in TRAIT_CHART_GROUPS:
        # 检查该组中有哪些性状实际存在
        existing_traits = [t for t in group['traits'] if t in available_traits]

        if not existing_traits:
            # 该组所有性状都不存在，跳过
            continue

        # 创建新的分组配置
        new_group = group.copy()
        new_group['traits'] = existing_traits
        new_group['trait_count'] = len(existing_traits)

        result_groups.append(new_group)

    return result_groups


def get_trait_display_name(trait):
    """获取性状的显示名称（中英文）"""
    chinese = TRAITS_TRANSLATION.get(trait, trait)
    return f"{trait} ({chinese})"


def get_all_traits_in_groups():
    """获取所有配置中的性状列表"""
    all_traits = set()
    for group in TRAIT_CHART_GROUPS:
        all_traits.update(group['traits'])
    return sorted(all_traits)


# 示例用法
if __name__ == "__main__":
    import sys
    from pathlib import Path

    # 添加项目根目录到路径
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(project_root))

    from core.breeding_calc.cow_traits_calc import TRAITS_TRANSLATION

    # 测试：假设数据中只有这些性状
    test_traits = ['NM$', 'TPI', 'MILK', 'FAT', 'PROT', 'FAT %', 'PROT%',
                   'SCS', 'DPR', 'PL', 'PTAT', 'UDC', 'FLC', 'RFI', 'FS']

    groups = get_chart_groups_for_traits(test_traits)

    print(f"共生成 {len(groups)} 个图表组：\n")
    for i, group in enumerate(groups, 1):
        print(f"{i}. {group['name']}")
        print(f"   性状 ({group['trait_count']}个): {', '.join(group['traits'])}")
        print(f"   说明: {group['description']}")
        print(f"   Y轴: {group['y_axis_label']}")
        print(f"   范围: {group['range']}")
        if group.get('invert'):
            print(f"   ⚠️ 反向指标（越低越好）")
        print()

    # 检查覆盖率
    all_configured = get_all_traits_in_groups()
    print(f"\n配置文件共覆盖 {len(all_configured)} 个性状")
    print(f"配置的性状: {', '.join(all_configured)}")
