"""
品种常量定义

用于在各类统计分析中区分奶牛品种与肉牛品种。
系谱完整性等"仅针对奶牛"的统计需要据此过滤掉肉牛个体。

维护者：王波臻/Barton
"""

# 奶牛品种白名单（仅这些品种计入奶牛统计）
# 采用白名单方式：新出现的肉牛品种（如西门塔尔、安格斯、和牛等）会自动被排除。
# 若牧场引入了新的奶牛品种，需在此处补充其确切写法。
DAIRY_BREEDS = frozenset({
    "荷斯坦",
    "娟姗",
    "娟珊",   # 娟姗的常见异写
    "瑞士褐",
    "更赛",
    "爱尔夏",
})


def is_dairy_breed(breed: object) -> bool:
    """
    判断给定品种是否为奶牛品种。

    Args:
        breed: 品种值（可能为 None / NaN / 字符串，含前后空格）

    Returns:
        是否属于奶牛品种白名单。空值按奶牛处理（默认荷斯坦，与数据标准化默认值一致）。
    """
    if breed is None:
        return True
    text = str(breed).strip()
    if text == "" or text.lower() == "nan":
        return True
    return text in DAIRY_BREEDS


def filter_dairy_cows(df, breed_col: str = "breed", sex_col: str = "sex",
                      exclude_male: bool = True, log_prefix: str = ""):
    """
    筛选出用于育种分析的母牛：排除公牛、排除肉牛品种（西门塔尔、安格斯等）。

    用于各类育种分析（性状/指数/系谱/近交/选配），确保只统计奶牛母牛。
    注意：不要用于牧场存栏/在群头数等需要全量牛只的基础统计。

    Args:
        df: 母牛数据 DataFrame
        breed_col: 品种列名，默认 'breed'
        sex_col: 性别列名，默认 'sex'
        exclude_male: 是否排除公牛，默认 True
        log_prefix: 日志前缀（便于定位是哪个分析做的过滤）

    Returns:
        仅含奶牛母牛的新 DataFrame（副本）。缺列时跳过对应过滤并告警。
    """
    import logging

    logger = logging.getLogger(__name__)
    if df is None:
        return df

    result = df

    # 1) 排除公牛（性别空值按母牛处理，与数据标准化默认值一致）
    if exclude_male:
        if sex_col in result.columns:
            before = len(result)
            sex_norm = result[sex_col].fillna('母').astype(str).str.strip()
            result = result[sex_norm != '公'].copy()
            excluded_male = before - len(result)
            if excluded_male > 0:
                logger.info(f"{log_prefix}已排除公牛 {excluded_male} 头（分析仅统计母牛）")
        else:
            logger.warning(f"{log_prefix}数据缺少 {sex_col} 列，无法排除公牛")

    # 2) 排除肉牛品种
    if breed_col in result.columns:
        before = len(result)
        result = result[result[breed_col].apply(is_dairy_breed)].copy()
        excluded = before - len(result)
        if excluded > 0:
            logger.info(f"{log_prefix}已排除非奶牛品种 {excluded} 头（分析仅统计奶牛）")
    else:
        logger.warning(f"{log_prefix}数据缺少 {breed_col} 列，无法按品种过滤，结果可能包含肉牛")

    return result
