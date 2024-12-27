# core/data/processor.py
import re
import pandas as pd
from pathlib import Path
import numpy as np

# 品种字母和对应双字母代码的映射
BREED_CORRECTIONS = {
    'H': 'HO',
    'J': 'JE',
    'B': 'BS',
    'W': 'WW',
    'X': 'XX',
    'A': 'AY',
    'M': 'MO',
    'G': 'GU'
}

# 允许的品种代码集合，包括单字母和双字母
ALLOWED_BREED_CODES = set(BREED_CORRECTIONS.values()) | {'H', 'J', 'B', 'W', 'X', 'A', 'M', 'G'}


# 标准基因组检测数据列名
STANDARD_GENOMIC_COLUMNS = [
    "Genomic Sire_NAAB",
    "Genomic Sire_NAAB_1",
    "Genomic mgs_reg",
    "Genomic mgs_NAAB",
    "MAST",
    "JNS",
    "Jersey %",
    "Inactive",
    "DA",
    "Weaver",
    "UD",
    "Udder Health",
    "UC",
    "TL",
    "Telstar",
    "SG",
    "ST",
    "SMA",
    "Sire Submitted",
    "Sire Status",
    "SDM",
    "Sample ID",
    "UW",
    "UH",
    "RW",
    "RT",
    "RA",
    "RP",
    "LS",
    "LR",
    "Results Last Updated",
    "PTAT",
    "PROT",
    "PROT%",
    "Horn/Polled",
    "NM$ % RANK",
    "NM$ Reliability",
    "MGS Status",
    "MFV",
    "MET",
    "KET",
    "Kappa Casein I (ABE)",
    "TPI",
    "Hoof Health",
    "Holstein %",
    "HLiv",
    "CVM",
    "Guernsey %",
    "FI",
    "Genomic_SIRE REG",
    "Genomic Dam",
    "FU",
    "FT",
    "FA",
    "First Evaluation Date",
    "FS",
    "FAT",
    "FAT %",
    "cow_id",
    "Purebred/Crossbred Evaluation",
    "Dominant Red",
    "DF",
    "Dam Submitted",
    "Dam Status",
    "Recessive Red",
    "Caustv Polled",
    "Caust CVM",
    "Caust Brachy",
    "Categories",
    "BVDV Results",
    "Brown Swiss %",
    "BLH",
    "BLE",
    "birth_date",
    "Beta Lactoglobulin",
    "BD",
    "Ayrshire %",
    "Alpha S-1 Casein",
    "Beta Casein A2",
    "MILK",
    "GIB",
    "FIB",
    "breed",
    "Barcode",
    "Z_TWIN",
    "Z_RETP",
    "Z_RESP",
    "Z_MFV",
    "Z_METR",
    "Z_MAST",
    "Z_LAME",
    "Z_KETO",
    "Z_DA",
    "Z_CYST",
    "Z_Calf_Scours",
    "Z_Calf_Resp",
    "Z_Calf_LIV",
    "Z_ABRT",
    "WT$",
    "UDC",
    "UD Reliability",
    "SSB",
    "SSB Reliability",
    "sex",
    "SCS",
    "SCS Reliability",
    "SCE",
    "SCE Reliability",
    "RFI",
    "Result Type",
    "Prot Reliability",
    "Prot % Reliability",
    "PL",
    "PL Reliability",
    "Official ID",
    "NM$",
    "Mulefoot",
    "Milk Reliability",
    "LIV",
    "Kappa Casein II",
    "HH6",
    "HH5",
    "HH4",
    "HH3",
    "HH2",
    "HH1",
    "HCR",
    "HCR Reliability",
    "HCD",
    "GM$",
    "GL",
    "FS-Type  Reliability",
    "FM$",
    "FLS",
    "FLC",
    "FE",
    "Fat Reliability",
    "Fat % Reliability",
    "Factor XI",
    "Evaluation Date",
    "EFC",
    "DWP$",
    "DWP % RANK",
    "DUMPS",
    "DSB",
    "DSB Reliability",
    "DPR",
    "DPR Reliability",
    "DCE",
    "DCE Reliability",
    "CW$",
    "CM$",
    "Citrullinemia",
    "Chondrodysplasia",
    "CCR",
    "CCR Reliability",
    "CA$",
    "Brachyspina",
    "BLAD",
    "Beta Casein A/B",
    "BDC",
    "At Lab Date",
    "BVDV Confirmation Results"
]

# 方案示例：为每一种检测报告定义独立的映射字典
GENOMIC_COLUMN_MAPPING_TYPE1 = {
    "Z_TWIN":"Z_TWIN",
    "Z_RETP":"Z_RETP",
    "Z_RESP":"Z_RESP",
    "Z_MFV":"Z_MFV",
    "Z_METR":"Z_METR",
    "Z_MAST":"Z_MAST",
    "Z_LAME":"Z_LAME",
    "Z_KETO":"Z_KETO",
    "Z_DA":"Z_DA",
    "Z_CYST":"Z_CYST",
    "Z_Calf_Scours":"Z_Calf_Scours",
    "Z_Calf_Resp":"Z_Calf_Resp",
    "Z_Calf_LIV":"Z_Calf_LIV",
    "Z_ABRT":"Z_ABRT",
    "WT$":"WT$",
    "Weaver":"Weaver",
    "UW":"UW",
    "UH":"UH",
    "Udder Health":"Udder Health",
    "UDC":"UDC",
    "UD Reliability":"UD Reliability",
    "UD":"UD",
    "UC":"UC",
    "TPI":"TPI",
    "TL":"TL",
    "Telstar":"Telstar",
    "ST":"ST",
    "SSB Reliability":"SSB Reliability",
    "SSB":"SSB",
    "SMA":"SMA",
    "Sire Submitted":"Sire Submitted",
    "Sire Status":"Sire Status",
    "Sire NAAB":"Genomic Sire_NAAB",
    "Sire":"Genomic_SIRE REG",
    "SG":"SG",
    "Sex":"sex",
    "SDM":"SDM",
    "SCS Reliability":"SCS Reliability",
    "SCS":"SCS",
    "SCE Reliability":"SCE Reliability",
    "SCE":"SCE",
    "Sample ID":"Sample ID",
    "RW":"RW",
    "RT":"RT",
    "RP":"RP",
    "RFI":"RFI",
    "Results Last Updated":"Results Last Updated",
    "Result Type":"Result Type",
    "Recessive Red":"Recessive Red",
    "RA":"RA",
    "Purebred/Crossbred Evaluation":"Purebred/Crossbred Evaluation",
    "PTAT":"PTAT",
    "PROT%":"PROT%",
    "Prot Reliability":"Prot Reliability",
    "Prot % Reliability":"Prot % Reliability",
    "PROT":"PROT",
    "PL Reliability":"PL Reliability",
    "PL":"PL",
    "Official ID":"Official ID",
    "NM$ Reliability":"NM$ Reliability",
    "NM$ % RANK":"NM$ % RANK",
    "NM$":"NM$",
    "Mulefoot":"Mulefoot",
    "Milk Reliability":"Milk Reliability",
    "MILK":"MILK",
    "MGS Status":"MGS Status",
    "MGS REG":"Genomic mgs_reg",
    "MGS NAAB":"Genomic mgs_NAAB",
    "MFV":"MFV",
    "MET":"MET",
    "MAST":"MAST",
    "LS":"LS",
    "LR":"LR",
    "LIV":"LIV",
    "KET":"KET",
    "Kappa Casein II":"Kappa Casein II",
    "Kappa Casein I (ABE)":"Kappa Casein I (ABE)",
    "JNS":"JNS",
    "Jersey %":"Jersey %",
    "IND INBRD":"GIB",
    "Inactive":"Inactive",
    "Horn/Polled":"Horn/Polled",
    "Hoof Health":"Hoof Health",
    "Holstein %":"Holstein %",
    "HLiv":"HLiv",
    "HH6":"HH6",
    "HH5":"HH5",
    "HH4":"HH4",
    "HH3":"HH3",
    "HH2":"HH2",
    "HH1":"HH1",
    "HCR Reliability":"HCR Reliability",
    "HCR":"HCR",
    "HCD":"HCD",
    "Guernsey %":"Guernsey %",
    "GM$":"GM$",
    "GL":"GL",
    "FUT INBRD":"FIB",
    "FU":"FU",
    "FT":"FT",
    "FS-Type  Reliability":"FS-Type  Reliability",
    "FS ":"FS",
    "FM$":"FM$",
    "FLS":"FLS",
    "FLC":"FLC",
    "First Evaluation Date":"First Evaluation Date",
    "FI":"FI",
    "FE":"FE",
    "Fat Reliability":"Fat Reliability",
    "Fat % Reliability":"Fat % Reliability",
    "FAT %":"FAT %",
    "FAT":"FAT",
    "Farm ID":"cow_id",
    "Factor XI":"Factor XI",
    "FA":"FA",
    "Evaluation Date":"Evaluation Date",
    "EFC":"EFC",
    "DWP$":"DWP$",
    "DWP % RANK":"DWP % RANK",
    "DUMPS":"DUMPS",
    "DSB Reliability":"DSB Reliability",
    "DSB":"DSB",
    "DPR Reliability":"DPR Reliability",
    "DPR":"DPR",
    "Dominant Red":"Dominant Red",
    "DF":"DF",
    "DCE Reliability":"DCE Reliability",
    "DCE":"DCE",
    "Dam Submitted":"Dam Submitted",
    "Dam Status":"Dam Status",
    "Dam":"Genomic Dam",
    "DA":"DA",
    "CW$":"CW$",
    "CVM":"CVM",
    "CM$":"CM$",
    "Citrullinemia":"Citrullinemia",
    "Chondrodysplasia":"Chondrodysplasia",
    "CCR Reliability":"CCR Reliability",
    "CCR":"CCR",
    "Caustv Polled":"Caustv Polled",
    "Caust CVM":"Caust CVM",
    "Caust Brachy":"Caust Brachy",
    "Categories":"Categories",
    "CA$":"CA$",
    "BVDV Results":"BVDV Results",
    "BVDV Confirmation Results":"BVDV Confirmation Results",
    "Brown Swiss %":"Brown Swiss %",
    "Breed":"breed",
    "Brachyspina":"Brachyspina",
    "BLH":"BLH",
    "BLE":"BLE",
    "BLAD":"BLAD",
    "Birth":"birth_date",
    "Beta Lactoglobulin":"Beta Lactoglobulin",
    "Beta Casein A2":"Beta Casein A2",
    "Beta Casein A/B":"Beta Casein A/B",
    "BDC":"BDC",
    "BD":"BD",
    "Barcode":"Barcode",
    "Ayrshire %":"Ayrshire %",
    "At Lab Date":"At Lab Date",
    "Alpha S-1 Casein":"Alpha S-1 Casein"
}

GENOMIC_COLUMN_MAPPING_TYPE2 = {
    "Weaver":"Weaver",
    "UD":"UD",
    "Udder Health":"Udder Health",
    "UDC":"UDC",
    "UC":"UC",
    "TL":"TL",
    "Telstar":"Telstar",
    "SG":"SG",
    "ST":"ST",
    "SSB":"SSB",
    "SMA":"SMA",
    "Sire Submitted":"Sire Submitted",
    "Sire Status":"Sire Status",
    "Sire NAAB":"Genomic Sire_NAAB",
    "Sex":"sex",
    "SDM":"SDM",
    "SCS":"SCS",
    "SCE":"SCE",
    "Sample ID":"Sample ID",
    "UW":"UW",
    "UH":"UH",
    "RW":"RW",
    "RT":"RT",
    "RA":"RA",
    "RP":"RP",
    "LS":"LS",
    "LR":"LR",
    "Results Last Updated":"Results Last Updated",
    "Evaluation Date":"Evaluation Date",
    "Result Type":"Result Type",
    "PTAT":"PTAT",
    "PROT":"PROT",
    "PROT%":"PROT%",
    "Horn/Polled":"Horn/Polled",
    "PL":"PL",
    "Official ID":"Official ID",
    "NM$ % RANK":"NM$ % RANK",
    "NM$":"NM$",
    "NM$ Reliability":"NM$ Reliability",
    "Mulefoot":"Mulefoot",
    "MILK":"MILK",
    "MGS Status":"MGS Status",
    "MFV":"MFV",
    "MET":"MET",
    "MGS REG":"Genomic mgs_reg",
    "MAST":"MAST",
    "LIV":"LIV",
    "KET":"KET",
    "Kappa Casein I (ABE)":"Kappa Casein I (ABE)",
    "JNS":"JNS",
    "Jersey %":"Jersey %",
    "TPI":"TPI",
    "Inactive":"Inactive",
    "Hoof Health":"Hoof Health",
    "Holstein %":"Holstein %",
    "HLiv":"HLiv",
    "HCR":"HCR",
    "HCD":"HCD",
    "HH1":"HH1",
    "CVM":"CVM",
    "Guernsey %":"Guernsey %",
    "GM$":"GM$",
    "GL":"GL",
    "FI":"FI",
    "Sire":"Genomic_SIRE REG",
    "Dam":"Genomic Dam",
    "FU":"FU",
    "FT":"FT",
    "FA":"FA",
    "FM$":"FM$",
    "FLS":"FLS",
    "FLC":"FLC",
    "First Evaluation Date":"First Evaluation Date",
    "FS ":"FS",
    "FAT":"FAT",
    "FAT %":"FAT %",
    "Farm ID":"cow_id",
    "Purebred/Crossbred Evaluation":"Purebred/Crossbred Evaluation",
    "EFC":"EFC",
    "DUMPS":"DUMPS",
    "DSB":"DSB",
    "DPR":"DPR",
    "Dominant Red":"Dominant Red",
    "DF":"DF",
    "DCE":"DCE",
    "Dam Submitted":"Dam Submitted",
    "Dam Status":"Dam Status",
    "DA":"DA",
    "Recessive Red":"Recessive Red",
    "CM$":"CM$",
    "CCR":"CCR",
    "Caustv Polled":"Caustv Polled",
    "Caust CVM":"Caust CVM",
    "Caust Brachy":"Caust Brachy",
    "Categories":"Categories",
    "BVDV Results":"BVDV Results",
    "Brown Swiss %":"Brown Swiss %",
    "Breed":"breed",
    "Brachyspina":"Brachyspina",
    "BLH":"BLH",
    "BLE":"BLE",
    "BLAD":"BLAD",
    "Birth":"birth_date",
    "Beta Lactoglobulin":"Beta Lactoglobulin",
    "BD":"BD",
    "Ayrshire %":"Ayrshire %",
    "Alpha S-1 Casein":"Alpha S-1 Casein",
    "Beta Casein A2":"Beta Casein A2"
}

GENOMIC_COLUMN_MAPPING_TYPE3 = { 
    "UW":"UW",
    "UH":"UH",
    "UDC":"UDC",
    "UD":"UD",
    "UC":"UC",
    "Type-FS":"PTAT",
    "TPI":"TPI",
    "TL":"TL",
    "ST":"ST",
    "SSB":"SSB",
    "Sire NAAB Code":"Genomic Sire_NAAB",
    "Sire":"Genomic_SIRE REG",
    "SG":"SG",
    "Sex":"sex",
    "SCS":"SCS",
    "SCE":"SCE",
    "RW":"RW",
    "RT":"RT",
    "RFI":"RFI",
    "Result Type":"Result Type",
    "Recessive Red ":"Recessive Red",
    "RA":"RA",
    "Purebred/Crossbred Evaluation":"Purebred/Crossbred Evaluation",
    "Prot %":"PROT%",
    "Prot":"PROT",
    "PL":"PL",
    "On-farm ID (Herd Management #)":"cow_id",
    "Official ID":"Official ID",
    "NM$ % Rank":"NM$ % RANK",
    "NM$":"NM$",
    "Mulefoot":"Mulefoot",
    "Milk":"MILK",
    "MGS NAAB Code":"Genomic mgs_NAAB",
    "Maternal Grandsire (MGS)":"Genomic mgs_reg",
    "LS":"LS",
    "LR":"LR",
    "LIV":"LIV",
    "Kappa Casein I (ABE)":"Kappa Casein I (ABE)",
    "Ind  Inbrd":"GIB",
    "Horn/Polled":"Horn/Polled",
    "HH6":"HH6",
    "HH5":"HH5",
    "HH4":"HH4",
    "HH3":"HH3",
    "HH2":"HH2",
    "HH1":"HH1",
    "HCR":"HCR",
    "HCD":"HCD",
    "GM$":"GM$",
    "GL":"GL",
    "Fut Inbrd":"FIB",
    "FU":"FU",
    "FT":"FT",
    "FS":"FS",
    "FM$":"FM$",
    "FLS":"FLS",
    "FLC":"FLC",
    "FI":"FI",
    "FE":"FE",
    "Fat %":"FAT %",
    "Fat":"FAT",
    "Factor XI":"Factor XI",
    "FA":"FA",
    "Evaluation Date":"Evaluation Date",
    "EFC":"EFC",
    "DUMPS":"DUMPS",
    "DSB":"DSB",
    "DPR":"DPR",
    "Dominant Red":"Dominant Red",
    "DF":"DF",
    "DCE":"DCE",
    "Dam":"Genomic Dam",
    "CVM":"CVM",
    "CM$":"CM$",
    "Citrullinemia":"Citrullinemia",
    "Chondrodysplasia":"Chondrodysplasia",
    "CDCB_RP":"RP",
    "CDCB_MET":"MET",
    "CDCB_MAST":"MAST",
    "CDCB_KET":"KET",
    "CDCB_HLV":"HLiv",
    "CDCB_HC":"MFV",
    "CDCB_DA":"DA",
    "CCR":"CCR",
    "CA$":"CA$",
    "Breed Of Evaluation":"breed",
    "Brachyspina":"Brachyspina",
    "BLAD":"BLAD",
    "Birth Date":"birth_date",
    "Beta Lactoglobulin":"Beta Lactoglobulin",
    "Beta Casein A2":"Beta Casein A2",
    "BDC":"BDC",
    "BD":"BD",
    "Barcode":"Barcode",
    "At Lab Date":"At Lab Date",
    "Alpha S-1 Casein":"Alpha S-1 Casein"
 }
GENOMIC_COLUMN_MAPPING_TYPE4 = { 
    "Z_TWIN":"Z_TWIN",
    "Z_RETP":"Z_RETP",
    "Z_RESP":"Z_RESP",
    "Z_MFV":"Z_MFV",
    "Z_METR":"Z_METR",
    "Z_MAST":"Z_MAST",
    "Z_LAME":"Z_LAME",
    "Z_KETO":"Z_KETO",
    "Z_DA":"Z_DA",
    "Z_CYST":"Z_CYST",
    "Z_Calf_Scours":"Z_Calf_Scours",
    "Z_Calf_Resp":"Z_Calf_Resp",
    "Z_Calf_LIV":"Z_Calf_LIV",
    "Z_ABRT":"Z_ABRT",
    "WT$":"WT$",
    "UW":"UW",
    "UH":"UH",
    "UDC":"UDC",
    "UD Reliability":"UD Reliability",
    "UD":"UD",
    "UC":"UC",
    "TYPE FS":"PTAT",
    "TPI":"TPI",
    "TL":"TL",
    "Suggested Sire Naab":"Genomic Sire_NAAB_1",
    "Suggested Sire":"Genomic_SIRE REG",
    "Status":"Inactive",
    "ST":"ST",
    "SSB Reliability":"SSB Reliability",
    "SSB":"SSB",
    "Sire NAAB Code":"Genomic Sire_NAAB",
    "SG":"SG",
    "Sex":"sex",
    "SCS Reliability":"SCS Reliability",
    "SCS":"SCS",
    "SCE Reliability":"SCE Reliability",
    "SCE":"SCE",
    "RW":"RW",
    "RT":"RT",
    "RFI":"RFI",
    "Result Type":"Result Type",
    "Recessive Red":"Recessive Red",
    "RA":"RA",
    "Purebred/Crossbred Evaluation":"Purebred/Crossbred Evaluation",
    "PROT%":"PROT%",
    "Prot Reliability":"Prot Reliability",
    "Prot % Reliability":"Prot % Reliability",
    "PROT":"PROT",
    "PL Reliability":"PL Reliability",
    "PL":"PL",
    "Official ID":"Official ID",
    "NM$ Reliability":"NM$ Reliability",
    "NM$ % RANK":"NM$ % RANK",
    "NM$":"NM$",
    "Mulefoot":"Mulefoot",
    "Milk Reliability":"Milk Reliability",
    "MILK":"MILK",
    "LS":"LS",
    "LR":"LR",
    "LIV":"LIV",
    "Kappa Casein II":"Kappa Casein II",
    "Kappa Casein I (ABE)":"Kappa Casein I (ABE)",
    "IND INBRD":"GIB",
    "Horn/Polled":"Horn/Polled",
    "HH6":"HH6",
    "HH5":"HH5",
    "HH4":"HH4",
    "HH3":"HH3",
    "HH2":"HH2",
    "HH1":"HH1",
    "HCR Reliability":"HCR Reliability",
    "HCR":"HCR",
    "HCD":"HCD",
    "Group":"Categories",
    "GM$":"GM$",
    "GL":"GL",
    "FUT INBRD":"FIB",
    "FU":"FU",
    "FT":"FT",
    "FS-Type  Reliability":"FS-Type  Reliability",
    "FS ":"FS",
    "FM$":"FM$",
    "FLS":"FLS",
    "FLC":"FLC",
    "FI":"FI",
    "FE":"FE",
    "Fat Reliability":"Fat Reliability",
    "Fat % Reliability":"Fat % Reliability",
    "FAT %":"FAT %",
    "FAT":"FAT",
    "Factor XI":"Factor XI",
    "FA":"FA",
    "Evaluation Date":"Evaluation Date",
    "EFC":"EFC",
    "DWP$":"DWP$",
    "DWP % RANK":"DWP % RANK",
    "DUMPS":"DUMPS",
    "DSB Reliability":"DSB Reliability",
    "DSB":"DSB",
    "DPR Reliability":"DPR Reliability",
    "DPR":"DPR",
    "Dominant Red":"Dominant Red",
    "DF":"DF",
    "DCE Reliability":"DCE Reliability",
    "DCE":"DCE",
    "Dam Correct":"Genomic Dam",
    "CW$":"CW$",
    "CVM":"CVM",
    "CM$":"CM$",
    "Citrullinemia":"Citrullinemia",
    "Chondrodysplasia":"Chondrodysplasia",
    "CDCB_RP":"RP",
    "CDCB_MET":"MET",
    "CDCB_MAST":"MAST",
    "CDCB_KET":"KET",
    "CDCB_HLV":"HLiv",
    "CDCB_HC":"MFV",
    "CDCB_DA":"DA",
    "CCR Reliability":"CCR Reliability",
    "CCR":"CCR",
    "CA$":"CA$",
    "BVDV Results":"BVDV Results",
    "BVDV Confirmation Results":"BVDV Confirmation Results",
    "Breed":"breed",
    "Brachyspina":"Brachyspina",
    "BLAD":"BLAD",
    "Birth Date":"birth_date",
    "Beta Lactoglobulin":"Beta Lactoglobulin",
    "Beta Casein A2":"Beta Casein A2",
    "Beta Casein A/B":"Beta Casein A/B",
    "BDC":"BDC",
    "BD":"BD",
    "At Lab Date":"At Lab Date",
    "Animal ID":"cow_id",
    "Alpha S-1 Casein":"Alpha S-1 Casein"
 }
GENOMIC_COLUMN_MAPPING_TYPE5 = { 
    "最终体型评分可靠性":"FS-Type  Reliability",
    "最终体型评分":"PTAT",
    "总性能指数":"TPI",
    "状态":"Inactive",
    "肢蹄指数":"FLC",
    "肢蹄评分":"FLS",
    "有无角":"Horn/Polled",
    "隐性红毛基因":"Recessive Red",
    "液奶净价值":"FM$",
    "悬韧带强度":"UC",
    "性别":"sex",
    "显性红":"Dominant Red",
    "未来近交指数":"FIB",
    "体细胞评分可靠性":"SCS Reliability",
    "体细胞评分":"SCS",
    "体深":"BD",
    "体躯结构指数":"BDC",
    "体强度":"SG",
    "体高":"ST",
    "蹄角度":"FA",
    "饲料效率":"FE",
    "饲料节约量":"FS",
    "硕腾子宫炎指数":"Z_METR",
    "硕腾真胃异位指数":"Z_DA",
    "硕腾酮病指数":"Z_KETO",
    "硕腾蹄病指数":"Z_LAME",
    "硕腾胎衣停滞指数":"Z_RETP",
    "硕腾双胎指数":"Z_TWIN",
    "硕腾乳房炎指数":"Z_MAST",
    "硕腾卵巢囊肿指数":"Z_CYST",
    "硕腾流产指数":"Z_ABRT",
    "硕腾犊牛呼吸道病指数":"Z_Calf_Resp",
    "硕腾犊牛腹泻指数":"Z_Calf_Scours",
    "硕腾犊牛成活率指数":"Z_Calf_LIV",
    "硕腾低血钙症指数":"Z_MFV",
    "硕腾成母牛呼吸道疾病指数":"Z_RESP",
    "首产提前天数":"EFC",
    "收样日期":"At Lab Date",
    "生产寿命可靠性":"PL Reliability",
    "生产寿命":"PL",
    "软骨发育异常":"Chondrodysplasia",
    "乳脂率可靠性":"Fat % Reliability",
    "乳脂率":"FAT %",
    "乳脂可靠性":"Fat Reliability",
    "乳脂":"FAT",
    "乳头长度":"TL",
    "乳房深度可靠性":"UD Reliability",
    "乳房深度":"UD",
    "乳房结构指数":"UDC",
    "乳蛋白率可靠性":"Prot % Reliability",
    "乳蛋白率":"PROT%",
    "乳蛋白可靠性":"Prot Reliability",
    "乳蛋白":"PROT",
    "青年牛受胎率可靠性":"HCR Reliability",
    "青年牛受胎率":"HCR",
    "青年牛成活率":"HLiv",
    "前乳头位置":"FT",
    "前乳房附着":"FU",
    "评估日期":"Evaluation Date",
    "品种":"breed",
    "女儿怀孕率可靠性":"DPR Reliability",
    "女儿怀孕率":"DPR",
    "女儿产犊易度可靠性":"DCE Reliability",
    "女儿产犊易度":"DCE",
    "女儿产犊死胎率可靠性":"DSB Reliability",
    "女儿产犊死胎率":"DSB",
    "牛配种易度":"SCE",
    "牛白细胞粘附缺陷病":"BLAD",
    "凝血因子 XI缺乏":"Factor XI",
    "尿苷单磷酸合成酶缺乏":"DUMPS",
    "奶酪净价值":"CM$",
    "牧场牛号":"cow_id",
    "母亲矫正":"Genomic Dam",
    "母牛健康指数":"WT$",
    "棱角性":"DF",
    "尻宽":"RW",
    "尻角度":"RA",
    "卡帕酪蛋白II":"Kappa Casein II",
    "卡帕酪蛋白I":"Kappa Casein I (ABE)",
    "净价值排名":"NM$ % RANK",
    "净价值":"NM$",
    "结余饲料量":"RFI",
    "结果类型":"Result Type",
    "健康净价值排名":"DWP % RANK",
    "健康净价值":"DWP$",
    "建议父亲":"Genomic_SIRE REG",
    "怀孕期天数":"GL",
    "后肢后视":"LR",
    "后肢侧视":"LS",
    "后乳头位置":"RT",
    "后乳房附着宽度":"UW",
    "后乳房附着高":"UH",
    "荷斯坦繁殖缺陷6型":"HH6",
    "荷斯坦繁殖缺陷5型":"HH5",
    "荷斯坦繁殖缺陷4型":"HH4",
    "荷斯坦繁殖缺陷3型":"HH3",
    "荷斯坦繁殖缺陷2型":"HH2",
    "荷斯坦繁殖缺陷1型":"HH1",
    "官方牛号":"Official ID",
    "瓜氨酸血症":"Citrullinemia",
    "公牛配种死胎率可靠性":"SSB Reliability",
    "公牛配种死胎率":"SSB",
    "公牛配种产犊易度":"SCE Reliability",
    "个体近交指数":"GIB",
    "父亲矫正":"Genomic Sire_NAAB",
    "分组":"Categories",
    "放牧净价值":"GM$",
    "繁殖指数":"FI",
    "短脊椎综合症征":"Brachyspina",
    "犊牛健康指数":"CW$",
    "犊牛脊椎畸形综合征":"CVM",
    "胆固醇吸收障碍单倍型":"HCD",
    "单趾畸形":"Mulefoot",
    "存活率":"LIV",
    "纯种/非纯种评估":"Purebred/Crossbred Evaluation",
    "出生日期":"birth_date",
    "成母牛受胎率可靠性":"CCR Reliability",
    "成母牛受胎率":"CCR",
    "产奶量可靠性":"Milk Reliability",
    "产奶量":"MILK",
    "产活犊能力":"CA$",
    "β乳球蛋白":"Beta Lactoglobulin",
    "β酪蛋白A2":"Beta Casein A2",
    "β酪蛋白 A/B":"Beta Casein A/B",
    "α-S-1酪蛋白":"Alpha S-1 Casein",
    "NM$ 可靠性":"NM$ Reliability",
    "CDCB子宫炎":"MET",
    "CDCB真胃移位":"DA",
    "CDCB酮病":"KET",
    "CDCB胎衣不下":"RP",
    "CDCB乳房炎":"MAST",
    "CDCB低血钙":"MFV",
    "BVDV Results":"BVDV Results",
    "BVDV Confirmation Results":"BVDV Confirmation Results"
 }

# 也可以统一放到一个 dict 中，按照类型区分
GENOMIC_COLUMN_MAPPING_BY_TYPE = {
    "type1": GENOMIC_COLUMN_MAPPING_TYPE1,
    "type2": GENOMIC_COLUMN_MAPPING_TYPE2,
    "type3": GENOMIC_COLUMN_MAPPING_TYPE3,
    "type4": GENOMIC_COLUMN_MAPPING_TYPE4,
    "type5": GENOMIC_COLUMN_MAPPING_TYPE5,
}

# === 3. 定义一个检测报告类型的函数 ===
def detect_report_type(genomic_df: pd.DataFrame) -> str:
    """
    根据每种类型的“关键列”或特征列来判断。
    假设每种类型各有 3 个关键列，如果都存在，则认为是对应类型。
    若判断逻辑更复杂，请自行修改。
    """
    # 示例：每种类型各自有一组“关键列”
    type1_keys = {"Sire NAAB", "MGS REG", "MGS NAAB"}  # 示例关键列
    type2_keys = {"Dom Red", "UCL", "Coat Color"}  # 示例关键列
    type3_keys = {"Maternal Grandsire (MGS)", "Type-FS", "On-farm ID (Herd Management #)"}  # ...
    type4_keys = {"Status", "Group", "Dam Correct"}           # ...
    type5_keys = {"生产寿命", "个体近交指数", "怀孕期天数"}           # ...

    # 将表里的实际列转为 set 便于判断
    actual_cols = set(genomic_df.columns)

    # 依次判断是否满足某种类型的关键列
    if type1_keys.issubset(actual_cols):
        return "type1"
    elif type2_keys.issubset(actual_cols):
        return "type2"
    elif type3_keys.issubset(actual_cols):
        return "type3"
    elif type4_keys.issubset(actual_cols):
        return "type4"
    elif type5_keys.issubset(actual_cols):
        return "type5"
    else:
        # 如果都不满足，你可以抛出异常，或者返回一个默认类型
        raise ValueError("无法识别报告类型，请下载模版填写对应内容")




def format_naab_number(naab_number):
    errors = []
    naab_number = str(naab_number).strip()

    # 1. 检查NAAB号长度是否超过15位
    if len(naab_number) > 15:
        errors.append(f"NAAB号长度超过15位: {naab_number}")

    # 2. 删除前导0
    naab_number = naab_number.lstrip('0')

    # 3. 查找品种字母位置
    match_letter = re.search(r'[A-Za-z]', naab_number)
    if not match_letter:
        errors.append(f"NAAB号中未找到品种字母: {naab_number}")
        # 如果连品种字母都找不到，后续无法正确解析，就返回None
        return None, errors

    letter_index = match_letter.start()
    station_number = naab_number[:letter_index]
    remainder = naab_number[letter_index:]

    # 4. 检查站号长度
    if len(station_number) > 3:
        errors.append(f"NAAB公牛号的站号超过3位: {naab_number}")
    elif len(station_number) < 1:
        errors.append(f"NAAB公牛号的站号为空: {naab_number}")

    station_number = station_number.zfill(3)

    # 5. 匹配品种字母
    match_breed = re.match(r'([A-Za-z]{1,2})', remainder)
    if not match_breed:
        errors.append(f"未找到有效的品种字母: {naab_number}")
        return None, errors
    breed_code = match_breed.group(1).upper()
    remainder = remainder[len(breed_code):]

    # 6. 如果品种代码只有一个字母，则补全为双字母
    if len(breed_code) == 1:
        if breed_code in BREED_CORRECTIONS:
            breed_code = BREED_CORRECTIONS[breed_code]
        else:
            errors.append(f"单字母品种代码{breed_code}无法映射到双字母代码: {naab_number}")

    # 检查品种代码是否有效
    if breed_code not in ALLOWED_BREED_CODES:
        errors.append(f"不支持的品种代码: {breed_code}, NAAB号: {naab_number}")

    # 7. 删除品种字母后的前导0
    remainder = remainder.lstrip('0')

    # 8. 检查后缀数字长度
    if len(remainder) > 5:
        errors.append(f"后缀数字长度超过5位: {naab_number}")

    remainder = remainder.zfill(5)
    formatted_naab = f"{station_number}{breed_code}{remainder}"

    return formatted_naab if not errors else None, errors

def preprocess_cow_data(cow_df, progress_callback=None):
    """
    预处理母牛数据
    """
    # 替换表头中的中文列名为英文列名
    column_mapping = {
        "耳号": "cow_id",
        "品种": "breed",
        "性别": "sex",
        "父亲号": "sire",
        "外祖父": "mgs",
        "母亲号": "dam",
        "外曾外祖父": "mmgs",
        "胎次": "lac",
        "最近产犊日期": "calving_date",
        "牛只出生日期": "birth_date",
        "月龄": "age",
        "本胎次配次": "services_time",
        "本胎次奶厅高峰产量": "peak_milk",
        "305奶量": "milk_305",
        "泌乳天数": "DIM",
        "繁育状态": "repro_status",
    }
    cow_df.rename(columns=column_mapping, inplace=True)

    # 定义需要保留的列
    columns_to_keep = [
        "cow_id", "breed", "sex", "sire", "mgs", "dam", "mmgs", 
        "lac", "calving_date", "birth_date", "age",
        "services_time", "DIM", "peak_milk", "milk_305", "repro_status", 
        "group", "是否在场"
    ]

    # 添加不存在的列并填充为空值
    missing_columns = [col for col in columns_to_keep if col not in cow_df.columns]
    for col in missing_columns:
        cow_df[col] = ""

    # 调整列的顺序
    cow_df = cow_df[columns_to_keep]

    # 删除性别为“公”的记录
    cow_df = cow_df[cow_df['sex'] != '公']

    # 处理数值列，将无效值转换为NaN
    numeric_columns = ['lac', 'age', 'services_time', 'DIM', 'peak_milk', 'milk_305']
    for column in numeric_columns:
        if column in cow_df.columns:
            # 转换为数值类型，无效值转为NaN
            cow_df[column] = pd.to_numeric(cow_df[column], errors='coerce')
            # 替换无限值为NaN
            cow_df[column] = cow_df[column].replace([np.inf, -np.inf], np.nan)
            # 将NaN保留为NaN，不替换为空字符串

    # 对cow_id, sire, mgs, dam, mmgs列进行空格和小数点清除
    columns_to_clean = ['cow_id', 'sire', 'mgs', 'dam', 'mmgs']
    for column in columns_to_clean:
        if column in cow_df.columns:
            # 将列转换为字符串类型
            cow_df[column] = cow_df[column].astype(str)
            # 去除空格、小数点并清理
            cow_df[column] = cow_df[column].str.replace(' ', '').str.replace('.', '', regex=False).str.strip()

    # 调试输出：查看清理后的cow_id和dam
    print("清理后的cow_id和dam:")
    print(cow_df[['cow_id', 'dam']].head())

    # 对calving_date和birth_date列转换为日期格式
    date_columns = ['calving_date', 'birth_date']
    for column in date_columns:
        if column in cow_df.columns:
            cow_df[column] = pd.to_datetime(cow_df[column], errors='coerce')

    # 检查重复的cow_id
    duplicate_cows = cow_df[cow_df.duplicated(subset=['cow_id'], keep=False)]
    if not duplicate_cows.empty:
        duplicate_count = len(duplicate_cows['cow_id'].unique())
        msg = f"发现{duplicate_count}个重复的母牛号。将按以下优先级保留记录：\n1. 性别为母牛\n2. 在群状态\n3. 出生日期最近\n4. 胎次最小\n5. 随机选择"
        if progress_callback:
            progress_callback(f"警告: {msg}")

        # 定义一个函数来选择要保留的记录
        def select_record(group):
            # 1. 优先选择性别为母牛的记录
            females = group[group['sex'] == '母']
            if not females.empty:
                group = females

            # 2. 在性别相同的情况下，优先选择在群的记录
            in_herd = group[group['是否在场'] == '是']
            if not in_herd.empty:
                group = in_herd

            # 3. 如果还有多条记录，选择出生日期最近的
            if group['birth_date'].notna().any():
                return group.loc[group['birth_date'].idxmax()]

            # 4. 如果出生日期都缺失，选择胎次最小的
            elif group['lac'].notna().any():
                return group.loc[group['lac'].idxmin()]

            # 5. 如果以上条件都不满足，随机选择一条记录
            else:
                return group.sample(n=1).iloc[0]

        # 按cow_id分组，应用选择函数
        cow_df = cow_df.groupby('cow_id').apply(select_record).reset_index(drop=True)

    invalid_naab_numbers = set()

    # 对sire, mgs, mmgs列进行NAAB编号格式化
    naab_columns = ['sire', 'mgs', 'mmgs']
    total_naab = cow_df.shape[0] * len(naab_columns)
    current_naab = 0

    for column in naab_columns:
        if column in cow_df.columns:
            def format_and_track(x):
                nonlocal current_naab
                if progress_callback:
                    current_naab += 1
                    progress = int((current_naab / total_naab) * 100)
                    progress_callback(progress)  # 修改这里，去除 .emit
                formatted_id, errors = format_naab_number(x)
                if errors:
                    invalid_naab_numbers.add(x)
                    return ''
                return formatted_id

            cow_df[column] = cow_df[column].apply(format_and_track)

    if invalid_naab_numbers:
        invalid_numbers_str = '\n'.join(invalid_naab_numbers)
        if progress_callback:
            progress_callback(f"NAAB公牛号的牛号部分有误,\n以下牛号HO之后的数字超过5位:\n\n{invalid_numbers_str}\n\n（正确案例:123HO12345）\n\n继续处理...")



    # 添加新列：birth_date_dam, mgd, birth_date_mgd
    # 1. 添加 birth_date_dam
    # 创建一个映射字典：cow_id -> birth_date
    cow_birth_date_map = cow_df.set_index('cow_id')['birth_date'].to_dict()
    cow_df['birth_date_dam'] = cow_df['dam'].map(cow_birth_date_map)

    # 2. 添加 mgd（外祖母）
    # 首先，需要获取母亲的母亲号（即外祖母的 cow_id）
    # 创建一个映射字典：cow_id -> dam
    cow_dam_map = cow_df.set_index('cow_id')['dam'].to_dict()
    cow_df['mgd'] = cow_df['dam'].map(cow_dam_map)

    # 3. 添加 birth_date_mgd
    # 通过 mgd（外祖母的 cow_id）映射到 birth_date
    cow_df['birth_date_mgd'] = cow_df['mgd'].map(cow_birth_date_map)

    # 填充缺失值（如果需要）
    cow_df['birth_date_dam'] = cow_df['birth_date_dam'].fillna(pd.NaT)
    cow_df['mgd'] = cow_df['mgd'].fillna('')
    cow_df['birth_date_mgd'] = cow_df['birth_date_mgd'].fillna(pd.NaT)

    # 对日期列进行格式化（可选）
    cow_df['birth_date_dam'] = cow_df['birth_date_dam'].dt.strftime('%Y-%m-%d')
    cow_df['birth_date_mgd'] = cow_df['birth_date_mgd'].dt.strftime('%Y-%m-%d')

    # 检查是否有缺失的母亲或外祖母信息，并记录警告或错误（可选）
    # missing_birth_date_dam = cow_df['birth_date_dam'].isna().sum()
    # missing_birth_date_mgd = cow_df['birth_date_mgd'].isna().sum()

    # if missing_birth_date_dam > 0:
    #     msg = f"警告: 有 {missing_birth_date_dam} 只母牛的母亲出生日期未找到。"
    #     if progress_callback:
    #         progress_callback(msg)

    # if missing_birth_date_mgd > 0:
    #     msg = f"警告: 有 {missing_birth_date_mgd} 只母牛的外祖母出生日期未找到。"
    #     if progress_callback:
    #         progress_callback(msg)

    return cow_df


def process_cow_data_file(input_file: Path, project_path: Path, progress_callback=None) -> Path:
    """
    标准化母牛数据文件
    """
    # 将标准化后的文件存储到 standardized_data 文件夹
    standardized_path = project_path / "standardized_data"
    standardized_path.mkdir(parents=True, exist_ok=True)
    # 读取文件
    try:
        # 在读取时指定数据类型
        df = pd.read_excel(input_file, dtype={'cow_id': str, 'sire': str, 'mgs': str, 'dam': str, 'mmgs': str})
    except Exception as e:
        raise ValueError(f"读取母牛数据文件失败: {e}")

    # 对数据进行标准化处理
    try:
        df_cleaned = preprocess_cow_data(df, progress_callback)
    except Exception as e:
        raise ValueError(f"预处理母牛数据失败: {e}")

    # 保存标准化后的文件
    output_file = standardized_path / "processed_cow_data.xlsx"
    try:
        df_cleaned.to_excel(output_file, index=False)
    except Exception as e:
        raise ValueError(f"保存母牛数据文件失败: {e}")

    # 确保文件存在
    if not output_file.exists():
        raise ValueError("标准化后的母牛数据文件未生成。")

    return output_file

def preprocess_bull_data(bull_df, progress_callback=None):
    # 清理 bull_id
    bull_df['bull_id'] = bull_df['bull_id'].astype(str).apply(lambda x: x.replace(' ', '').strip())
    bull_df = bull_df.dropna(subset=['bull_id'])  # 删除 NaN 行
    bull_df = bull_df[bull_df['bull_id'] != '']  # 删除空字符串行
    bull_df = bull_df[~bull_df['bull_id'].str.contains("nan", case=False)]  # 删除包含"nan"的行

    all_errors = []
    formatted_ids = []

    total = bull_df.shape[0]
    for idx, row in bull_df.iterrows():
        original_id = row['bull_id']
        formatted_id, errors = format_naab_number(original_id)
        if errors:
            all_errors.extend(errors)
        # 无论是否有错误，都将formatted_id加入列表（有错则None）
        formatted_ids.append(formatted_id)
        if progress_callback:
            progress = int((idx + 1) / total * 100)
            progress_callback(progress)

    bull_df['bull_id'] = formatted_ids

    # 如果有错误信息，一次性报错
    if all_errors:
        error_message = "\n".join(all_errors)
        raise ValueError(f"数据处理错误(以下为全部错误信息):\n{error_message}")

    # 没有错误则返回处理后的DataFrame
    return bull_df

def process_bull_data_file(input_file: Path, project_path: Path, progress_callback=None) -> Path:
    """
    标准化备选公牛数据文件
    """
    # 将标准化后的文件存储到 standardized_data 文件夹
    standardized_path = project_path / "standardized_data"
    standardized_path.mkdir(parents=True, exist_ok=True)
    # 读取文件
    try:
        df = pd.read_excel(input_file)
    except Exception as e:
        raise ValueError(f"读取备选公牛数据文件失败: {e}")
    # 对数据进行标准化处理，如：
    try:
        df_cleaned = preprocess_bull_data(df, progress_callback)
    except Exception as e:
        raise ValueError(f"预处理备选公牛数据失败: {e}")

    # 假设标准化后的文件名固定为 "processed_bull_data.xlsx"
    output_file = standardized_path / "processed_bull_data.xlsx"
    try:
        df_cleaned.to_excel(output_file, index=False)
    except Exception as e:
        raise ValueError(f"保存备选公牛数据文件失败: {e}")

    return output_file  # 返回标准化后的文件路径

def process_body_conformation_file(input_file: Path, project_path: Path, progress_callback=None) -> Path:
    """
    标准化体型外貌数据文件
    """
    # 将标准化后的文件存储到 standardized_data 文件夹
    standardized_path = project_path / "standardized_data"
    standardized_path.mkdir(parents=True, exist_ok=True)
    # 读取文件，根据文件类型选择读取方法
    try:
        if input_file.suffix.lower() == '.csv':
            df = pd.read_csv(input_file)
        else:
            df = pd.read_excel(input_file)
    except Exception as e:
        raise ValueError(f"读取体型外貌数据文件失败: {e}")

    # 数据标准化逻辑（根据用户提供的必需列进行处理）
    required_columns = [
        "牧场", "牛号", "体高", "胸宽", "体深", "腰强度", "尻角度", "尻宽", 
        "蹄角度", "蹄踵深度", "骨质地", "后肢侧视", "后肢后视", "乳房深度", 
        "中央悬韧带", "前乳房附着", "前乳头位置", "前乳头长度", "后乳房附着高度", 
        "后乳房附着宽度", "后乳头位置", "棱角性"
    ]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"体型外貌数据缺少以下必需列: {', '.join(missing_columns)}")

    # 删除缺失值
    df_cleaned = df.dropna(subset=required_columns)

    # 您可以在这里添加更多的标准化逻辑，例如数据类型转换、格式统一等

    # 保存标准化后的文件
    output_file = standardized_path / "processed_body_conformation_data.xlsx"
    try:
        df_cleaned.to_excel(output_file, index=False)
    except Exception as e:
        raise ValueError(f"保存体型外貌数据文件失败: {e}")

    # 确保文件存在
    if not output_file.exists():
        raise ValueError("标准化后的体型外貌数据文件未生成。")

    return output_file

def process_breeding_record_file(input_file: Path, project_path: Path, cow_df=None, progress_callback=None) -> Path:
    """
    标准化配种记录数据文件

    参数:
        input_file (Path): 输入的配种记录数据文件路径。
        project_path (Path): 当前项目的路径。
        cow_df (DataFrame, optional): 母牛数据的DataFrame，用于映射父号。
        progress_callback (callable, optional): 进度回调函数，用于更新进度条或显示信息。

    返回:
        Path: 标准化后的配种记录数据文件路径。
    """
    # 将标准化后的文件存储到 standardized_data 文件夹
    standardized_path = project_path / "standardized_data"
    standardized_path.mkdir(parents=True, exist_ok=True)
    # 读取文件，根据文件类型选择读取方法
    try:
        if input_file.suffix.lower() == '.csv':
            df = pd.read_csv(input_file)
        else:
            df = pd.read_excel(input_file)
    except Exception as e:
        raise ValueError(f"读取配种记录数据文件失败: {e}")

    # 数据标准化逻辑（根据用户提供的必需列进行处理）
    required_columns = ['耳号', '配种日期', '冻精编号', '冻精类型']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"配种记录数据缺少以下必需列: {', '.join(missing_columns)}")

    # 删除缺失值
    df_cleaned = df.dropna(subset=required_columns)

    # 处理 '冻精编号' 使用 format_naab_number
    def apply_format_naab_number(x):
        formatted_id, errors = format_naab_number(x)
        if errors:
            # 如果有错误，返回空字符串
            return ''
        return formatted_id

    total = df_cleaned.shape[0]
    for idx, row in df_cleaned.iterrows():
        df_cleaned.at[idx, '冻精编号'] = apply_format_naab_number(row['冻精编号'])
        if progress_callback:
            progress = int((idx + 1) / total * 100)
            progress_callback(progress)

    # 处理 '配种日期' 转换为日期格式
    df_cleaned['配种日期'] = pd.to_datetime(df_cleaned['配种日期'], errors='coerce')

    # 填充 NaN 为 ''
    df_cleaned.fillna('', inplace=True)

    # 添加父号列
    if cow_df is not None:
        # 确保 'cow_id' 和 'sire' 列存在
        if 'cow_id' not in cow_df.columns or 'sire' not in cow_df.columns:
            raise ValueError("母牛数据缺少 'cow_id' 或 'sire' 列。")
        cow_df['cow_id'] = cow_df['cow_id'].astype(str)
        sire_dict = dict(zip(cow_df['cow_id'], cow_df['sire']))
        # 将耳号转换为字符串类型
        df_cleaned['耳号'] = df_cleaned['耳号'].astype(str)
        # 添加父号列
        df_cleaned['父号'] = df_cleaned['耳号'].map(sire_dict).fillna('')
    else:
        # 如果没有提供 cow_df，添加空的父号列
        df_cleaned['父号'] = ''

    # 重新排列列的顺序
    df_cleaned = df_cleaned[['耳号', '父号', '冻精编号', '配种日期', '冻精类型']]

    # 保存标准化后的文件
    output_file = standardized_path / "processed_breeding_data.xlsx"
    try:
        df_cleaned.to_excel(output_file, index=False)
    except Exception as e:
        raise ValueError(f"保存配种记录数据文件失败: {e}")

    # 确保文件存在
    if not output_file.exists():
        raise ValueError("标准化后的配种记录数据文件未生成。")

    return output_file


# === 4. 修改 preprocess_genomic_data 函数 ===
def preprocess_genomic_data(genomic_df, progress_callback=None):
    """
    预处理基因组检测数据的主函数。通过检查关键列名，
    确定不同的报告类型，进而选择对应的映射字典进行重命名。
    不再需要 combine_first 逻辑。

    :param genomic_df: 读取 Excel/CSV 后得到的原始 DataFrame
    :param progress_callback: 进度更新的回调函数，可选
    :return: 预处理并标准化后的 DataFrame
    """
    print("开始预处理基因组检测数据...")
    genomic_df = genomic_df.copy()
    print(f"输入数据的列名: {genomic_df.columns.tolist()}")
    print(f"输入数据的形状: {genomic_df.shape}")

    try:
        # 1. 根据关键列名检测报告类型
        report_type = detect_report_type(genomic_df)
        print(f"识别到的报告类型: {report_type}")

        # 2. 选择对应的映射字典
        mapping_dict = GENOMIC_COLUMN_MAPPING_BY_TYPE[report_type]
        print(f"使用映射字典: {mapping_dict}")

        # 3. 找到 cow_id 列（也可以直接用映射后的 "cow_id"）
        cow_id_col = None
        cow_id_alternatives = ["Animal ID", "Farm ID", "牧场牛号", "On-farm ID (Herd Management #)"]
        for possible_id in cow_id_alternatives:
            if possible_id in genomic_df.columns:
                cow_id_col = possible_id
                print(f"找到 cow_id 列: {cow_id_col}")
                break
        if not cow_id_col:
            raise ValueError(
                f"在输入数据中未找到 cow_id 列。可用的列名: {genomic_df.columns.tolist()}"
            )

        # 保存 cow_id 的原始值，供后续插回最终 DataFrame
        cow_id_values = genomic_df[cow_id_col].copy()

        # 4. 按照当前类型的映射字典重命名列
        rename_dict = {old: new for old, new in mapping_dict.items() if old in genomic_df.columns}
        print(f"将要重命名的列: {rename_dict}")
        genomic_df = genomic_df.rename(columns=rename_dict)
        print(f"重命名后的列名: {genomic_df.columns.tolist()}")

        # 5. 构建 result_rows，用来拼装标准化后的数据
        result_rows = []
        for idx in range(len(genomic_df)):
            row_data = {}
            # 初始化所有标准列为 NaN
            for col in STANDARD_GENOMIC_COLUMNS:
                row_data[col] = np.nan

            # 将存在于 genomic_df 中的列映射到 row_data
            for col in genomic_df.columns:
                if col in STANDARD_GENOMIC_COLUMNS:
                    row_data[col] = genomic_df.iloc[idx][col]

            # 强制添加 cow_id
            row_data["cow_id"] = cow_id_values.iloc[idx]

            # 如果存在 'Results Last Updated' 或 'Evaluation Date' 列，则做时间转换
            if "Results Last Updated" in genomic_df.columns:
                row_data["Results_Last_Updated"] = pd.to_datetime(
                    genomic_df.iloc[idx]["Results Last Updated"], errors="coerce"
                )
            elif "Evaluation Date" in genomic_df.columns:
                row_data["Results_Last_Updated"] = pd.to_datetime(
                    genomic_df.iloc[idx]["Evaluation Date"], errors="coerce"
                )
            else:
                # 如果都不存在，则默认赋值当前时间
                row_data["Results_Last_Updated"] = pd.Timestamp.now()

            result_rows.append(row_data)

        # 6. 生成最终的 standardized_df
        standardized_df = pd.DataFrame(result_rows)

        # 确保列顺序和 STANDARD_GENOMIC_COLUMNS 一致
        # 如果一些列在 STANDARD_GENOMIC_COLUMNS 中未出现，就忽略
        standardized_df = standardized_df[STANDARD_GENOMIC_COLUMNS + ["cow_id", "Results_Last_Updated"]]

        print(f"处理后的数据形状: {standardized_df.shape}")
        print("基因组数据预处理完成")

        return standardized_df

    except Exception as e:
        print(f"预处理过程中发生错误: {str(e)}")
        print("当前处理的数据状态:")
        print(f"- 原始数据形状: {genomic_df.shape}")
        print(f"- 原始数据列名: {genomic_df.columns.tolist()}")
        raise

# === 5. 修改 process_genomic_data_file 函数 ===
def process_genomic_data_file(input_files: list[Path], project_path: Path, progress_callback=None) -> Path:
    """
    标准化基因组检测数据文件。

    :param input_files: 输入文件路径列表
    :param project_path: 项目根目录路径
    :param progress_callback: 进度更新的回调函数，可选
    :return: 最终汇总文件的路径
    """
    print("开始处理基因组检测数据...")

    standardized_path = project_path / "standardized_data"
    standardized_path.mkdir(parents=True, exist_ok=True)

    processed_files = []  # 用于存储处理后的文件路径

    # 为每个输入文件创建独立的处理结果
    for idx, input_file in enumerate(input_files, start=1):
        try:
            print(f"处理文件 {idx}/{len(input_files)}: {input_file.name}")
            # 读取文件
            if input_file.suffix.lower() == '.csv':
                df = pd.read_csv(input_file)
            else:
                df = pd.read_excel(input_file)

            # 预处理数据（根据报告类型重命名）
            df_cleaned = preprocess_genomic_data(df, progress_callback)

            # 保存独立的处理结果
            output_file = standardized_path / f"processed_genomic_data_{idx}.xlsx"
            df_cleaned.to_excel(output_file, index=False)
            print(f"已保存处理结果到: {output_file}")
            processed_files.append(output_file)

        except Exception as e:
            raise ValueError(f"处理文件 {input_file.name} 时发生错误: {e}")

    # 合并所有处理结果到最终文件
    try:
        final_output = standardized_path / "processed_genomic_data.xlsx"

        if not final_output.exists():
            if len(processed_files) == 1:
                # 只有一份处理结果，直接重命名为最终汇总文件
                processed_files[0].rename(final_output)
                print(f"已保存最终汇总结果到: {final_output}")
            else:
                # 多份处理结果，进行合并
                final_df = pd.concat(
                    [pd.read_excel(f) for f in processed_files],
                    ignore_index=True
                )

                # 根据 cow_id 和 Results_Last_Updated 去重
                final_df['Results_Last_Updated'] = pd.to_datetime(final_df['Results_Last_Updated'])
                final_df = final_df.sort_values('Results_Last_Updated', ascending=False)
                final_df = final_df.drop_duplicates(subset='cow_id', keep='first')

                # 保存最终结果
                final_df.to_excel(final_output, index=False)
                print(f"已保存最终汇总结果到: {final_output}")
        else:
            # 如果存在旧的汇总文件，需要将新处理的文件与之合并
            final_df = pd.read_excel(final_output)

            # 确保旧的汇总文件列名无重复且符合标准
            final_df = final_df.loc[:, ~final_df.columns.duplicated()]
            # 可以进一步验证列名是否唯一，避免潜在问题
            if final_df.columns.duplicated().any():
                raise ValueError("现有汇总文件中存在重复的列名。请检查并清理汇总文件。")

            # 读取并合并新处理的文件
            for temp_file in processed_files:
                temp_df = pd.read_excel(temp_file)
                # 确保 temp_df 的列名与 final_df 一致
                if not set(STANDARD_GENOMIC_COLUMNS + ['cow_id', 'Results_Last_Updated']).issubset(temp_df.columns):
                    raise ValueError(f"处理文件 {temp_file.name} 缺少必要的标准列。")
                final_df = pd.concat([final_df, temp_df], ignore_index=True)

            # 根据 cow_id 和 Results_Last_Updated 去重
            final_df['Results_Last_Updated'] = pd.to_datetime(final_df['Results_Last_Updated'])
            final_df = final_df.sort_values('Results_Last_Updated', ascending=False)
            final_df = final_df.drop_duplicates(subset='cow_id', keep='first')

            # 保存最终结果
            final_df.to_excel(final_output, index=False)
            print(f"已保存最终汇总结果到: {final_output}")

        return final_output

    except Exception as e:
        raise ValueError(f"合并处理结果时发生错误: {e}")
