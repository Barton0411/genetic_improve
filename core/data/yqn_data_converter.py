"""
伊起牛数据转换器

将伊起牛API返回的JSON数据转换为标准Excel格式，供后续标准化处理使用。
"""
import pandas as pd
from pathlib import Path
from typing import Dict, List
import logging


class YQNDataConverter:
    """伊起牛数据转换器 - 将API数据转换为标准Excel格式"""

    # 字段映射: API字段名 → 标准字段名
    # 支持多个别名应对API字段变化
    FIELD_MAPPING = {
        # 基础信息
        "earNum": "耳号",
        "cowUniqid": "唯一牛号",
        "cowNum": "旧牛号",
        "electronicEartag": "电子耳标",

        # 系谱信息
        "fatherNum": "父亲号",
        "motherNum": "母亲号",
        "motherCowUniqid": "唯一母亲号",
        "grandFather": "祖父",
        "grandPa": "外祖父",
        "grandMother": "祖母",
        "grandMa": "外祖母",

        # 繁殖信息
        "lactation": "胎次",
        "fertilityStatus": "繁殖状态",
        "repro_status": "繁殖状态",  # 新增：另一种繁殖状态字段名
        "reproStatus": "繁殖状态",  # 新增：驼峰命名版本
        "inseminationTimes": "配种次数",
        "frozenSpermNum": "冻精编号",
        "embryoNum": "胚胎编号",
        "insemType": "配种类型",

        # 日期信息
        "birthday": "出生日期",
        "birth_date": "出生日期",  # 新增：下划线命名版本
        "birthDate": "出生日期",  # 新增：驼峰命名版本
        "recentCalvingDate": "最近产犊日期",
        "firstCalvingDate": "首次产犊日期",
        "recentInsemDate": "最近配种日期",
        "recentEstrusDate": "最近发情日期",
        "recentExaminationDate": "最近妊检日期",
        "recentDryDate": "最近干奶日期",
        "entryDate": "入场日期",

        # 天数信息
        "dayAge": "日龄",
        "monthAge": "月龄",
        "calvingDays": "产后天数",
        "milkDays": "泌乳天数",
        "pregnancyDays": "在胎天数",
        "insemDays": "配后天数",
        "dryDays": "干奶天数",

        # 健康和位置
        "cowHealthStatus": "健康状态",
        "penName": "牛舍名称",
        "penCode": "牛舍编号",
        "milkStatus": "泌乳状态",

        # 离场信息
        "exitDate": "离场日期",
        "exitType": "离场类型",

        # 其他
        "sex": "性别",
        "cultivar": "品种",
        "purpose": "用途",
        "living": "是否在场",
        "farmCode": "牧场编号",
        "isCore": "是否核心牛",
        "coreDate": "核心牛标识日期",
    }

    @staticmethod
    def convert_herd_to_excel(api_data: dict, output_path: Path) -> Path:
        """
        将API牛群数据转换为Excel文件

        参数:
            api_data: API返回的原始数据
            output_path: 输出Excel文件路径

        返回:
            Excel文件路径

        异常:
            ValueError: 数据为空或格式错误
        """
        logger = logging.getLogger(__name__)

        # 提取数据记录
        records = api_data.get("data", [])
        if not records:
            raise ValueError("API返回的牛群数据为空")

        logger.info(f"开始转换 {len(records)} 条牛只数据")

        # 转换为DataFrame
        df = pd.DataFrame(records)
        logger.info(f"原始数据列: {df.columns.tolist()}")

        # 检查关键字段是否存在
        key_fields_to_check = ['birthday', 'birth_date', 'birthDate',
                                'fertilityStatus', 'repro_status', 'reproStatus',
                                'living']
        found_fields = [f for f in key_fields_to_check if f in df.columns]
        missing_fields = [f for f in key_fields_to_check if f not in df.columns]
        logger.info(f"找到的关键字段: {found_fields}")
        if missing_fields:
            logger.warning(f"缺失的关键字段: {missing_fields}")

        # 打印第一条记录作为样本（脱敏处理）
        if len(records) > 0:
            sample = records[0]
            logger.info(f"第一条记录的字段: {list(sample.keys())}")
            # 记录出生日期相关字段的值
            birth_fields = {k: sample.get(k) for k in ['birthday', 'birth_date', 'birthDate'] if k in sample}
            if birth_fields:
                logger.info(f"出生日期字段值示例: {birth_fields}")
            # 记录繁殖状态相关字段的值
            repro_fields = {k: sample.get(k) for k in ['fertilityStatus', 'repro_status', 'reproStatus'] if k in sample}
            if repro_fields:
                logger.info(f"繁殖状态字段值示例: {repro_fields}")

        # 字段映射和重命名
        df_renamed = YQNDataConverter._rename_columns(df)
        logger.info(f"映射后数据列: {df_renamed.columns.tolist()}")

        # 数据清洗
        df_cleaned = YQNDataConverter._clean_data(df_renamed)

        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存为Excel
        df_cleaned.to_excel(output_path, index=False)

        logger.info(f"数据已保存到: {output_path}")
        logger.info(f"最终行数: {len(df_cleaned)}, 列数: {len(df_cleaned.columns)}")

        return output_path

    @staticmethod
    def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
        """
        重命名列，使用字段映射表

        参数:
            df: 原始DataFrame

        返回:
            重命名后的DataFrame
        """
        logger = logging.getLogger(__name__)
        rename_map = {}

        for api_field, std_field in YQNDataConverter.FIELD_MAPPING.items():
            if api_field in df.columns:
                rename_map[api_field] = std_field

        if rename_map:
            logger.info(f"字段映射: {rename_map}")
            df_renamed = df.rename(columns=rename_map)
        else:
            logger.warning("未找到任何匹配的字段，保留原始列名")
            df_renamed = df.copy()

        return df_renamed

    @staticmethod
    def _clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        数据清洗和格式化

        参数:
            df: DataFrame

        返回:
            清洗后的DataFrame
        """
        logger = logging.getLogger(__name__)

        # 1. 确保ID字段为字符串类型
        id_columns = [
            "耳号", "唯一牛号", "旧牛号", "电子耳标",
            "父亲号", "母亲号", "唯一母亲号",
            "祖父", "外祖父", "祖母", "外祖母",
            "冻精编号", "胚胎编号"
        ]

        for col in id_columns:
            if col in df.columns:
                # 转为字符串
                df[col] = df[col].astype(str)
                # 去除首尾空格
                df[col] = df[col].str.strip()
                # 将 'nan', 'None', 'null' 转为空字符串
                df[col] = df[col].replace(['nan', 'None', 'null'], '')
                # 空字符串保持为空
                df.loc[df[col] == '', col] = ''

        # 2. 日期格式标准化
        date_columns = [
            "出生日期", "最近产犊日期", "首次产犊日期",
            "最近配种日期", "最近发情日期", "最近妊检日期",
            "最近干奶日期", "入场日期"
        ]

        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        # 3. 移除耳号为空的行
        if "耳号" in df.columns:
            initial_count = len(df)
            df = df[df["耳号"].notna() & (df["耳号"] != "")]
            removed_count = initial_count - len(df)
            if removed_count > 0:
                logger.warning(f"移除了 {removed_count} 条耳号为空的记录")

        # 4. 数值字段转换
        numeric_columns = [
            "胎次", "配种次数", "日龄", "产后天数",
            "泌乳天数", "在胎天数", "配后天数", "干奶天数"
        ]

        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

        # 5. 月龄保留小数
        if "月龄" in df.columns:
            df["月龄"] = pd.to_numeric(df["月龄"], errors='coerce').fillna(0.0)

        # 6. 布尔值转换为中文
        if "是否在场" in df.columns:
            # 将布尔值、字符串 'true'/'false'、1/0 等统一转换为 '是'/'否'
            def convert_to_chinese(val):
                if pd.isna(val) or val == '' or val is None:
                    return ''
                val_str = str(val).lower().strip()
                if val_str in ['true', '1', 'yes', 'y', '是']:
                    return '是'
                elif val_str in ['false', '0', 'no', 'n', '否']:
                    return '否'
                else:
                    return ''

            df["是否在场"] = df["是否在场"].apply(convert_to_chinese)
            logger.info(f"已将'是否在场'字段转换为中文: {df['是否在场'].value_counts().to_dict()}")

        return df

    @staticmethod
    def preview_data(api_data: dict, limit: int = 20) -> pd.DataFrame:
        """
        生成数据预览（前N条）

        参数:
            api_data: API返回的原始数据
            limit: 预览行数，默认20

        返回:
            预览数据的DataFrame
        """
        logger = logging.getLogger(__name__)

        records = api_data.get("data", [])
        if not records:
            logger.warning("API返回的数据为空")
            return pd.DataFrame()

        # 取前N条
        preview_records = records[:limit]
        logger.info(f"生成预览数据，前 {len(preview_records)} 条")

        # 转换和清洗
        df = pd.DataFrame(preview_records)
        df_renamed = YQNDataConverter._rename_columns(df)
        df_cleaned = YQNDataConverter._clean_data(df_renamed)

        return df_cleaned
