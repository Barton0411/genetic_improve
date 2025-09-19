"""
字段映射管理工具
用于处理多对1字段映射和中英文显示转换
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List

class FieldMappingManager:
    """字段映射管理器"""

    def __init__(self, config_file: Optional[str] = None):
        """
        初始化字段映射管理器

        Args:
            config_file: 映射配置文件路径，如果不提供则尝试使用项目配置文件
        """
        # 默认配置文件路径
        if config_file is None:
            project_root = Path(__file__).parent.parent
            config_file = project_root / "config" / "field_mappings.json"

        if config_file and Path(config_file).exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.normalize_mapping = config.get('normalize_mappings', {})
                self.display_mapping = config.get('display_mappings', {})
        else:
            # 默认映射配置 - 使用用户提供的标准映射
            self.normalize_mapping = {
                # 牛只基础信息
                "cow_id": ["cow_id", "ID", "Cow_ID", "CowID", "牛号", "牛只编号",
                          "animal_id", "cattle_id", "耳号", "个体号"],

                "birth_date": ["birth_date", "Birth_Date", "BirthDate", "出生日期",
                              "birth_dt", "birthday"],

                "lac": ["lac", "LAC", "Lactation", "胎次", "lactation"],

                "sex": ["sex", "Sex", "Gender", "性别"],

                "sire_id": ["sire_id", "Sire_ID", "SireID", "父号", "sire", "父亲ID"],

                "dam_id": ["dam_id", "Dam_ID", "DamID", "母号", "dam", "母亲ID"],

                "naab": ["NAAB", "Bull_NAAB", "BullNAAB", "公牛号", "bull_id", "Bull_ID",
                        "bull_cattle_id", "种公牛"],

                # 牧场相关
                "farm_code": ["farm_code", "farm_id", "站号", "牧场编号",
                             "result_farm_code", "牧场代码"],

                # 日期相关
                "mating_date": ["mating_date", "配种日期", "选配日期"],

                # 产奶性能
                "milk_yield": ["milk_yield", "产奶量", "日产奶量", "milk_production"],
                "fat_percentage": ["fat_percentage", "乳脂率", "fat_rate", "脂肪率"],
                "protein_percentage": ["protein_percentage", "乳蛋白率", "protein_rate", "蛋白率"],

                # 用户相关
                "employee_id": ["employee_id", "user_id", "工号", "username"],
                "password": ["password", "密码", "PW", "pwd"],

                # 选配相关
                "mating_result_id": ["mating_result_id", "result_id", "match_id", "选配结果"],

                # 其他
                "name": ["name", "姓名", "名称", "cattle_name", "bull_name"]
            }

            self.display_mapping = {
                # 牛只基础信息
                "cow_id": "牛号",
                "birth_date": "出生日期",
                "lac": "胎次",
                "sex": "性别",
                "sire_id": "父号",
                "dam_id": "母号",
                "naab": "公牛号",

                # 牛只其他信息
                "cattle_name": "牛只名称",

                # 牧场相关
                "farm_code": "牧场代码",
                "farm_name": "牧场名称",

                # 日期相关
                "mating_date": "选配日期",

                # 产奶性能
                "milk_yield": "产奶量",
                "fat_percentage": "乳脂率",
                "protein_percentage": "乳蛋白率",

                # 用户相关
                "employee_id": "工号",
                "password": "密码",
                "name": "姓名",

                # 选配相关
                "mating_result_id": "选配结果编号",
                "inbreeding_coefficient": "近交系数",

                # 其他常用字段
                "status": "状态",
                "created_at": "创建时间",
                "updated_at": "更新时间"
            }

        # 构建反向索引（加速查找）
        self.reverse_index = {}
        self._build_reverse_index()

    def _build_reverse_index(self):
        """构建反向查找索引，将所有变体映射到标准字段"""
        for standard_field, variants in self.normalize_mapping.items():
            for variant in variants:
                # 转换为小写进行匹配（忽略大小写）
                self.reverse_index[variant.lower()] = standard_field

    def normalize_field(self, field_name: str) -> str:
        """
        将任意字段名转换为标准字段名

        Args:
            field_name: 原始字段名

        Returns:
            标准字段名，如果没有找到映射则返回原始字段名
        """
        if not field_name:
            return field_name

        # 忽略大小写查找
        standard_field = self.reverse_index.get(field_name.lower(), field_name)
        return standard_field

    def get_display_name(self, field_name: str) -> str:
        """
        获取字段的中文显示名

        Args:
            field_name: 字段名（可以是原始字段名或标准字段名）

        Returns:
            中文显示名，如果没有找到则返回原字段名
        """
        # 先标准化字段名
        standard_field = self.normalize_field(field_name)
        # 获取中文显示名
        return self.display_mapping.get(standard_field, standard_field)

    def normalize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        标准化数据字典的字段名

        Args:
            data: 包含原始字段名的数据字典

        Returns:
            字段名已标准化的数据字典
        """
        if not data:
            return data

        result = {}
        for field_name, value in data.items():
            standard_field = self.normalize_field(field_name)
            # 如果已存在相同的标准字段，保留非空值
            if standard_field in result:
                if value and not result[standard_field]:
                    result[standard_field] = value
            else:
                result[standard_field] = value

        return result

    def get_display_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        将数据字典转换为中文显示格式

        Args:
            data: 包含英文字段名的数据字典

        Returns:
            使用中文字段名的数据字典
        """
        if not data:
            return data

        result = {}
        for field_name, value in data.items():
            display_name = self.get_display_name(field_name)
            result[display_name] = value

        return result

    def normalize_dataframe_columns(self, columns: List[str]) -> List[str]:
        """
        标准化DataFrame的列名

        Args:
            columns: 原始列名列表

        Returns:
            标准化后的列名列表
        """
        return [self.normalize_field(col) for col in columns]

    def get_display_columns(self, columns: List[str]) -> List[str]:
        """
        获取DataFrame列的中文显示名

        Args:
            columns: 英文列名列表

        Returns:
            中文列名列表
        """
        return [self.get_display_name(col) for col in columns]

    def save_config(self, config_file: str):
        """
        保存映射配置到文件

        Args:
            config_file: 配置文件路径
        """
        config = {
            "normalize_mappings": self.normalize_mapping,
            "display_mappings": self.display_mapping
        }

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)


# 单例模式，全局共享映射管理器
_global_mapper = None

def get_field_mapper() -> FieldMappingManager:
    """获取全局字段映射管理器实例"""
    global _global_mapper
    if _global_mapper is None:
        _global_mapper = FieldMappingManager()
    return _global_mapper


# 便捷函数
def normalize_field(field_name: str) -> str:
    """标准化字段名的便捷函数"""
    return get_field_mapper().normalize_field(field_name)


def get_display_name(field_name: str) -> str:
    """获取中文显示名的便捷函数"""
    return get_field_mapper().get_display_name(field_name)


def normalize_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """标准化数据字典的便捷函数"""
    return get_field_mapper().normalize_data(data)


if __name__ == "__main__":
    # 测试代码
    mapper = FieldMappingManager()

    # 测试字段标准化 - 使用用户提供的映射
    print("字段标准化测试:")
    test_fields = [
        "cow_id", "ID", "Cow_ID", "牛号",  # 应该都映射到 cow_id
        "birth_date", "Birth_Date", "出生日期",  # 应该都映射到 birth_date
        "lac", "LAC", "胎次",  # 应该都映射到 lac
        "NAAB", "Bull_NAAB", "公牛号",  # 应该都映射到 naab
        "sire_id", "父号",  # 应该都映射到 sire_id
        "dam_id", "母号"  # 应该都映射到 dam_id
    ]
    for field in test_fields:
        standard = mapper.normalize_field(field)
        display = mapper.get_display_name(field)
        print(f"  {field:15} → {standard:15} → {display}")

    # 测试数据标准化 - 使用实际可能出现的字段名
    print("\n数据标准化测试:")
    raw_data = {
        "ID": "CN001234",  # 应该映射到 cow_id
        "Birth_Date": "2020-01-01",  # 应该映射到 birth_date
        "LAC": 3,  # 应该映射到 lac
        "Sex": "F",  # 应该映射到 sex
        "父号": "US001234",  # 应该映射到 sire_id
        "母号": "CN005678",  # 应该映射到 dam_id
        "Bull_NAAB": "7HO12345",  # 应该映射到 naab
        "牧场编号": "YILI001",  # 应该映射到 farm_code
        "产奶量": 8500  # 应该映射到 milk_yield
    }

    normalized = mapper.normalize_data(raw_data)
    print(f"  原始数据: {raw_data}")
    print(f"  标准化后: {normalized}")

    # 测试中文显示
    display = mapper.get_display_data(normalized)
    print(f"  中文显示: {display}")