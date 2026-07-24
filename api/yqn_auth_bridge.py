"""伊起牛登录令牌核验。

服务端使用伊起牛 ``getInfo`` 接口核验访问令牌，并从可信响应中取得工号。
不得记录访问令牌或伊起牛返回的完整用户资料。
"""

from __future__ import annotations

import os
from typing import Optional

import requests


class YQNAuthError(RuntimeError):
    """伊起牛登录令牌无效或上游认证服务不可用。"""


def verify_yqn_access_token(
    access_token: str,
    base_url: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> str:
    """向伊起牛核验访问令牌并返回登录工号。"""
    normalized_token = str(access_token or "").strip()
    if not normalized_token:
        raise YQNAuthError("伊起牛登录令牌为空")

    api_base_url = (
        base_url
        or os.getenv("YQN_API_BASE_URL")
        or "https://yqnapi.yqndairy.com"
    ).rstrip("/")
    http = session or requests.Session()
    http.trust_env = False
    http.proxies = {"http": None, "https": None}

    try:
        response = http.get(
            f"{api_base_url}/system/user/getInfo",
            headers={
                "Authorization": f"Bearer {normalized_token}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise YQNAuthError("伊起牛登录令牌核验失败") from exc

    if not isinstance(payload, dict) or payload.get("code") not in (0, 200):
        raise YQNAuthError("伊起牛登录令牌无效")

    user = payload.get("user")
    if not isinstance(user, dict):
        raise YQNAuthError("伊起牛用户信息格式异常")

    username = str(user.get("userName") or "").strip()
    if not username:
        raise YQNAuthError("伊起牛用户信息缺少工号")
    return username
