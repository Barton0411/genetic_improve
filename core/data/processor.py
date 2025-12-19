# core/data/processor.py
import re
import pandas as pd
from pathlib import Path
import numpy as np
import logging
import traceback

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
    根据每种类型的"关键列"或特征列来判断。
    假设每种类型各有 3 个关键列，如果都存在，则认为是对应类型。
    若判断逻辑更复杂，请自行修改。
    """
    # 示例：每种类型各自有一组"关键列"
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

    # 0. 去除开头和结尾的特殊标记（不区分大小写，同时处理前后缀）
    # 长的标记放前面优先匹配，避免 X 误匹配 XK
    prefixes_to_remove = ['XK', 'SEX', '性控', 'P', 'X', 'S', '性', '普']
    suffixes_to_remove = ['XK', 'SEX', '性控', 'P', 'X', 'S', '性', '普']

    # 去除前缀
    naab_upper = naab_number.upper()
    for prefix in prefixes_to_remove:
        if naab_upper.startswith(prefix.upper()):
            naab_number = naab_number[len(prefix):]
            break

    # 去除后缀（前缀去除后继续检查后缀）
    naab_upper = naab_number.upper()
    for suffix in suffixes_to_remove:
        if naab_upper.endswith(suffix.upper()):
            naab_number = naab_number[:-len(suffix)]
            break

    naab_number = naab_number.strip()  # 再次去除可能的空格

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

def preprocess_cow_data(cow_df, progress_callback=None, source_system: str = "伊起牛"):
    """
    预处理母牛数据

    参数:
        cow_df: 母牛数据DataFrame
        progress_callback: 进度回调函数
        source_system: 数据来源系统，可选值：伊起牛、慧牧云、优源-DC305
    """
    print(f"[DEBUG-1] 开始预处理母牛数据，行数: {len(cow_df)}, source_system={source_system}")
    try:
        # 多系统列名映射（标准列名 -> 可能的原始列名列表）
        column_aliases = {
            "cow_id": ["耳号", "牛号"],  # 伊起牛+慧牧云用"耳号"，DC305用"牛号"
            "breed": ["品种"],
            "sex": ["性别"],
            "sire": ["父亲号", "父号", "公牛号"],  # 伊起牛"父亲号"、慧牧云"父号"、DC305"公牛号"
            "mgs": ["外祖父", "外祖父号"],  # 伊起牛+慧牧云"外祖父"、DC305"外祖父号"
            "dam": ["母亲号", "母号", "母亲牛号"],  # 伊起牛"母亲号"、慧牧云"母号"、DC305"母亲牛号"
            "mmgs": ["外曾外祖父"],
            "lac": ["胎次"],
            "calving_date": ["最近产犊日期", "产犊日期"],  # 伊起牛"最近产犊日期"、慧牧云+DC305"产犊日期"
            "birth_date": ["牛只出生日期", "生日"],  # 伊起牛"牛只出生日期"、慧牧云+DC305"生日"
            "age": ["月龄"],
            "days_of_age": ["日龄"],  # DC305特有，用于计算月龄
            "services_time": ["本胎次配次", "配次", "配种次数"],  # 伊起牛"本胎次配次"、慧牧云"配次"、DC305"配种次数"
            "peak_milk": ["本胎次奶厅高峰产量"],
            "milk_305": ["305奶量", "305ME"],  # 伊起牛+慧牧云"305奶量"、DC305"305ME"
            "DIM": ["泌乳天数"],
            "repro_status": ["繁育状态", "繁育代号"],  # 伊起牛+慧牧云"繁育状态"、DC305"繁育代号"
        }

        # 替换表头中的中文列名为英文列名
        print("[DEBUG-2] 开始转换列名...")
        print("[DEBUG-3] 原始列名:", cow_df.columns.tolist())

        # 构建实际的列名映射（根据当前数据中存在的列名）
        column_mapping = {}
        for standard_name, aliases in column_aliases.items():
            for alias in aliases:
                if alias in cow_df.columns:
                    column_mapping[alias] = standard_name
                    break  # 找到第一个匹配的就停止

        print(f"[DEBUG-3.1] 构建的列名映射: {column_mapping}")
        cow_df.rename(columns=column_mapping, inplace=True)
        print("[DEBUG-4] 转换后列名:", cow_df.columns.tolist())

        # DC305 特殊数据清洗
        if source_system == "优源-DC305":
            print("[DEBUG-4.1] DC305特殊数据清洗...")
            # 1. 所有字符串列去除尾部空格
            for col in cow_df.columns:
                if cow_df[col].dtype == 'object':
                    cow_df[col] = cow_df[col].astype(str).str.strip()
            # 2. '-' 视为空值
            cow_df.replace('-', np.nan, inplace=True)
            cow_df.replace('', np.nan, inplace=True)
            # 3. 母亲牛号 0 视为空值（处理字符串和数值两种情况）
            if 'dam' in cow_df.columns:
                cow_df.loc[cow_df['dam'] == '0', 'dam'] = np.nan
                cow_df.loc[cow_df['dam'] == '0.0', 'dam'] = np.nan
                cow_df.loc[cow_df['dam'] == 0, 'dam'] = np.nan
                cow_df.loc[cow_df['dam'] == 0.0, 'dam'] = np.nan
            print("[DEBUG-4.1] DC305特殊数据清洗完成")

        # 处理 sex 字段：空值默认为 '母'
        if 'sex' in cow_df.columns:
            empty_sex_count = cow_df['sex'].isna().sum()
            if empty_sex_count > 0:
                # 如果全是空值，直接赋值为'母'（避免float64类型fillna问题）
                if empty_sex_count == len(cow_df):
                    cow_df['sex'] = '母'
                else:
                    cow_df['sex'] = cow_df['sex'].fillna('母')
                print(f"[DEBUG-4.2] sex字段有 {empty_sex_count} 个空值，已默认填充为 '母'")
        else:
            cow_df['sex'] = '母'
            print("[DEBUG-4.2] sex字段不存在，已创建并填充为 '母'")

        # 处理 breed 字段：空值默认为 '荷斯坦'
        if 'breed' in cow_df.columns:
            empty_breed_count = cow_df['breed'].isna().sum()
            if empty_breed_count > 0:
                cow_df['breed'] = cow_df['breed'].fillna('荷斯坦')
                print(f"[DEBUG-4.3] breed字段有 {empty_breed_count} 个空值，已默认填充为 '荷斯坦'")
        else:
            cow_df['breed'] = '荷斯坦'
            print("[DEBUG-4.3] breed字段不存在，已创建并填充为 '荷斯坦'")

        # 处理 是否在场 字段
        # 慧牧云特殊处理：根据"离场日期"推断是否在场
        if '离场日期' in cow_df.columns and '是否在场' not in cow_df.columns:
            print("[DEBUG-4.4] 慧牧云系统：根据'离场日期'推断'是否在场'...")
            # 离场日期为空 → 在场；离场日期不为空 → 离场
            cow_df['是否在场'] = cow_df['离场日期'].apply(
                lambda x: '否' if pd.notna(x) and str(x).strip() not in ['', 'nan', 'NaT'] else '是'
            )
            in_herd_count = (cow_df['是否在场'] == '是').sum()
            left_count = (cow_df['是否在场'] == '否').sum()
            print(f"[DEBUG-4.4] 根据离场日期推断：在场 {in_herd_count} 头，离场 {left_count} 头")
        elif '是否在场' in cow_df.columns:
            empty_in_herd_count = cow_df['是否在场'].isna().sum()
            empty_str_count = (cow_df['是否在场'] == '').sum()
            total_empty = empty_in_herd_count + empty_str_count
            if total_empty > 0:
                cow_df['是否在场'] = cow_df['是否在场'].replace('', np.nan).fillna('是')
                print(f"[DEBUG-4.4] 是否在场字段有 {total_empty} 个空值，已默认填充为 '是'")
        else:
            cow_df['是否在场'] = '是'
            print("[DEBUG-4.4] 是否在场字段不存在，已创建并填充为 '是'")

        # 处理 age（月龄）字段：从 days_of_age 或 birth_date 计算
        if 'age' not in cow_df.columns:
            cow_df['age'] = np.nan

        # 优先使用 days_of_age（DC305特有）计算月龄
        if 'days_of_age' in cow_df.columns:
            print("[DEBUG-4.5] 使用日龄计算月龄...")
            # 日龄转月龄: days_of_age / 30.44
            cow_df['days_of_age'] = pd.to_numeric(cow_df['days_of_age'], errors='coerce')
            mask = cow_df['age'].isna() & cow_df['days_of_age'].notna()
            cow_df.loc[mask, 'age'] = (cow_df.loc[mask, 'days_of_age'] / 30.44).round(1)
            calculated_count = mask.sum()
            if calculated_count > 0:
                print(f"[DEBUG-4.5] 从日龄计算了 {calculated_count} 条月龄数据")

        # 其次使用 birth_date 计算月龄
        if 'birth_date' in cow_df.columns:
            print("[DEBUG-4.6] 检查是否需要从出生日期计算月龄...")
            cow_df['birth_date'] = pd.to_datetime(cow_df['birth_date'], errors='coerce')
            today = pd.Timestamp.now()
            mask = cow_df['age'].isna() & cow_df['birth_date'].notna()
            if mask.any():
                cow_df.loc[mask, 'age'] = cow_df.loc[mask, 'birth_date'].apply(
                    lambda bd: (today.year - bd.year) * 12 + (today.month - bd.month) if pd.notna(bd) else np.nan
                )
                calculated_count = mask.sum()
                print(f"[DEBUG-4.6] 从出生日期计算了 {calculated_count} 条月龄数据")

        # 定义需要保留的列
        print("[DEBUG-5] 设置需要保留的列...")
        columns_to_keep = [
            "cow_id", "breed", "sex", "sire", "dam", "mgs", "mgd", "mmgs",
            "lac", "calving_date", "birth_date", "birth_date_dam", "birth_date_mgd", "age",
            "services_time", "DIM", "peak_milk", "milk_305", "repro_status",
            "group", "是否在场"
        ]

        # 先添加dam相关的派生列（移到前面，在调整列顺序之前）
        print("[DEBUG-6] 添加dam相关派生列...")
        try:
            # 定义ID预处理函数
            # 创建映射字典
            print("  - 创建ID映射字典")
            print("    说明：直接使用原始数据，不做任何格式转换")

            # 创建简单的映射字典（数据本身就很标准，不需要处理）
            birth_map = {}  # cow_id -> birth_date
            dam_map = {}     # cow_id -> dam

            for _, row in cow_df.iterrows():
                # cow_id和dam都保持原样，直接使用
                cow_id = row['cow_id']
                if pd.isna(cow_id):
                    continue

                birth_date = row['birth_date']
                dam = row['dam'] if pd.notna(row['dam']) else None

                # 直接使用原始值作为key
                birth_map[cow_id] = birth_date
                dam_map[cow_id] = dam

            print(f"  - 映射字典创建完成：基础记录 {len(set(birth_map.values()))} 条，总映射 {len(birth_map)} 条")

            # 调试：显示映射内容
            if len(birth_map) <= 20:  # 只在数据量小时显示
                print("  - [DEBUG] 映射键值：")
                for k in sorted(birth_map.keys()):
                    print(f"      '{k}'")



            # 定义查找函数
            def find_birth_date(dam_id):
                """查找dam的出生日期（直接查找，数据本身很标准）"""
                if pd.isna(dam_id):
                    return pd.NaT

                # 直接查找，数据本身很标准
                if dam_id in birth_map:
                    return birth_map[dam_id]

                return pd.NaT

            def find_mgd(dam_id):
                """查找dam的母亲（mgd）"""
                if pd.isna(dam_id):
                    return ''

                # 直接查找
                if dam_id in dam_map:
                    return dam_map[dam_id]

                return ''

            # 打印示例（调试用）
            print("  - 映射示例（前5个）：")
            count = 0
            for cow_id, birth_date in birth_map.items():
                if count < 5:
                    print(f"    cow_id='{cow_id}' -> birth_date={birth_date}")
                    count += 1

            # 1. 添加 birth_date_dam
            print("  - 添加 birth_date_dam 列")
            # 调试：打印dam列的值
            if len(cow_df) <= 10:
                print(f"    [DEBUG] dam列值: {cow_df['dam'].tolist()}")
                print(f"    [DEBUG] 映射键: {list(birth_map.keys())}")
            cow_df['birth_date_dam'] = cow_df['dam'].apply(find_birth_date)
            dam_with_birth_date = cow_df['birth_date_dam'].notna().sum()
            total_dams = cow_df['dam'].notna().sum()
            print(f"    找到 {dam_with_birth_date}/{total_dams} 个dam的出生日期 ({dam_with_birth_date/total_dams*100:.1f}%)" if total_dams > 0 else "    没有dam数据")

            # 2. 添加 mgd（外祖母）
            print("  - 添加 mgd 列")
            cow_df['mgd'] = cow_df['dam'].apply(find_mgd)
            mgd_found = (cow_df['mgd'] != '').sum()
            print(f"    找到 {mgd_found}/{total_dams} 个mgd（外祖母）" if total_dams > 0 else "    没有mgd数据")

            # 3. 添加 birth_date_mgd
            print("  - 添加 birth_date_mgd 列")
            cow_df['birth_date_mgd'] = cow_df['mgd'].apply(find_birth_date)
            mgd_with_birth_date = cow_df['birth_date_mgd'].notna().sum()
            print(f"    找到 {mgd_with_birth_date} 个mgd的出生日期")

            # 填充缺失值
            print("  - 处理缺失值")
            cow_df['birth_date_dam'] = cow_df['birth_date_dam'].fillna(pd.NaT)
            cow_df['mgd'] = cow_df['mgd'].fillna('')
            cow_df['birth_date_mgd'] = cow_df['birth_date_mgd'].fillna(pd.NaT)

            print("  - dam相关列添加完成")
        except Exception as e:
            import logging
            print(f"[DEBUG-ERROR] 添加dam相关列时出错: {e}")
            logging.error(f"添加dam相关列时出错: {e}")
            import traceback
            print(traceback.format_exc())
            # 确保新列存在
            cow_df['birth_date_dam'] = pd.NaT
            cow_df['mgd'] = ""
            cow_df['birth_date_mgd'] = pd.NaT

        # 添加不存在的列并填充为空值
        print("[DEBUG-7] 添加其他缺失列...")
        missing_columns = [col for col in columns_to_keep if col not in cow_df.columns]
        for col in missing_columns:
            print(f"  - 添加缺失列: {col}")
            cow_df[col] = ""

        # 调整列的顺序
        try:
            print("[DEBUG-8] 调整列顺序...")
            cow_df = cow_df[columns_to_keep]
        except KeyError as ke:
            import logging
            print(f"[DEBUG-ERROR] 调整列顺序时出错，找不到列: {ke}")
            logging.error(f"调整列顺序时出错，找不到列: {ke}")
            # 确保只使用存在的列
            existing_columns = [col for col in columns_to_keep if col in cow_df.columns]
            cow_df = cow_df[existing_columns]
            # 添加缺失的列
            for col in columns_to_keep:
                if col not in existing_columns:
                    cow_df[col] = ""

        # 删除性别为"公"的记录
        print("[DEBUG-8] 过滤记录...")
        if 'sex' in cow_df.columns:
            print(f"  - 过滤前记录数: {len(cow_df)}")
            cow_df = cow_df[cow_df['sex'] != '公']
            print(f"  - 过滤后记录数: {len(cow_df)}")

        # 处理数值列，将无效值转换为NaN
        print("[DEBUG-9] 处理数值列...")
        numeric_columns = ['lac', 'age', 'services_time', 'DIM', 'peak_milk', 'milk_305']
        for column in numeric_columns:
            if column in cow_df.columns:
                try:
                    print(f"  - 处理数值列: {column}")
                    # 转换为数值类型，无效值转为NaN
                    cow_df[column] = pd.to_numeric(cow_df[column], errors='coerce')
                    # 替换无限值为NaN
                    cow_df[column] = cow_df[column].replace([np.inf, -np.inf], np.nan)
                except Exception as e:
                    import logging
                    print(f"[DEBUG-ERROR] 处理数值列 {column} 时出错: {e}")
                    logging.error(f"处理数值列 {column} 时出错: {e}")
                    # 确保此列为有效的数值类型
                    cow_df[column] = ""

        # 不对cow_id和dam进行任何处理，保持原始格式
        print("[DEBUG-10] 跳过ID列清理，保持原始格式...")
        # 只对sire, mgs, mmgs进行必要的NAAB格式处理（如果需要）
        # cow_id和dam完全保持原样

        # 调试输出：查看清理后的cow_id和dam
        import logging
        print("[DEBUG-11] 清理后的ID列预览:")
        if not cow_df.empty:
            print(cow_df[['cow_id', 'dam']].head().to_string())
            logging.info(cow_df[['cow_id', 'dam']].head().to_string())

        # 对所有日期列转换为日期格式
        print("[DEBUG-12] 处理日期列...")
        date_columns = ['calving_date', 'birth_date', 'birth_date_dam', 'birth_date_mgd']
        for column in date_columns:
            if column in cow_df.columns:
                try:
                    print(f"  - 处理日期列: {column}")
                    # 如果已经是datetime类型，跳过
                    if not pd.api.types.is_datetime64_any_dtype(cow_df[column]):
                        cow_df[column] = pd.to_datetime(cow_df[column], errors='coerce')
                except Exception as e:
                    import logging
                    print(f"[DEBUG-ERROR] 处理日期列 {column} 时出错: {e}")
                    logging.error(f"处理日期列 {column} 时出错: {e}")
                    cow_df[column] = pd.NaT

        # 检查重复的cow_id
        print("[DEBUG-13] 检查重复的cow_id...")
        try:
            duplicate_cows = cow_df[cow_df.duplicated(subset=['cow_id'], keep=False)]
            if not duplicate_cows.empty:
                duplicate_count = len(duplicate_cows['cow_id'].unique())
                print(f"  - 发现{duplicate_count}个重复的母牛号")
                msg = f"发现{duplicate_count}个重复的母牛号。将按以下优先级保留记录：\n1. 性别为母牛\n2. 在群状态\n3. 出生日期最近\n4. 胎次最小\n5. 随机选择"
                if progress_callback:
                    progress_callback(msg)

                # 定义一个函数来选择要保留的记录
                def select_record(group):
                    try:
                        print(f"  - 处理重复的cow_id: {group['cow_id'].iloc[0]}")
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
                    except Exception as e:
                        import logging
                        print(f"[DEBUG-ERROR] 选择要保留的记录时出错: {e}")
                        logging.error(f"选择要保留的记录时出错: {e}")
                        # 返回第一条记录作为备选
                        return group.iloc[0]

                # 按cow_id分组，应用选择函数
                try:
                    print("  - 开始处理重复记录...")
                    cow_df = cow_df.groupby('cow_id').apply(select_record).reset_index(drop=True)
                    print(f"  - 处理后记录数: {len(cow_df)}")
                except Exception as e:
                    import logging
                    print(f"[DEBUG-ERROR] 处理重复cow_id时出错: {e}")
                    logging.error(f"处理重复cow_id时出错: {e}")
            else:
                print("  - 未发现重复的cow_id")
        except Exception as e:
            import logging
            print(f"[DEBUG-ERROR] 检查重复的cow_id时出错: {e}")
            logging.error(f"检查重复的cow_id时出错: {e}")

        print("[DEBUG-14] 开始处理NAAB编号...")
        invalid_naab_numbers = set()

        # 对sire, mgs, mmgs列进行NAAB编号格式化
        try:
            naab_columns = ['sire', 'mgs', 'mmgs']
            total_naab = cow_df.shape[0] * len(naab_columns)
            current_naab = 0
            last_progress = -1  # 移到外层，避免重复创建

            for column in naab_columns:
                if column in cow_df.columns:
                    print(f"  - 处理NAAB列: {column}")
                    def format_and_track(x):
                        try:
                            nonlocal current_naab, last_progress
                            current_naab += 1
                            # 仅在进度变化时更新（避免过于频繁的更新）
                            if progress_callback:
                                progress = int((current_naab / total_naab) * 100)
                                if progress != last_progress:  # 只有进度真正变化时才更新
                                    last_progress = progress
                                    progress_callback(progress)
                            formatted_id, errors = format_naab_number(x)
                            if errors and len(invalid_naab_numbers) < 10:
                                # 仅在前10个错误时打印，避免过多输出
                                invalid_naab_numbers.add(x)
                            return formatted_id if not errors else ''
                        except Exception as e:
                            import logging
                            # 仅记录错误，不打印调试信息
                            logging.error(f"处理NAAB编号 {x} 时出错: {e}")
                            return ''

                    cow_df[column] = cow_df[column].apply(format_and_track)
                    print(f"  - 完成处理NAAB列: {column}")
        except Exception as e:
            import logging
            print(f"[DEBUG-ERROR] 处理NAAB编号时出错: {e}")
            logging.error(f"处理NAAB编号时出错: {e}")

        if invalid_naab_numbers:
            invalid_numbers_str = '\n'.join(str(num) for num in invalid_naab_numbers)
            print(f"[DEBUG-15] 发现 {len(invalid_naab_numbers)} 个无效的NAAB编号")
            if progress_callback:
                progress_callback(f"NAAB公牛号的牛号部分有误,\n以下牛号HO之后的数字超过5位:\n\n{invalid_numbers_str}\n\n（正确案例:123HO12345）\n\n继续处理...")

        # 注意：dam相关列（birth_date_dam, mgd, birth_date_mgd）已在前面添加

        # 确保关键ID字段都是字符串类型
        print("[DEBUG-16.5] 确保ID字段为字符串类型...")
        if 'cow_id' in cow_df.columns:
            cow_df['cow_id'] = cow_df['cow_id'].astype(str)
        if 'dam' in cow_df.columns:
            cow_df['dam'] = cow_df['dam'].astype(str)
        if 'mgd' in cow_df.columns:
            cow_df['mgd'] = cow_df['mgd'].astype(str)
        if 'sire' in cow_df.columns:
            cow_df['sire'] = cow_df['sire'].astype(str)
        if 'mgs' in cow_df.columns:
            cow_df['mgs'] = cow_df['mgs'].astype(str)

        print("[DEBUG-17] 预处理完成，返回结果DataFrame，行数:", len(cow_df))
        return cow_df
    except Exception as e:
        import logging
        import traceback
        print(f"[DEBUG-FATAL] 预处理母牛数据时出错: {e}")
        print(traceback.format_exc())
        logging.error(f"预处理母牛数据时出错: {e}")
        logging.error(traceback.format_exc())
        raise ValueError(f"预处理母牛数据时出错: {e}")


def process_cow_data_file(input_file: Path, project_path: Path, progress_callback=None, source_system: str = "伊起牛") -> Path:
    """
    标准化母牛数据文件

    参数:
        source_system: 数据来源系统，可选值：伊起牛、慧牧云、优源-DC305
    """
    import logging
    print(f"[DEBUG-FILE-1] 开始标准化母牛数据文件: {input_file}, source_system={source_system}")
    # 将标准化后的文件存储到 standardized_data 文件夹
    standardized_path = project_path / "standardized_data"
    standardized_path.mkdir(parents=True, exist_ok=True)
    print(f"[DEBUG-FILE-2] 标准化路径: {standardized_path}")
    
    # 配置日志
    logging.basicConfig(
        filename=project_path / "cow_data_processing.log",
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logging.info(f"开始处理母牛数据文件: {input_file}")
    logging.info(f"项目路径: {project_path}")
    
    # 读取文件
    try:
        # 在读取时指定数据类型，使用原始列名
        print(f"[DEBUG-FILE-3] 开始读取母牛数据文件..., source_system={source_system}")
        logging.info(f"开始读取母牛数据文件, source_system={source_system}")

        # 根据数据来源系统选择dtype配置
        if source_system == "慧牧云":
            dtype_config = {
                '耳号': str, '父号': str, '母号': str, '外祖父': str, '外曾外祖父': str
            }
        elif source_system == "优源-DC305":
            dtype_config = {
                '牛号': str, '公牛号': str, '母亲牛号': str, '外祖父号': str
            }
        else:  # 默认伊起牛
            dtype_config = {
                '耳号': str, '父亲号': str, '母亲号': str, '外祖父': str, '外曾外祖父': str, '祖父': str, '与配冻精编号': str
            }

        df = pd.read_excel(input_file, dtype=dtype_config)
        print(f"[DEBUG-FILE-4] 成功读取母牛数据文件，数据形状: {df.shape}")
        logging.info(f"成功读取母牛数据文件，数据形状: {df.shape}")
        logging.info(f"列名: {df.columns.tolist()}")
    except Exception as e:
        print(f"[DEBUG-FILE-ERROR] 读取母牛数据文件失败: {e}")
        logging.error(f"读取母牛数据文件失败: {e}")
        import traceback
        logging.error(traceback.format_exc())
        raise ValueError(f"读取母牛数据文件失败: {e}")

    # 对数据进行标准化处理
    try:
        print("[DEBUG-FILE-5] 开始预处理母牛数据...")
        logging.info("开始预处理母牛数据...")
        df_cleaned = preprocess_cow_data(df, progress_callback, source_system)
        print(f"[DEBUG-FILE-6] 成功预处理母牛数据，处理后数据形状: {df_cleaned.shape}")
        logging.info(f"成功预处理母牛数据，处理后数据形状: {df_cleaned.shape}")
    except Exception as e:
        print(f"[DEBUG-FILE-ERROR] 预处理母牛数据失败: {e}")
        logging.error(f"预处理母牛数据失败: {e}")
        import traceback
        logging.error(traceback.format_exc())
        raise ValueError(f"预处理母牛数据失败: {e}")

    # 保存前格式化日期列（确保日期格式正确）
    print("[DEBUG-FILE-7] 格式化日期列为Excel格式")
    date_columns_to_format = ['calving_date', 'birth_date', 'birth_date_dam', 'birth_date_mgd']
    for col in date_columns_to_format:
        if col in df_cleaned.columns:
            # 保持为datetime类型，让pandas处理Excel格式
            # 只需要确保NaT值被正确处理
            df_cleaned[col] = pd.to_datetime(df_cleaned[col], errors='coerce')

    # 确保所有ID列保持为字符串类型（保持原始格式）
    print("[DEBUG-FILE-7.1] 确保ID列保持原始字符串格式")
    id_columns = ['cow_id', 'dam', 'sire', 'mgs', 'mgd', 'mmgs']
    for col in id_columns:
        if col in df_cleaned.columns:
            # 先转为字符串
            df_cleaned[col] = df_cleaned[col].astype(str)
            # 将 'nan' 或空字符串替换回 NaN
            df_cleaned[col] = df_cleaned[col].replace(['nan', 'None', ''], pd.NA)
            print(f"  {col}列类型: {df_cleaned[col].dtype}")

    # 保存标准化后的文件
    output_file = standardized_path / "processed_cow_data.xlsx"
    try:
        print(f"[DEBUG-FILE-8] 开始保存标准化后的母牛数据到: {output_file}")
        logging.info(f"开始保存标准化后的母牛数据到: {output_file}")
        df_cleaned.to_excel(output_file, index=False)
        print("[DEBUG-FILE-9] 成功保存标准化后的母牛数据")
        logging.info("成功保存标准化后的母牛数据")
    except Exception as e:
        print(f"[DEBUG-FILE-ERROR] 保存母牛数据文件失败: {e}")
        logging.error(f"保存母牛数据文件失败: {e}")
        import traceback
        logging.error(traceback.format_exc())
        raise ValueError(f"保存母牛数据文件失败: {e}")

    # 确保文件存在
    if not output_file.exists():
        print("[DEBUG-FILE-ERROR] 标准化后的母牛数据文件未生成。")
        logging.error("标准化后的母牛数据文件未生成。")
        raise ValueError("标准化后的母牛数据文件未生成。")

    print(f"[DEBUG-FILE-10] 母牛数据处理完成，输出文件: {output_file}")
    logging.info(f"母牛数据处理完成，输出文件: {output_file}")
    return output_file

def preprocess_bull_data(bull_df, progress_callback=None):
    # 清理 bull_id - 保持字符串类型
    bull_df['bull_id'] = bull_df['bull_id'].astype(str).apply(lambda x: x.replace(' ', '').strip())
    bull_df = bull_df.dropna(subset=['bull_id'])  # 删除 NaN 行
    bull_df = bull_df[bull_df['bull_id'] != '']  # 删除空字符串行
    bull_df = bull_df[~bull_df['bull_id'].str.contains("nan", case=False)]  # 删除包含"nan"的行

    print(f"[DEBUG-BULL-PREPROCESS] 开始处理 {len(bull_df)} 条备选公牛记录")

    # 保存原始公牛号（用于最终输出时还原）
    bull_df['bull_id_original'] = bull_df['bull_id'].copy()

    all_errors = []
    formatted_ids = []
    invalid_count = 0

    total = bull_df.shape[0]
    for idx, row in bull_df.iterrows():
        original_id = row['bull_id']
        formatted_id, errors = format_naab_number(original_id)
        if errors:
            # 记录错误但不中断处理
            all_errors.extend(errors)
            invalid_count += 1
            # 对于格式错误的NAAB号，保留原始值以便后续上传为缺失公牛
            formatted_ids.append(original_id)
            print(f"[DEBUG-BULL-PREPROCESS] 保留格式异常的NAAB号: {original_id}")
        else:
            # 格式正确，使用格式化后的ID
            formatted_ids.append(formatted_id)

        if progress_callback:
            progress = int((idx + 1) / total * 100)
            progress_callback(progress)

    bull_df['bull_id'] = formatted_ids

    # 显示警告信息但不终止处理（只在日志中显示，不弹窗）
    if all_errors:
        print(f"[DEBUG-BULL-PREPROCESS] ⚠️ 发现 {invalid_count} 个格式异常的NAAB号，将保留原值")
        print(f"[DEBUG-BULL-PREPROCESS] 这些公牛在查询时会被识别为缺失公牛")
        # 只显示前5个错误作为示例
        sample_errors = all_errors[:5]
        for error in sample_errors:
            print(f"[DEBUG-BULL-PREPROCESS]   - {error}")
        if len(all_errors) > 5:
            print(f"[DEBUG-BULL-PREPROCESS]   ... 还有 {len(all_errors) - 5} 个类似错误")

        # 不在这里弹窗，等到检查数据库后统一提示

    # 确保 bull_id 为字符串类型
    bull_df['bull_id'] = bull_df['bull_id'].astype(str)

    print(f"[DEBUG-BULL-PREPROCESS] 处理完成，保留所有 {len(bull_df)} 条记录")
    # 返回处理后的DataFrame，包含格式错误的记录
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
        df = pd.read_excel(input_file, dtype={'bull_id': str, '公牛号': str, '冻精编号': str})
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

    # ========== 新增：检查本地数据库并上传缺失公牛 ==========
    print("\n[检查点-上传] 开始检查本地数据库中的缺失公牛...")
    try:
        from core.data.update_manager import LOCAL_DB_PATH
        from sqlalchemy import create_engine, text
        import datetime

        # 连接本地数据库
        db_engine = create_engine(f'sqlite:///{LOCAL_DB_PATH}')
        print(f"[检查点-上传] 本地数据库路径: {LOCAL_DB_PATH}")

        missing_bulls = []
        bull_ids = df_cleaned['bull_id'].tolist()
        print(f"[检查点-上传] 需要检查 {len(bull_ids)} 个公牛")

        # 查询每个公牛是否在本地数据库中存在
        with db_engine.connect() as conn:
            for bull_id in bull_ids:
                result = conn.execute(
                    text("SELECT COUNT(*) as cnt FROM bull_library WHERE `BULL NAAB`=:bull_id"),
                    {"bull_id": str(bull_id)}
                ).fetchone()

                if result[0] == 0:
                    # 数据库中不存在
                    missing_bulls.append(bull_id)
                    print(f"[检查点-上传] 缺失公牛: {bull_id}")

        print(f"[检查点-上传] 共发现 {len(missing_bulls)} 个缺失公牛")

        # 如果有缺失公牛，上传到云端
        if missing_bulls:
            print("[检查点-上传] 准备上传缺失公牛到云端...")

            # 准备上传数据
            from api.api_client import get_api_client

            # 获取用户名（从主窗口）
            try:
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
                if app:
                    for widget in app.topLevelWidgets():
                        if hasattr(widget, 'username'):
                            username = widget.username
                            break
                    else:
                        username = 'unknown'
                else:
                    username = 'unknown'
            except:
                username = 'unknown'

            bulls_data = []
            for bull_id in missing_bulls:
                bulls_data.append({
                    'bull': str(bull_id),
                    'source': 'bull_upload',
                    'time': datetime.datetime.now().isoformat(),
                    'user': username
                })

            print(f"[检查点-上传] 用户名: {username}")
            print(f"[检查点-上传] 调用API上传 {len(bulls_data)} 条记录...")

            api_client = get_api_client()
            success = api_client.upload_missing_bulls(bulls_data)

            # 弹窗通知用户缺失公牛（合并提示，不管上传成功与否都显示）
            try:
                from PyQt6.QtWidgets import QMessageBox

                # 构建缺失公牛列表（最多显示20个）
                bull_list = "\n".join([f"• {bull}" for bull in missing_bulls[:20]])
                if len(missing_bulls) > 20:
                    bull_list += f"\n... 还有 {len(missing_bulls) - 20} 个"

                msg = QMessageBox()
                msg.setIcon(QMessageBox.Icon.Information)
                msg.setWindowTitle("在本地数据库中未找到部分公牛")
                msg.setText(f"在本地数据库中未找到 {len(missing_bulls)} 个公牛")
                msg.setInformativeText(
                    "建议您稍后更新本地数据库，或联系管理员添加这些公牛的完整信息。"
                )
                msg.setDetailedText(f"缺失公牛列表：\n\n{bull_list}")
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.exec()

            except Exception as e:
                print(f"[检查点-上传] 无法显示通知对话框: {e}")

            # 上传结果日志
            if success:
                print(f"[检查点-上传] ✅ 成功上传 {len(missing_bulls)} 个缺失公牛到云端")
            else:
                print(f"[检查点-上传] ❌ 上传失败")
        else:
            print("[检查点-上传] ✅ 所有公牛都在本地数据库中，无需上传")

        db_engine.dispose()

    except Exception as e:
        print(f"[检查点-上传] ⚠️ 检查缺失公牛时发生异常: {e}")
        import traceback
        print(f"[检查点-上传] 异常详情:\n{traceback.format_exc()}")
        # 即使检查失败，也继续返回文件路径，不影响主流程

    print("[检查点-上传] 缺失公牛检查完成\n")
    # ==========================================================

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
            df = pd.read_csv(input_file, dtype={'牛号': str, '耳号': str, 'cow_id': str})
        else:
            df = pd.read_excel(input_file, dtype={'牛号': str, '耳号': str, 'cow_id': str})
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

    # 确保牛号字段为字符串类型
    if '牛号' in df_cleaned.columns:
        df_cleaned['牛号'] = df_cleaned['牛号'].astype(str)
    if 'cow_id' in df_cleaned.columns:
        df_cleaned['cow_id'] = df_cleaned['cow_id'].astype(str)

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

def process_breeding_record_file(input_file: Path, project_path: Path, cow_df=None, progress_callback=None, source_system: str = "伊起牛") -> Path:
    """
    标准化配种记录数据文件 - 完全重写版本

    核心策略：先备份配种日期列，处理其他列后再转换日期格式，确保数据不丢失

    参数:
        input_file (Path): 输入的配种记录数据文件路径
        project_path (Path): 当前项目的路径
        cow_df (DataFrame, optional): 母牛数据的DataFrame，用于映射父号
        progress_callback (callable, optional): 进度回调函数
        source_system (str): 数据来源系统，可选值：伊起牛、慧牧云、优源-DC305

    返回:
        Path: 标准化后的配种记录数据文件路径
    """
    import logging

    print("=" * 80)
    print(f"🔵 使用全新重写的 process_breeding_record_file (v1.2.0.14), source_system={source_system}")
    print("=" * 80)
    logging.info(f"使用全新重写的 process_breeding_record_file, source_system={source_system}")

    # ========== 第1步: 读取原始数据 ==========
    print(f"\n【步骤1】读取原始文件: {input_file}")
    standardized_path = project_path / "standardized_data"
    standardized_path.mkdir(parents=True, exist_ok=True)

    try:
        if input_file.suffix.lower() == '.csv':
            df_raw = pd.read_csv(input_file, dtype={'耳号': str, '母牛号': str, '冻精编号': str})
        else:
            # 🔧 关键修复：先读取，然后立即转换日期列为字符串
            df_raw = pd.read_excel(input_file, dtype={'耳号': str, '母牛号': str, '冻精编号': str})
        print(f"  ✓ 读取成功，原始数据形状: {df_raw.shape}")
        print(f"  ✓ 包含列: {', '.join(df_raw.columns)}")

        # 🔧 立即转换所有可能的日期列为字符串（在列名映射之前）
        possible_date_columns = ['配种日期', '配种时间', '授精日期', '授精时间', 'breed_date', 'breeding_date',
                                  '出生日期', '最近产犊日期', '最近发情日期', '初检日期', '创建日期']
        for col in possible_date_columns:
            if col in df_raw.columns:
                # 如果是datetime类型，转换为字符串
                if df_raw[col].dtype == 'datetime64[ns]' or pd.api.types.is_datetime64_any_dtype(df_raw[col]):
                    df_raw[col] = df_raw[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                    print(f"  🔧 已将列 '{col}' 从datetime转换为字符串")
                # 如果是object类型但包含datetime对象，也转换
                elif df_raw[col].dtype == 'object':
                    def safe_datetime_to_str(val):
                        if pd.isna(val):
                            return val
                        if isinstance(val, pd.Timestamp) or hasattr(val, 'strftime'):
                            try:
                                return val.strftime('%Y-%m-%d %H:%M:%S')
                            except:
                                return str(val)
                        return val
                    df_raw[col] = df_raw[col].apply(safe_datetime_to_str)
                    print(f"  🔧 已清理列 '{col}' 中的datetime对象")

        # 🔍 诊断：检查读取后配种日期列的情况
        if '配种日期' in df_raw.columns:
            print(f"  🔍 配种日期列读取后的数据类型: {df_raw['配种日期'].dtype}")
            print(f"  🔍 配种日期前3个值: {df_raw['配种日期'].head(3).tolist()}")
            print(f"  🔍 配种日期前3个值的类型: {[type(v).__name__ for v in df_raw['配种日期'].head(3)]}")
    except Exception as e:
        error_msg = f"读取配种记录文件失败: {e}"
        print(f"  ✗ {error_msg}")
        raise ValueError(error_msg)


    # ========== 第2步: 列名映射 ==========
    print(f"\n【步骤2】列名标准化")
    # 多系统列名映射（包含新增的慧牧云和DC305列名）
    column_mappings = {
        '耳号': ['耳号', '牛号', '母牛号', '母牛耳号', 'cow_id'],
        '配种日期': ['配种日期', '配种时间', '授精日期', '授精时间', '事件日期', '日期'],  # 慧牧云"事件日期"、DC305"日期"
        '冻精编号': ['冻精编号', '冻精号', '公牛号', '精液号', '备注'],  # 慧牧云"冻精号"、DC305"备注"
        '冻精类型': ['冻精类型', '精液类型', '类型', '是否性控']  # 慧牧云"是否性控"（需值转换）
    }

    # 检测是否存在"是否性控"列（慧牧云特有）
    has_sex_control_column = '是否性控' in df_raw.columns

    for target_col, possible_names in column_mappings.items():
        if target_col not in df_raw.columns:
            for possible_name in possible_names:
                if possible_name in df_raw.columns:
                    df_raw.rename(columns={possible_name: target_col}, inplace=True)
                    print(f"  ✓ 映射列名: {possible_name} → {target_col}")
                    break

    # 慧牧云特殊处理：是否性控 → 冻精类型 值转换
    if has_sex_control_column and '冻精类型' in df_raw.columns:
        print("  🔧 慧牧云系统：转换'是否性控'为'冻精类型'...")
        def convert_sex_control(val):
            if pd.isna(val):
                return '普通冻精'
            if val == True or str(val).lower() in ['true', '是', '1']:
                return '性控冻精'
            return '普通冻精'
        df_raw['冻精类型'] = df_raw['冻精类型'].apply(convert_sex_control)
        print(f"  ✓ 是否性控值转换完成")

    # DC305 特殊处理
    if source_system == "优源-DC305":
        print("  🔧 DC305系统：特殊数据清洗...")
        # 所有字符串列去除尾部空格
        for col in df_raw.columns:
            if df_raw[col].dtype == 'object':
                df_raw[col] = df_raw[col].astype(str).str.strip()
        # '-' 视为空值
        df_raw.replace('-', np.nan, inplace=True)
        df_raw.replace('', np.nan, inplace=True)
        print("  ✓ DC305特殊数据清洗完成")

    # ========== 第3步: 检查必需列 ==========
    print(f"\n【步骤3】检查必需列")
    required_columns = ['耳号', '配种日期', '冻精编号', '冻精类型']
    missing_columns = [col for col in required_columns if col not in df_raw.columns]
    if missing_columns:
        # 简化错误消息，适用于所有数据源
        if '冻精类型' in missing_columns:
            error_msg = "配种记录数据缺少'冻精类型'列"
        else:
            error_msg = f"配种记录数据缺少以下必需列: {', '.join(missing_columns)}"
        print(f"  ✗ {error_msg}")
        raise ValueError(error_msg)
    print(f"  ✓ 所有必需列都存在")

    # ========== 第4步: 删除缺失值 ==========
    print(f"\n【步骤4】删除缺失值")
    print(f"  - 原始记录数: {len(df_raw)}")

    # 🔍 诊断：显示每个关键列的缺失情况
    print(f"  🔍 关键列缺失值统计:")
    for col in required_columns:
        missing_count = df_raw[col].isna().sum()
        if missing_count > 0:
            print(f"     - {col}: {missing_count} 条缺失 ({missing_count/len(df_raw)*100:.1f}%)")

    df_cleaned = df_raw.dropna(subset=required_columns).copy()
    print(f"  - 删除缺失值后: {len(df_cleaned)}")
    print(f"  - 删除了 {len(df_raw) - len(df_cleaned)} 条记录 ({(len(df_raw) - len(df_cleaned))/len(df_raw)*100:.1f}%)")


    # ========== 第5步: 备份配种日期列（关键步骤！） ==========
    print(f"\n【步骤5】🔐 备份配种日期列（确保数据安全）")
    breed_date_backup = df_cleaned['配种日期'].copy()  # 创建深拷贝
    print(f"  ✓ 已备份 {len(breed_date_backup)} 条配种日期记录")
    print(f"  - 数据类型: {breed_date_backup.dtype}")
    print(f"  - 非空记录: {breed_date_backup.notna().sum()}")
    print(f"  - 样本数据（前3个）: {breed_date_backup.iloc[:3].tolist()}")

    # 🔍 诊断：检查备份时索引273的值
    if len(breed_date_backup) > 273:
        val_273_backup = breed_date_backup.iloc[273]
        print(f"  🔍 备份时索引273的值: {repr(val_273_backup)} (type: {type(val_273_backup).__name__})")

    # 🔍 诊断：检查备份中的唯一值类型
    sample_types = [type(v).__name__ for v in breed_date_backup.iloc[:10]]
    print(f"  🔍 前10个值的类型: {set(sample_types)}")

    # ========== 第6步: 处理ID字段类型 ==========
    print(f"\n【步骤6】确保ID字段为字符串类型")
    df_cleaned['耳号'] = df_cleaned['耳号'].astype(str)
    df_cleaned['冻精编号'] = df_cleaned['冻精编号'].astype(str)
    df_cleaned['冻精类型'] = df_cleaned['冻精类型'].astype(str)
    print(f"  ✓ ID字段类型转换完成")

    # ========== 第7步: 处理冻精编号格式化 ==========
    print(f"\n【步骤7】格式化冻精编号")

    def format_naab_safe(naab_id):
        """安全的NAAB号格式化函数

        重要：如果格式化失败，保留原值而不是清空！
        这样即使是非标准NAAB号（如国内编号），也能保留在配种记录中。
        """
        try:
            if pd.isna(naab_id) or not str(naab_id).strip():
                return ''

            original_str = str(naab_id).strip()
            formatted_id, errors = format_naab_number(original_str)

            # 如果格式化成功，返回格式化后的值
            if formatted_id is not None:
                return formatted_id

            # 如果格式化失败，保留原值（可能是非标准编号）
            return original_str

        except Exception:
            # 异常情况也保留原值
            return str(naab_id).strip() if not pd.isna(naab_id) else ''

    # 使用Series.apply进行格式化，不影响DataFrame的其他列
    formatted_naab_series = df_cleaned['冻精编号'].apply(format_naab_safe)
    df_cleaned['冻精编号'] = formatted_naab_series

    non_empty_count = (df_cleaned['冻精编号'] != '').sum()

    # 统计标准NAAB号和非标准编号
    standard_count = 0
    non_standard_count = 0
    for naab in df_cleaned['冻精编号']:
        if naab and str(naab).strip():
            formatted, errors = format_naab_number(str(naab))
            if formatted is not None:
                standard_count += 1
            else:
                non_standard_count += 1

    print(f"  ✓ 冻精编号格式化完成")
    print(f"  - 总编号数: {non_empty_count}/{len(df_cleaned)}")
    print(f"  - 标准NAAB号: {standard_count} ({standard_count/len(df_cleaned)*100:.1f}%)")
    if non_standard_count > 0:
        print(f"  - 非标准编号: {non_standard_count} ({non_standard_count/len(df_cleaned)*100:.1f}%) [已保留原值]")

    # ========== 第8步: 恢复配种日期并转换为datetime ==========
    print(f"\n【步骤8】🔓 恢复并转换配种日期")
    # 从备份中恢复配种日期
    df_cleaned['配种日期'] = breed_date_backup.copy()
    print(f"  ✓ 已从备份恢复配种日期")
    print(f"  - 恢复后非空数: {df_cleaned['配种日期'].notna().sum()}")
    print(f"  - 恢复后数据类型: {df_cleaned['配种日期'].dtype}")

    # 🔍 诊断：检查恢复后的数据样本
    print(f"  🔍 恢复后样本数据（前5个）:")
    for i in range(min(5, len(df_cleaned))):
        val = df_cleaned['配种日期'].iloc[i]
        print(f"     [{i}] {repr(val)} (type: {type(val).__name__})")

    # 🔍 诊断：检查可能失败的记录（index=273）
    if len(df_cleaned) > 273:
        val_273 = df_cleaned['配种日期'].iloc[273]
        print(f"  🔍 索引273的值: {repr(val_273)} (type: {type(val_273).__name__})")

    # 🔧 使用自定义日期解析器，不依赖pandas的to_datetime
    print(f"  🔧 使用自定义日期解析器...")
    from datetime import datetime

    def parse_date_manually(date_val):
        """手动解析日期字符串为datetime对象"""
        if pd.isna(date_val):
            return pd.NaT

        # 如果已经是datetime对象，直接返回
        if isinstance(date_val, (datetime, pd.Timestamp)):
            return pd.Timestamp(date_val)

        # 转换为字符串并清理
        date_str = str(date_val).strip()

        # 尝试多种日期格式
        date_formats = [
            '%Y-%m-%d %H:%M:%S',    # 2025-10-11 17:43:02
            '%Y-%m-%d',              # 2025-10-11
            '%Y/%m/%d %H:%M:%S',    # 2025/10/11 17:43:02
            '%Y/%m/%d',              # 2025/10/11
            '%d-%m-%Y %H:%M:%S',    # 11-10-2025 17:43:02
            '%d/%m/%Y %H:%M:%S',    # 11/10/2025 17:43:02
        ]

        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return pd.Timestamp(dt)
            except (ValueError, TypeError):
                continue

        # 如果所有格式都失败，返回NaT
        print(f"      ⚠️  无法解析日期: {repr(date_str)}")
        return pd.NaT

    df_cleaned['配种日期'] = df_cleaned['配种日期'].apply(parse_date_manually)
    successful_conversions = df_cleaned['配种日期'].notna().sum()
    print(f"  ✓ datetime转换完成")
    print(f"  - 成功转换: {successful_conversions}/{len(breed_date_backup)}")
    print(f"  - 转换成功率: {successful_conversions/len(breed_date_backup)*100:.1f}%")

    if successful_conversions < len(breed_date_backup) * 0.9:
        print(f"  ⚠️  警告: 超过10%的日期转换失败")
        # 🔍 诊断：找出转换失败的记录样本
        failed_dates = df_cleaned[df_cleaned['配种日期'].isna()]
        if len(failed_dates) > 0:
            print(f"  🔍 转换失败的记录样本（前5个）:")
            for idx in failed_dates.head(5).index:
                original_val = breed_date_backup.loc[idx]
                # 检查字符串的详细信息
                if isinstance(original_val, str):
                    print(f"     耳号={df_cleaned.loc[idx, '耳号']}, 原始值={repr(original_val)}")
                    print(f"       - 长度: {len(original_val)}")
                    print(f"       - 字节表示: {original_val.encode('utf-8')}")
                    print(f"       - ASCII码: {[ord(c) for c in original_val[:10]]}")
                else:
                    print(f"     耳号={df_cleaned.loc[idx, '耳号']}, 原始值={repr(original_val)}, 类型={type(original_val).__name__}")

    # ========== 第9步: 填充其他列的空值 ==========
    print(f"\n【步骤9】填充其他列的空值")
    for col in ['耳号', '冻精编号', '冻精类型']:
        df_cleaned[col] = df_cleaned[col].fillna('')
    print(f"  ✓ 非日期列空值填充完成")

    # ========== 第10步: 添加父号列（从母牛数据映射） ==========
    print(f"\n【步骤10】映射父号")
    if cow_df is not None and not cow_df.empty and 'cow_id' in cow_df.columns and 'sire' in cow_df.columns:
        try:
            # 创建映射字典
            cow_df['cow_id'] = cow_df['cow_id'].astype(str)
            sire_dict = dict(zip(cow_df['cow_id'], cow_df['sire']))

            # 映射父号
            df_cleaned['父号'] = df_cleaned['耳号'].map(sire_dict).fillna('')
            matched_count = (df_cleaned['父号'] != '').sum()
            print(f"  ✓ 父号映射完成")
            print(f"  - 成功匹配: {matched_count}/{len(df_cleaned)}")
        except Exception as e:
            print(f"  ✗ 父号映射失败: {e}")
            df_cleaned['父号'] = ''
    else:
        print(f"  - 未提供母牛数据，父号列设为空")
        df_cleaned['父号'] = ''

    # ========== 第11步: 重新排列列顺序 ==========
    print(f"\n【步骤11】重新排列列顺序")
    columns_order = ['耳号', '父号', '冻精编号', '配种日期', '冻精类型']
    df_final = df_cleaned[columns_order].copy()
    print(f"  ✓ 列顺序: {' | '.join(columns_order)}")

    # ========== 第12步: 保存文件 ==========
    print(f"\n【步骤12】保存标准化文件")
    output_file = standardized_path / "processed_breeding_data.xlsx"
    try:
        df_final.to_excel(output_file, index=False)
        print(f"  ✓ 文件已保存: {output_file}")
    except Exception as e:
        error_msg = f"保存文件失败: {e}"
        print(f"  ✗ {error_msg}")
        raise ValueError(error_msg)

    # ========== 最终验证 ==========
    print(f"\n{'='*80}")
    print("📊 最终数据统计:")
    print(f"  - 总记录数: {len(df_final)}")
    print(f"  - 配种日期完整率: {df_final['配种日期'].notna().sum()}/{len(df_final)} ({df_final['配种日期'].notna().sum()/len(df_final)*100:.1f}%)")
    print(f"  - 冻精编号填充率: {(df_final['冻精编号']!='').sum()}/{len(df_final)} ({(df_final['冻精编号']!='').sum()/len(df_final)*100:.1f}%)")
    print(f"  - 父号匹配率: {(df_final['父号']!='').sum()}/{len(df_final)} ({(df_final['父号']!='').sum()/len(df_final)*100:.1f}%)")
    print(f"{'='*80}\n")

    # 调用进度回调
    if progress_callback:
        progress_callback(100, "配种记录处理完成")

    return output_file


# === 4. 修改 preprocess_genomic_data 函数 ===
def preprocess_genomic_data(genomic_df, progress_callback=None):
    """
    预处理基因组检测数据的主函数。通过检查关键列名，
    确定不同的报告类型，进而选择对应的映射字典进行重命名。
    不再需要 combine_first 逻辑。

    :param genomic_df: 读取 Excel/CSV 后得到的原始 DataFrame
    :param progress_callback: 进度更新的回调函数，可选 - 接收 (progress, message) 参数
    :return: 预处理并标准化后的 DataFrame
    """
    print("开始预处理基因组检测数据...")
    genomic_df = genomic_df.copy()
    print(f"输入数据的列名: {genomic_df.columns.tolist()}")
    print(f"输入数据的形状: {genomic_df.shape}")

    try:
        # 1. 根据关键列名检测报告类型
        if progress_callback:
            progress_callback(None, f"检测报告类型中...输入数据有 {len(genomic_df)} 行，{len(genomic_df.columns)} 列")
        
        report_type = detect_report_type(genomic_df)
        print(f"识别到的报告类型: {report_type}")
        
        if progress_callback:
            progress_callback(None, f"识别到报告类型: {report_type}")

        # 2. 选择对应的映射字典
        mapping_dict = GENOMIC_COLUMN_MAPPING_BY_TYPE[report_type]
        print(f"使用映射字典: {mapping_dict}")
        
        if progress_callback:
            progress_callback(None, f"选择映射字典，包含 {len(mapping_dict)} 个列映射规则")

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

        if progress_callback:
            progress_callback(None, f"找到牛号标识列: {cow_id_col}")

        # 保存 cow_id 的原始值，供后续插回最终 DataFrame
        cow_id_values = genomic_df[cow_id_col].copy()

        # 4. 按照当前类型的映射字典重命名列
        rename_dict = {old: new for old, new in mapping_dict.items() if old in genomic_df.columns}
        print(f"将要重命名的列: {rename_dict}")
        
        if progress_callback:
            progress_callback(None, f"将重命名 {len(rename_dict)} 个列到标准格式")
        
        genomic_df = genomic_df.rename(columns=rename_dict)
        print(f"重命名后的列名: {genomic_df.columns.tolist()}")
        
        if progress_callback:
            progress_callback(None, f"列重命名完成，开始构建标准化数据结构...")

        # 5. 构建 result_rows，用来拼装标准化后的数据
        result_rows = []
        total_rows = len(genomic_df)
        
        for idx in range(total_rows):
            # 每处理100行更新一次进度
            if progress_callback and idx % 100 == 0:
                progress_callback(None, f"正在处理第 {idx+1}/{total_rows} 行数据...")
            
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

        if progress_callback:
            progress_callback(None, f"数据行处理完成，共处理 {len(result_rows)} 行")

        # 6. 生成最终的 standardized_df
        standardized_df = pd.DataFrame(result_rows)

        # 确保列顺序和 STANDARD_GENOMIC_COLUMNS 一致
        # 如果一些列在 STANDARD_GENOMIC_COLUMNS 中未出现，就忽略
        standardized_df = standardized_df[STANDARD_GENOMIC_COLUMNS + ["cow_id", "Results_Last_Updated"]]

        # 确保cow_id为字符串类型
        if 'cow_id' in standardized_df.columns:
            standardized_df['cow_id'] = standardized_df['cow_id'].astype(str)

        print(f"处理后的数据形状: {standardized_df.shape}")
        print("基因组数据预处理完成")
        
        if progress_callback:
            progress_callback(None, f"标准化完成：{standardized_df.shape[0]} 行 x {standardized_df.shape[1]} 列")

        return standardized_df

    except Exception as e:
        print(f"预处理过程中发生错误: {str(e)}")
        print("当前处理的数据状态:")
        print(f"- 原始数据形状: {genomic_df.shape}")
        print(f"- 原始数据列名: {genomic_df.columns.tolist()}")
        
        if progress_callback:
            progress_callback(None, f"预处理错误: {str(e)}")
        
        raise

# === 5. 修改 process_genomic_data_file 函数 ===
def process_genomic_data_file(input_files: list[Path], project_path: Path, progress_callback=None) -> Path:
    """
    标准化基因组检测数据文件。

    :param input_files: 输入文件路径列表
    :param project_path: 项目根目录路径
    :param progress_callback: 进度更新的回调函数，可选 - 应该接收 (progress, message) 参数
    :return: 最终汇总文件的路径
    """
    print("开始处理基因组检测数据...")
    
    # 更新进度：开始处理
    if progress_callback:
        progress_callback(5, "开始处理基因组检测数据...")

    standardized_path = project_path / "standardized_data"
    standardized_path.mkdir(parents=True, exist_ok=True)
    
    if progress_callback:
        progress_callback(8, f"创建标准化目录: {standardized_path}")

    processed_files = []  # 用于存储处理后的文件路径
    total_files = len(input_files)

    if progress_callback:
        progress_callback(10, f"准备处理 {total_files} 个文件")

    # 为每个输入文件创建独立的处理结果
    for idx, input_file in enumerate(input_files, start=1):
        try:
            print(f"处理文件 {idx}/{len(input_files)}: {input_file.name}")
            
            # 更新进度：读取文件
            if progress_callback:
                file_progress = 10 + (idx - 1) * (60 / total_files)
                progress_callback(int(file_progress), f"正在读取文件 {idx}/{total_files}: {input_file.name}")
            
            # 读取文件
            if input_file.suffix.lower() == '.csv':
                df = pd.read_csv(input_file, dtype={'cow_id': str, 'Farm ID': str, 'On-farm ID (Herd Management #)': str})
                if progress_callback:
                    progress_callback(int(file_progress + 5), f"成功读取CSV文件，数据行数: {len(df)}")
            else:
                df = pd.read_excel(input_file, dtype={'cow_id': str, 'Farm ID': str, 'On-farm ID (Herd Management #)': str})
                if progress_callback:
                    progress_callback(int(file_progress + 5), f"成功读取Excel文件，数据行数: {len(df)}")

            # 更新进度：预处理数据
            if progress_callback:
                process_progress = 10 + (idx - 1) * (60 / total_files) + (15 / total_files)
                progress_callback(int(process_progress), f"开始预处理文件 {idx}: 列数 {len(df.columns)}")

            # 预处理数据（根据报告类型重命名）
            df_cleaned = preprocess_genomic_data(df, progress_callback)
            
            if progress_callback:
                save_progress = 10 + (idx - 1) * (60 / total_files) + (25 / total_files)
                progress_callback(int(save_progress), f"数据预处理完成，处理后行数: {len(df_cleaned)}")

            # 保存独立的处理结果
            output_file = standardized_path / f"processed_genomic_data_{idx}.xlsx"
            df_cleaned.to_excel(output_file, index=False)
            print(f"已保存处理结果到: {output_file}")
            processed_files.append(output_file)
            
            # 更新进度：完成单个文件
            if progress_callback:
                complete_progress = 10 + idx * (60 / total_files)
                progress_callback(int(complete_progress), f"文件 {idx} 处理完成，保存至: {output_file.name}")

        except Exception as e:
            error_msg = f"处理文件 {input_file.name} 时发生错误: {e}"
            if progress_callback:
                progress_callback(int(10 + (idx - 1) * (60 / total_files)), f"错误: {error_msg}")
            raise ValueError(error_msg)

    # 更新进度：开始合并结果
    if progress_callback:
        progress_callback(75, f"开始合并 {len(processed_files)} 个处理结果...")

    # 合并所有处理结果到最终文件
    try:
        final_output = standardized_path / "processed_genomic_data.xlsx"

        if not final_output.exists():
            if len(processed_files) == 1:
                # 只有一份处理结果，直接重命名为最终汇总文件
                processed_files[0].rename(final_output)
                print(f"已保存最终汇总结果到: {final_output}")
                if progress_callback:
                    progress_callback(95, f"单文件处理完成，重命名为: {final_output.name}")
            else:
                # 多份处理结果，进行合并
                if progress_callback:
                    progress_callback(80, "读取所有处理结果进行合并...")
                
                final_df = pd.concat(
                    [pd.read_excel(f) for f in processed_files],
                    ignore_index=True
                )
                
                if progress_callback:
                    progress_callback(85, f"合并完成，总记录数: {len(final_df)}")

                # 根据 cow_id 和 Results_Last_Updated 去重
                final_df['Results_Last_Updated'] = pd.to_datetime(final_df['Results_Last_Updated'])
                final_df = final_df.sort_values('Results_Last_Updated', ascending=False)
                original_count = len(final_df)
                final_df = final_df.drop_duplicates(subset='cow_id', keep='first')
                deduplicated_count = len(final_df)
                
                if progress_callback:
                    progress_callback(90, f"去重完成: {original_count} -> {deduplicated_count} 条记录")

                # 确保cow_id为字符串类型
                if 'cow_id' in final_df.columns:
                    final_df['cow_id'] = final_df['cow_id'].astype(str)

                # 保存最终结果
                final_df.to_excel(final_output, index=False)
                print(f"已保存最终汇总结果到: {final_output}")
                if progress_callback:
                    progress_callback(95, f"多文件合并完成，保存至: {final_output.name}")
        else:
            # 如果存在旧的汇总文件，需要将新处理的文件与之合并
            if progress_callback:
                progress_callback(78, "发现现有汇总文件，开始增量合并...")
            
            final_df = pd.read_excel(final_output)
            
            if progress_callback:
                progress_callback(80, f"读取现有汇总文件: {len(final_df)} 条记录")

            # 确保旧的汇总文件列名无重复且符合标准
            final_df = final_df.loc[:, ~final_df.columns.duplicated()]
            # 可以进一步验证列名是否唯一，避免潜在问题
            if final_df.columns.duplicated().any():
                raise ValueError("现有汇总文件中存在重复列名。请检查并清理汇总文件。")

            # 读取并合并新处理的文件
            for i, temp_file in enumerate(processed_files, 1):
                temp_df = pd.read_excel(temp_file)
                # 确保 temp_df 的列名与 final_df 一致
                if not set(STANDARD_GENOMIC_COLUMNS + ['cow_id', 'Results_Last_Updated']).issubset(temp_df.columns):
                    raise ValueError(f"处理文件 {temp_file.name} 缺少必要的标准列。")
                final_df = pd.concat([final_df, temp_df], ignore_index=True)
                
                if progress_callback:
                    progress_callback(int(80 + i * (8 / len(processed_files))), f"合并第 {i} 个新文件: {len(temp_df)} 条记录")

            # 根据 cow_id 和 Results_Last_Updated 去重
            final_df['Results_Last_Updated'] = pd.to_datetime(final_df['Results_Last_Updated'])
            final_df = final_df.sort_values('Results_Last_Updated', ascending=False)
            original_count = len(final_df)
            final_df = final_df.drop_duplicates(subset='cow_id', keep='first')
            deduplicated_count = len(final_df)

            if progress_callback:
                progress_callback(92, f"增量合并去重: {original_count} -> {deduplicated_count} 条记录")

            # 保存最终结果
            final_df.to_excel(final_output, index=False)
            print(f"已保存最终汇总结果到: {final_output}")
            if progress_callback:
                progress_callback(95, f"增量合并完成，保存至: {final_output.name}")

        # 更新进度：处理完成
        if progress_callback:
            progress_callback(100, f"基因组数据处理全部完成！最终文件: {final_output.name}")

        return final_output

    except Exception as e:
        error_msg = f"合并处理结果时发生错误: {e}"
        if progress_callback:
            progress_callback(75, f"错误: {error_msg}")
        raise ValueError(error_msg)
