"""
参测牛数据列名映射
将参测牛数据（遗传进展）的中文列名映射到系统中的英文性状代码
"""

# 参测牛数据列名 → 系统性状代码
REFERENCE_TRAIT_MAPPING = {
    # 基础映射（12个已确认）
    'IPI': 'TPI',
    '净效益（美元）': 'NM$',
    '产奶量': 'MILK',
    '乳脂率（%）': 'FAT %',
    '乳脂量（磅）': 'FAT',
    '乳蛋白率%': 'PROT%',
    '乳蛋白量（磅）': 'PROT',
    '体细胞评分': 'SCS',
    '生产寿命': 'PL',
    '女儿情期受胎率': 'DPR',
    'CCR': 'CCR',
    '青年母牛受胎率': 'HCR',

    # 饲料相关
    'Feed Save': 'FS',
    'RFI': 'RFI',
    '液态奶指数$': 'FM$',
    'CM$': 'CM$',
    '放牧指数$': 'GM$',
    'FE$': 'FE',

    # 健康相关
    '存活能力': 'LIV',
    'HLiv': 'HLiv',
    'MFV': 'MFV',
    'DAB': 'DA',
    'KET': 'KET',
    'MAS': 'MAST',
    'MET': 'MET',
    'RP': 'RP',

    # 繁殖相关
    '女儿产犊难易': 'DCE',
    '公牛配种易产性': 'SCE',
    '女儿死胎率': 'DSB',
    '公牛配种死胎率': 'SSB',
    'GL': 'GL',
    'EFC': 'EFC',
    'FI': 'FI',

    # 体型相关
    '体型总分': 'PTAT',
    '肢蹄结构评分': 'FLC',
    '乳房综合评分': 'UDC',
    'BWC': 'BDC',
    'HT': 'ST',
    '强壮度': 'SG',
    '体深': 'BD',
    '乳用性': 'DF',
    '尻角度': 'RA',
    '尻宽': 'RW',
    '后肢侧视': 'LS',
    '后肢后视': 'LR',
    '蹄角度': 'FA',
    '肢蹄运动评分': 'FLS',

    # 乳房相关
    '前乳房附着': 'FU',
    '后乳房高度': 'UH',
    'RUW': 'UW',
    '悬韧带': 'UC',
    '乳房深度': 'UD',
    '前乳头位置': 'FT',
    '后乳头位置': 'RT',
    '乳头长度': 'TL',
}

# 系统性状代码 → 中文名称（用于显示）
TRAIT_CHINESE_NAMES = {
    'TPI': '育种综合指数',
    'NM$': '净利润值',
    'CM$': '奶酪净值',
    'FM$': '液奶净值',
    'GM$': '放牧净值',
    'MILK': '产奶量',
    'FAT': '乳脂量',
    'PROT': '乳蛋白量',
    'FAT %': '乳脂率',
    'PROT%': '乳蛋白率',
    'SCS': '体细胞指数',
    'DPR': '女儿怀孕率',
    'HCR': '青年牛受胎率',
    'CCR': '成母牛受胎率',
    'PL': '生产寿命',
    'SCE': '配种产犊难易度',
    'DCE': '女儿产犊难易度',
    'SSB': '配种死胎率',
    'DSB': '女儿死淘率',
    'PTAT': '体型综合指数',
    'UDC': '乳房综合指数',
    'FLC': '肢蹄综合指数',
    'BDC': '体重综合指数',
    'ST': '体高',
    'SG': '强壮度',
    'BD': '体深',
    'DF': '乳用特征',
    'RA': '尻角度',
    'RW': '尻宽',
    'LS': '后肢侧视',
    'LR': '后肢后视',
    'FA': '蹄角度',
    'FLS': '肢蹄评分',
    'FU': '前方附着',
    'UH': '后房高度',
    'UW': '后方宽度',
    'UC': '悬韧带',
    'UD': '乳房深度',
    'FT': '前乳头位置',
    'RT': '后乳头位置',
    'TL': '乳头长度',
    'FE': '饲料效率指数',
    'FI': '繁殖力指数',
    'LIV': '存活率',
    'GL': '妊娠长度',
    'MAST': '乳房炎抗病性',
    'MET': '子宫炎抗病性',
    'RP': '胎衣不下抗病性',
    'KET': '酮病抗病性',
    'DA': '变胃抗病性',
    'MFV': '产后瘫抗病性',
    'EFC': '首次产犊月龄',
    'HLiv': '后备牛存活率',
    'FS': '饲料节约指数',
    'RFI': '剩余饲料采食量',
}


def map_reference_columns(reference_df):
    """
    将参测牛数据的列名映射为系统性状代码

    Args:
        reference_df: 参测牛数据DataFrame

    Returns:
        映射后的DataFrame，列名为系统性状代码
    """
    import pandas as pd

    # 创建新的DataFrame
    mapped_df = pd.DataFrame()

    # 保留出生年列
    if '出生年' in reference_df.columns:
        mapped_df['birth_year'] = reference_df['出生年'].str.replace('年', '').astype(int)

    # 映射性状列
    for ref_col, sys_col in REFERENCE_TRAIT_MAPPING.items():
        if ref_col in reference_df.columns:
            mapped_df[sys_col] = reference_df[ref_col]

    return mapped_df


def get_trait_display_name(trait_code):
    """
    获取性状的中文显示名称

    Args:
        trait_code: 性状代码（如'TPI', 'NM$'）

    Returns:
        中文名称
    """
    return TRAIT_CHINESE_NAMES.get(trait_code, trait_code)
