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
