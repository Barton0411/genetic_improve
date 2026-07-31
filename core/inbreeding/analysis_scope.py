"""近交分析的数据范围选择。

本模块只接收 DataFrame 和公牛号标准化函数，不读取文件、不写文件，也不依赖
Qt。自动分析和界面分析必须共同调用这里的纯函数，避免两条入口使用不同的
母牛、配种记录或备选公牛范围。
"""

from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from config.breed_constants import is_dairy_breed
from utils.large_excel_writer import normalize_identifier


STANDARDIZED_BULL_ID_COLUMN = "__inbreeding_standardized_bull_id"
ORIGINAL_BULL_ID_COLUMN = "__inbreeding_original_bull_id"


@dataclass
class InbreedingAnalysisScope:
    """一次近交分析实际使用的数据集合。"""

    cows: pd.DataFrame
    breeding_records: pd.DataFrame
    candidate_bulls: pd.DataFrame


def _clean_identifier(value) -> str:
    text = normalize_identifier(value).strip()
    if text.casefold() in {"", "nan", "none", "null", "nat"}:
        return ""
    # Excel 中纯数字标识符可能被历史文件保存成文本 ``123.0``。
    # 这里只去掉一个纯数字末尾的 ``.0``，不会把一般公牛号或带前导零
    # 的文本转成数值。
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def _select_dairy_females(cow_df: pd.DataFrame) -> pd.DataFrame:
    """严格选择标准母牛档案中的奶牛母牛，不使用“过滤为空后回退”逻辑。"""
    result = cow_df.copy(deep=True)

    if "sex" in result.columns:
        sex = result["sex"].fillna("母").astype(str).str.strip()
        result = result[sex != "公"].copy()

    if "breed" in result.columns:
        result = result[result["breed"].apply(is_dairy_breed)].copy()

    if "cow_id" not in result.columns:
        raise KeyError("标准母牛档案缺少 cow_id 列")

    normalized_ids = result["cow_id"].map(_clean_identifier)
    result = result[normalized_ids != ""].copy()
    return result


def build_inbreeding_analysis_scope(
    analysis_type: str,
    cow_df: pd.DataFrame,
    *,
    breeding_df: Optional[pd.DataFrame] = None,
    candidate_bull_df: Optional[pd.DataFrame] = None,
    standardize_bull_id: Optional[Callable[[str], str]] = None,
) -> InbreedingAnalysisScope:
    """构建自动/UI 共用的近交分析范围。

    ``candidate`` 只分析在场奶牛母牛；备选公牛在公牛号标准化后去重。
    ``mated`` 以标准母牛档案中的全部奶牛母牛 ID 为白名单筛配种记录，不再
    额外要求母牛当前在场，因此保留离场母牛的历史配种记录。

    所有输入都会深拷贝；为近交分析增加的内部列不会写回
    ``processed_bull_data.xlsx``，也不会改变个体选配使用的复合冻精库存。
    """
    if analysis_type not in {"candidate", "mated"}:
        raise ValueError(f"不支持的近交分析类型: {analysis_type}")

    dairy_cows = _select_dairy_females(cow_df)
    empty = pd.DataFrame()

    if analysis_type == "mated":
        if breeding_df is None:
            raise ValueError("已配公牛近交分析缺少配种记录")
        if "耳号" not in breeding_df.columns:
            raise KeyError("标准配种记录缺少 耳号 列")

        allowed_cow_ids = {
            _clean_identifier(value)
            for value in dairy_cows["cow_id"]
            if _clean_identifier(value)
        }
        records = breeding_df.copy(deep=True)
        record_cow_ids = records["耳号"].map(_clean_identifier)
        records = records[record_cow_ids.isin(allowed_cow_ids)].copy()
        return InbreedingAnalysisScope(
            cows=dairy_cows,
            breeding_records=records,
            candidate_bulls=empty,
        )

    if "是否在场" not in dairy_cows.columns:
        raise KeyError("标准母牛档案缺少 是否在场 列")
    in_herd = dairy_cows[
        dairy_cows["是否在场"].fillna("").astype(str).str.strip().eq("是")
    ].copy()

    if candidate_bull_df is None:
        raise ValueError("备选公牛近交分析缺少备选公牛数据")
    if "bull_id" not in candidate_bull_df.columns:
        raise KeyError("备选公牛数据缺少 bull_id 列")

    standardizer = standardize_bull_id or (lambda value: value)
    bulls = candidate_bull_df.copy(deep=True)
    bulls[ORIGINAL_BULL_ID_COLUMN] = bulls["bull_id"].map(_clean_identifier)
    bulls[STANDARDIZED_BULL_ID_COLUMN] = bulls[ORIGINAL_BULL_ID_COLUMN].map(
        lambda value: _clean_identifier(standardizer(value)) if value else ""
    )
    bulls = bulls[bulls[STANDARDIZED_BULL_ID_COLUMN] != ""].copy()
    bulls = bulls.drop_duplicates(
        subset=[STANDARDIZED_BULL_ID_COLUMN],
        keep="first",
    ).copy()

    return InbreedingAnalysisScope(
        cows=in_herd,
        breeding_records=empty,
        candidate_bulls=bulls,
    )
