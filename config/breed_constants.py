"""
品种常量定义

用于在各类统计分析中区分奶牛品种与肉牛品种。
系谱完整性等"仅针对奶牛"的统计需要据此过滤掉肉牛个体。

维护者：王波臻/Barton
"""

# 奶牛品种白名单（中文名，含常见异写/变体）。
# 采用白名单方式：新出现的肉牛品种（如西门塔尔、安格斯、和牛等）会自动被排除。
# 若牧场引入了新的奶牛品种，需在此处补充其确切写法。
DAIRY_BREEDS = frozenset({
    "荷斯坦",
    "中国荷斯坦",
    "荷斯坦牛",
    "黑白花",
    "中国黑白花",
    "娟姗",
    "娟珊",   # 娟姗的常见异写
    "瑞士褐",
    "更赛",
    "爱尔夏",
})

# 奶牛品种英文名（小写）。部分数据源用英文表示品种。
_DAIRY_BREEDS_EN = frozenset({
    "holstein",
    "jersey",
    "brown swiss",
    "brownswiss",
    "guernsey",
    "ayrshire",
})

# 奶牛品种代码白名单（如伊起牛 cultivar 字段返回的代码）。
# CC002 = 中国荷斯坦（伊起牛）。新数据源若用代码表示奶牛品种，在此补充其代码。
DAIRY_BREED_CODES = frozenset({
    "CC002",   # 中国荷斯坦（伊起牛）
})

# 奶牛品种中文关键词（用于宽松包含匹配，兼容"X牛"/"中国X"等变体写法，
# 如"娟姗牛"、"荷斯坦牛"、"中国荷斯坦"均能识别）。
_DAIRY_NAME_KEYWORDS = (
    "荷斯坦",
    "黑白花",
    "娟姗",
    "娟珊",
    "瑞士褐",
    "更赛",
    "爱尔夏",
)

# 奶牛品种英文关键词（小写，用于包含匹配）。
_DAIRY_EN_KEYWORDS = (
    "holstein",
    "jersey",
    "brown swiss",
    "brownswiss",
    "guernsey",
    "ayrshire",
)


def is_dairy_breed(breed: object) -> bool:
    """
    判断给定品种是否为奶牛品种。

    兼容多种写法：中文名（含"X牛"/"中国X"等变体）、英文名、品种代码（如伊起牛 CC002）。
    采用关键词包含匹配，例如"娟姗牛"、"荷斯坦牛"、"中国荷斯坦"均判为奶牛。
    空值按奶牛处理（默认荷斯坦，与数据标准化默认值一致）。

    Args:
        breed: 品种值（可能为 None / NaN / 字符串 / 代码，含前后空格）

    Returns:
        是否属于奶牛品种。
    """
    if breed is None:
        return True
    text = str(breed).strip()
    if text == "" or text.lower() == "nan":
        return True
    # 品种代码（大小写不敏感）
    if text.upper() in DAIRY_BREED_CODES:
        return True
    # 中文名（精确，保留向后兼容）
    if text in DAIRY_BREEDS:
        return True
    # 中文关键词包含匹配（兼容"X牛"/"中国X"等变体）
    if any(k in text for k in _DAIRY_NAME_KEYWORDS):
        return True
    # 英文名包含匹配（小写）
    low = text.lower()
    if low in _DAIRY_BREEDS_EN or any(k in low for k in _DAIRY_EN_KEYWORDS):
        return True
    return False


def filter_dairy_cows(df, breed_col: str = "breed", sex_col: str = "sex",
                      exclude_male: bool = True, log_prefix: str = ""):
    """
    筛选出用于育种分析的母牛：排除公牛、排除肉牛品种（西门塔尔、安格斯等）。

    用于各类育种分析（性状/指数/系谱/近交/选配），确保只统计奶牛母牛。
    注意：不要用于牧场存栏/在群头数等需要全量牛只的基础统计。

    安全兜底：若按品种过滤后结果为空（通常意味着该数据源的品种字段是
    未识别的代码/写法，而非真的全是肉牛），则放弃品种过滤、保留全部并告警，
    避免把整个牧场的牛误删导致后续分析（如"处理年度数据失败"）中断。

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
        filtered = result[result[breed_col].apply(is_dairy_breed)].copy()
        # 安全兜底：品种过滤把数据清空（before>0 但 filtered 为空），
        # 多半是品种字段为未识别的代码/写法，放弃品种过滤、保留全部母牛。
        if before > 0 and len(filtered) == 0:
            sample = result[breed_col].dropna().astype(str).str.strip()
            sample = list(sample.unique()[:5])
            logger.warning(
                f"{log_prefix}品种过滤后为空（共 {before} 头），疑似品种字段为未识别的"
                f"代码/写法：{sample}，已跳过品种过滤、保留全部母牛以避免分析中断。"
                f"如需精确区分肉牛，请在 config/breed_constants.py 补充该写法。"
            )
            # 保留 result（已做性别过滤），不做品种过滤
        else:
            excluded = before - len(filtered)
            result = filtered
            if excluded > 0:
                logger.info(f"{log_prefix}已排除非奶牛品种 {excluded} 头（分析仅统计奶牛）")
    else:
        logger.warning(f"{log_prefix}数据缺少 {breed_col} 列，无法按品种过滤，结果可能包含肉牛")

    return result
