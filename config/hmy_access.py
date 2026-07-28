"""慧牧云功能账号白名单。"""

from __future__ import annotations


HMY_ALLOWED_USER_IDS = frozenset(
    {
        "10075345",
        "10012295",
        "10097762",
        "10049745",
        "10073346",
        "10062690",
        "10090892",
        "10073309",
        "10047020",
        "10030967",
    }
)

INTERFACE_DISABLED_USER_IDS = frozenset(
    {
        "01062799",
    }
)


def can_use_interface_data(username) -> bool:
    """判断账号是否允许使用伊起牛或慧牧云接口数据。"""
    return str(username or "").strip() not in INTERFACE_DISABLED_USER_IDS


def is_hmy_user_allowed(username) -> bool:
    """仅允许明确列入白名单的工号使用慧牧云功能。"""
    normalized_username = str(username or "").strip()
    return (
        can_use_interface_data(normalized_username)
        and normalized_username in HMY_ALLOWED_USER_IDS
    )
