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
    print("[DEBUG-1] 开始预处理母牛数据，行数:", len(cow_df))
    try:
        # 替换表头中的中文列名为英文列名
        print("[DEBUG-2] 开始转换列名...")
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
        print("[DEBUG-3] 原始列名:", cow_df.columns.tolist())
        cow_df.rename(columns=column_mapping, inplace=True)
        print("[DEBUG-4] 转换后列名:", cow_df.columns.tolist())

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


def process_cow_data_file(input_file: Path, project_path: Path, progress_callback=None) -> Path:
    """
    标准化母牛数据文件
    """
    import logging
    print("[DEBUG-FILE-1] 开始标准化母牛数据文件:", input_file)
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
        print("[DEBUG-FILE-3] 开始读取母牛数据文件...")
        logging.info("开始读取母牛数据文件...")
        # 使用原始列名来指定dtype，确保前导零不会丢失
        df = pd.read_excel(input_file, dtype={
            '耳号': str,
            '父亲号': str,
            '母亲号': str,
            '外祖父': str,
            '外曾外祖父': str,
            '祖父': str,
            '与配冻精编号': str
        })
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
        df_cleaned = preprocess_cow_data(df, progress_callback)
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
    print(f"[DEBUG-BREEDING-1] 开始处理配种记录文件: {input_file}")
    
    # 将标准化后的文件存储到 standardized_data 文件夹
    standardized_path = project_path / "standardized_data"
    standardized_path.mkdir(parents=True, exist_ok=True)
    print(f"[DEBUG-BREEDING-2] 标准化路径: {standardized_path}")
    
    # 读取文件，根据文件类型选择读取方法
    try:
        print(f"[DEBUG-BREEDING-3] 尝试读取配种记录文件: {input_file}")
        if input_file.suffix.lower() == '.csv':
            df = pd.read_csv(input_file)
        else:
            df = pd.read_excel(input_file)
        print(f"[DEBUG-BREEDING-4] 成功读取配种记录文件，形状: {df.shape}")
    except Exception as e:
        error_msg = f"读取配种记录数据文件失败: {e}"
        print(f"[DEBUG-BREEDING-ERROR] {error_msg}")
        raise ValueError(error_msg)

    # 打印当前文件的列名，帮助调试
    print(f"[DEBUG-BREEDING-COLUMNS] 文件包含的列: {list(df.columns)}")
    
    # 列名映射，处理可能的列名变化
    column_mappings = {
        '耳号': ['耳号', '牛号', '母牛号', '母牛耳号', 'cow_id', 'ID', 'id'],
        '配种日期': ['配种日期', '配种时间', '授精日期', '授精时间', 'breed_date', 'breeding_date'],
        '冻精编号': ['冻精编号', '冻精号', '公牛号', '精液号', 'semen_id', 'bull_id'],
        '冻精类型': ['冻精类型', '精液类型', '类型', 'semen_type', 'type']
    }
    
    # 尝试映射列名
    for target_col, possible_names in column_mappings.items():
        if target_col not in df.columns:
            for possible_name in possible_names:
                if possible_name in df.columns:
                    print(f"[DEBUG-BREEDING-MAPPING] 映射列名: {possible_name} -> {target_col}")
                    df.rename(columns={possible_name: target_col}, inplace=True)
                    break
    
    # 数据标准化逻辑（根据用户提供的必需列进行处理）
    required_columns = ['耳号', '配种日期', '冻精编号', '冻精类型']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        error_msg = f"配种记录数据缺少以下必需列: {', '.join(missing_columns)}\n当前文件包含的列: {', '.join(df.columns)}"
        print(f"[DEBUG-BREEDING-ERROR] {error_msg}")
        raise ValueError(error_msg)

    # 删除缺失值
    print(f"[DEBUG-BREEDING-5] 删除缺失值前记录数: {len(df)}")
    df_cleaned = df.dropna(subset=required_columns)
    print(f"[DEBUG-BREEDING-6] 删除缺失值后记录数: {len(df_cleaned)}")

    # 处理 '冻精编号' 使用 format_naab_number
    def apply_format_naab_number(x):
        try:
            # 防止空值或None
            if pd.isna(x) or not x:
                return ''
                
            formatted_id, errors = format_naab_number(str(x))
            if errors:
                # 如果有错误，返回空字符串
                print(f"[DEBUG-BREEDING-WARNING] 冻精编号格式错误: {x}, 错误: {errors}")
                return ''
            return formatted_id
        except Exception as e:
            print(f"[DEBUG-BREEDING-ERROR] 处理冻精编号时出错: {x}, 错误: {e}")
            return ''

    # 安全地处理每行数据
    total = df_cleaned.shape[0]
    try:
        print(f"[DEBUG-BREEDING-7] 开始处理冻精编号，总行数: {total}")
        for idx, row in df_cleaned.iterrows():
            try:
                df_cleaned.at[idx, '冻精编号'] = apply_format_naab_number(row['冻精编号'])
                
                # 只在特定间隔更新进度，减少回调频率
                if progress_callback and idx % max(1, total // 10) == 0:
                    progress = int((idx + 1) / total * 100)
                    print(f"[DEBUG-BREEDING-8] 进度更新: {progress}%")
                    progress_callback(progress)
            except Exception as e:
                print(f"[DEBUG-BREEDING-ERROR] 处理第 {idx} 行时出错: {e}")
                # 继续处理下一行
                continue
    except Exception as e:
        print(f"[DEBUG-BREEDING-ERROR] 处理冻精编号过程中出错: {e}")
        # 继续执行，不抛出异常

    # 处理 '配种日期' 转换为日期格式
    try:
        print(f"[DEBUG-BREEDING-9] 处理配种日期")
        df_cleaned['配种日期'] = pd.to_datetime(df_cleaned['配种日期'], errors='coerce')
    except Exception as e:
        print(f"[DEBUG-BREEDING-ERROR] 处理配种日期时出错: {e}")
        # 继续执行

    # 填充 NaN 为 ''
    try:
        print(f"[DEBUG-BREEDING-10] 填充空值")
        df_cleaned.fillna('', inplace=True)
    except Exception as e:
        print(f"[DEBUG-BREEDING-ERROR] 填充空值时出错: {e}")
        # 继续执行

    # 添加父号列
    try:
        print(f"[DEBUG-BREEDING-11] 处理父号列")
        # 检查cow_df是否有效
        if cow_df is not None and not cow_df.empty:
            # 确保 'cow_id' 和 'sire' 列存在
            if 'cow_id' in cow_df.columns and 'sire' in cow_df.columns:
                try:
                    print(f"[DEBUG-BREEDING-12] 创建父号映射字典，母牛数据形状: {cow_df.shape}")
                    # 确保cow_id列为字符串类型
                    cow_df['cow_id'] = cow_df['cow_id'].astype(str)
                    # 创建映射字典: cow_id -> sire
                    sire_dict = dict(zip(cow_df['cow_id'], cow_df['sire']))
                    print(f"[DEBUG-BREEDING-13] 创建了 {len(sire_dict)} 个映射项")
                    
                    # 确保配种记录的耳号列为字符串类型
                    df_cleaned['耳号'] = df_cleaned['耳号'].astype(str)
                    print(f"[DEBUG-BREEDING-14] 开始映射父号...")
                    
                    # 检查映射前的样本数据
                    sample_ear_tags = df_cleaned['耳号'].head(5).tolist()
                    print(f"[DEBUG-BREEDING-15] 样本耳号: {sample_ear_tags}")
                    sample_matches = [sire_dict.get(tag, '未匹配') for tag in sample_ear_tags]
                    print(f"[DEBUG-BREEDING-16] 样本映射结果: {sample_matches}")
                    
                    # 添加父号列
                    df_cleaned['父号'] = df_cleaned['耳号'].map(sire_dict).fillna('')
                    
                    # 检查映射效果
                    matched_count = (df_cleaned['父号'] != '').sum()
                    print(f"[DEBUG-BREEDING-17] 父号映射完成，成功匹配 {matched_count}/{len(df_cleaned)} 条记录")
                except Exception as e:
                    print(f"[DEBUG-BREEDING-ERROR] 映射父号时出错: {e}")
                    import traceback
                    print(traceback.format_exc())
                    df_cleaned['父号'] = ''  # 出错时设置为空字符串
            else:
                print(f"[DEBUG-BREEDING-WARNING] 母牛数据中缺少必要的列: cow_id或sire")
                df_cleaned['父号'] = ''
        else:
            # 如果没有提供有效的cow_df，添加空的父号列
            print(f"[DEBUG-BREEDING-WARNING] 未提供有效的母牛数据")
            df_cleaned['父号'] = ''
    except Exception as e:
        print(f"[DEBUG-BREEDING-ERROR] 处理父号时出错: {e}")
        import traceback
        print(traceback.format_exc())
        df_cleaned['父号'] = ''  # 确保父号列存在

    # 重新排列列的顺序
    try:
        print(f"[DEBUG-BREEDING-18] 重新排列列顺序")
        columns_to_keep = ['耳号', '父号', '冻精编号', '配种日期', '冻精类型']
        # 确保所有必要的列都存在
        for col in columns_to_keep:
            if col not in df_cleaned.columns:
                df_cleaned[col] = ''
                
        df_cleaned = df_cleaned[columns_to_keep]
    except Exception as e:
        print(f"[DEBUG-BREEDING-ERROR] 重新排列列时出错: {e}")
        # 继续执行，不抛出异常

    # 保存标准化后的文件
    output_file = standardized_path / "processed_breeding_data.xlsx"
    try:
        print(f"[DEBUG-BREEDING-19] 保存处理后的文件: {output_file}")
        df_cleaned.to_excel(output_file, index=False)
        print(f"[DEBUG-BREEDING-20] 文件保存成功")
    except Exception as e:
        error_msg = f"保存配种记录数据文件失败: {e}"
        print(f"[DEBUG-BREEDING-ERROR] {error_msg}")
        raise ValueError(error_msg)

    print(f"[DEBUG-BREEDING-21] 配种记录处理完成，返回文件路径: {output_file}")
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
                df = pd.read_csv(input_file)
                if progress_callback:
                    progress_callback(int(file_progress + 5), f"成功读取CSV文件，数据行数: {len(df)}")
            else:
                df = pd.read_excel(input_file)
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
