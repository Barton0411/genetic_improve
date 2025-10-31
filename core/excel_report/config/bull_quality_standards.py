"""
优质冻精技术标准配置
"""

# 美国后裔标准
US_PROGENY_STANDARDS = {
    'TPI': 2850,
    'NM$': 300,
    'MILK': 200,
    'PROT': 20,
    'UDC': 0,
    'RFI': 100,
    'PL': 1.5,
    'DPR': -2
}

# 美国基因组标准
US_GENOMIC_STANDARDS = {
    'TPI': 2900,
    'NM$': 400,
    'MILK': 300,
    'PROT': 30,
    'UDC': 0,
    'RFI': 100,
    'PL': 1.5,
    'DPR': -2
}

# 缺陷基因列表
DEFECT_GENES = ['HH1', 'HH2', 'HH3', 'HH4', 'HH5', 'HH6', 'MW']

# 标准表格式
QUALITY_STANDARD_TABLE = {
    'headers': ['育种指标标识', '类型', 'TPI\n(GTPI)\n综合生产\n指数', 'NM$\n净效益\n指数',
                'Milk\n奶量育种值\n(磅)', 'Prot蛋白量育种值\n(磅)', 'UDC\n乳房\n综合\n指数',
                'FE\n饲料\n转化\n指数', 'PL\n生产\n寿命', 'DPR女儿怀孕率', '缺陷基因'],
    'rows': [
        {
            'country': '美国',
            'type': '后裔',
            'TPI': '≥2850',
            'NM$': '≥300',
            'MILK': '≥200',
            'PROT': '≥20',
            'UDC': '≥0',
            'RFI': '≥100',
            'PL': '≥1.5',
            'DPR': '≥-2',
            'genes': 'HH1-HH6\nHMW'
        },
        {
            'country': '',
            'type': '基因组',
            'TPI': '≥2900',
            'NM$': '≥400',
            'MILK': '≥300',
            'PROT': '≥30',
            'UDC': '≥0',
            'RFI': '≥100',
            'PL': '≥1.5',
            'DPR': '≥-2',
            'genes': 'HH1-HH6\nHMW'
        }
    ]
}
