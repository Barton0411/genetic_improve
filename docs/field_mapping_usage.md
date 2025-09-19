# 字段映射工具使用说明

## 概述

字段映射工具用于解决系统中字段名不统一的问题，支持多对一映射和中英文显示转换。

## 核心功能

### 1. 字段标准化
将各种不同格式的字段名转换为标准英文字段名：
- `ID`, `Cow_ID`, `牛号` → `cow_id`
- `Birth_Date`, `出生日期` → `birth_date`
- `LAC`, `胎次` → `lac`

### 2. 中文显示转换
将标准英文字段名转换为中文显示名：
- `cow_id` → `牛号`
- `birth_date` → `出生日期`
- `lac` → `胎次`

## 使用方法

### 基础使用
```python
from utils.field_mapper import get_field_mapper

# 获取字段映射管理器
mapper = get_field_mapper()

# 标准化字段名
standard_field = mapper.normalize_field("ID")  # 返回 "cow_id"

# 获取中文显示名
display_name = mapper.get_display_name("cow_id")  # 返回 "牛号"

# 标准化数据字典
raw_data = {"ID": "CN001234", "Birth_Date": "2020-01-01"}
normalized = mapper.normalize_data(raw_data)
# 返回: {"cow_id": "CN001234", "birth_date": "2020-01-01"}

# 转换为中文显示
display_data = mapper.get_display_data(normalized)
# 返回: {"牛号": "CN001234", "出生日期": "2020-01-01"}
```

### 便捷函数
```python
from utils.field_mapper import normalize_field, get_display_name, normalize_data

# 直接使用便捷函数
standard = normalize_field("牛号")  # 返回 "cow_id"
display = get_display_name("cow_id")  # 返回 "牛号"
```

## 配置文件

字段映射关系存储在 `config/field_mappings.json` 中，您可以随时编辑此文件来添加或修改映射关系。

### 添加新的映射
在 `config/field_mappings.json` 的 `normalize_mappings` 部分添加：
```json
{
  "new_field": ["variant1", "variant2", "变体名称"]
}
```

在 `display_mappings` 部分添加中文显示名：
```json
{
  "new_field": "新字段"
}
```

## 当前支持的字段映射

### 牛只基础信息
- `cow_id`: 牛号、牛只编号、ID等 → "牛号"
- `birth_date`: 出生日期相关 → "出生日期"
- `lac`: 胎次相关 → "胎次"
- `sex`: 性别相关 → "性别"
- `sire_id`: 父亲相关 → "父号"
- `dam_id`: 母亲相关 → "母号"
- `naab`: 公牛号相关 → "公牛号"

### 生产数据
- `milk_yield`: 产奶量相关 → "产奶量"
- `fat_percentage`: 乳脂率相关 → "乳脂率"
- `protein_percentage`: 乳蛋白率相关 → "乳蛋白率"

### 其他
- `farm_code`: 牧场代码相关 → "牧场代码"
- `employee_id`: 工号相关 → "工号"

## 注意事项

1. **字段映射只能由您来定义**，工具不会自动判断映射关系
2. 映射查找忽略大小写
3. 如果找不到映射，会返回原始字段名
4. 修改配置文件后会立即生效，无需重启应用
5. 支持多个原始字段映射到同一个标准字段