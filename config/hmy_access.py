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


def is_hmy_user_allowed(username) -> bool:
    """仅允许明确列入白名单的工号使用慧牧云功能。"""
    return str(username or "").strip() in HMY_ALLOWED_USER_IDS
