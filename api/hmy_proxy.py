"""慧牧云服务端只读代理。

AES 鉴权信息仅允许存在于服务端环境变量中，不得返回给客户端或写入日志。
"""

from __future__ import annotations

import base64
import os
from datetime import date
from typing import Optional

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


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


def is_hmy_user_allowed(username: object) -> bool:
    """判断登录工号是否已开通慧牧云新功能。"""
    return str(username or "").strip() in HMY_ALLOWED_USER_IDS


class HMYProxyError(RuntimeError):
    """慧牧云代理基础异常。"""


class HMYProxyConfigError(HMYProxyError):
    """慧牧云服务端鉴权配置异常。"""


class HMYProxyUpstreamError(HMYProxyError):
    """慧牧云上游请求或响应异常。"""


class HMYProxyClient:
    """使用服务端 AES 密钥读取慧牧云牛群分页数据。"""

    def __init__(
        self,
        aes_key: Optional[str] = None,
        base_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ):
        base_url_value = base_url or os.getenv("HMY_API_BASE_URL")
        if not base_url_value:
            raise HMYProxyConfigError("慧牧云服务端地址未配置")
        self.base_url = base_url_value.rstrip("/")
        key_value = aes_key or os.getenv("HMY_API_AES_KEY")
        if not key_value:
            raise HMYProxyConfigError("慧牧云服务端鉴权未配置")

        self._key_bytes = key_value.strip().encode("utf-8")
        if len(self._key_bytes) not in (16, 24, 32):
            raise HMYProxyConfigError("慧牧云服务端鉴权配置无效")

        self.session = session or requests.Session()
        self.session.trust_env = False
        self.session.proxies = {"http": None, "https": None}

    def _make_secret(self, request_date: Optional[date] = None) -> str:
        """按慧牧云协议生成当天请求头，不记录或返回原始密钥。"""
        plain = (request_date or date.today()).isoformat().encode("utf-8")
        padder = PKCS7(128).padder()
        padded = padder.update(plain) + padder.finalize()
        cipher = Cipher(algorithms.AES(self._key_bytes), modes.ECB())
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(encrypted).decode("ascii")

    def get_cow_page(
        self,
        farm_code: str,
        page_size: int = 2000,
        page_num: int = 1,
    ) -> dict:
        """读取一页牛群数据，并在服务边界验证响应格式。"""
        normalized_farm_code = str(farm_code or "").strip()
        if not normalized_farm_code:
            raise ValueError("牧场编码不能为空")
        if not 1 <= int(page_size) <= 2000:
            raise ValueError("page_size 必须在 1 到 2000 之间")
        if int(page_num) < 1:
            raise ValueError("page_num 必须大于等于 1")

        try:
            response = self.session.get(
                f"{self.base_url}/outside/yl/cow",
                params={
                    "farmCode": normalized_farm_code,
                    "pageSize": int(page_size),
                    "pageNum": int(page_num),
                },
                headers={"secret": self._make_secret()},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise HMYProxyUpstreamError("慧牧云上游请求失败") from exc

        if not isinstance(payload, dict):
            raise HMYProxyUpstreamError("慧牧云上游返回格式异常")

        rows = payload.get("data") or []
        if not isinstance(rows, list):
            raise HMYProxyUpstreamError("慧牧云上游 data 字段格式异常")
        try:
            count = int(payload.get("count") or 0)
        except (TypeError, ValueError) as exc:
            raise HMYProxyUpstreamError("慧牧云上游 count 字段格式异常") from exc
        if count < 0:
            raise HMYProxyUpstreamError("慧牧云上游 count 字段无效")

        return {"code": payload.get("code", 200), "count": count, "data": rows}
