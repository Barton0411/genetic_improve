"""慧牧云只读数据接口客户端。"""

from __future__ import annotations

import base64
import json
import os
import subprocess
from datetime import date
from pathlib import Path
from typing import List, Optional

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


class HMYApiClient:
    """访问慧牧云牛群接口；当前仅开放只读查询能力。"""

    DEFAULT_BASE_URL = "https://hmy.yourandairy.com:8099"
    KEYCHAIN_SERVICE = "genetic-improve-hmy-api"
    KEYCHAIN_ACCOUNT = "aes-key"

    def __init__(self, aes_key: Optional[str] = None, base_url: Optional[str] = None):
        self.base_url = (base_url or os.getenv("HMY_API_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self._aes_key = aes_key or self._load_aes_key()
        if not self._aes_key:
            raise ValueError(
                "未找到慧牧云接口鉴权信息。请设置 HMY_API_AES_KEY，"
                "或将密钥保存到 macOS 钥匙串服务 genetic-improve-hmy-api。"
            )

        key_bytes = self._aes_key.encode("utf-8")
        if len(key_bytes) not in (16, 24, 32):
            raise ValueError("慧牧云接口鉴权信息长度无效")
        self._key_bytes = key_bytes

        self.session = requests.Session()
        self.session.trust_env = False
        self.session.proxies = {"http": None, "https": None}

    @classmethod
    def _load_aes_key(cls) -> Optional[str]:
        """优先从环境变量读取，其次从 macOS 钥匙串读取。"""
        env_value = os.getenv("HMY_API_AES_KEY")
        if env_value:
            return env_value.strip()

        try:
            result = subprocess.run(
                [
                    "security",
                    "find-generic-password",
                    "-s",
                    cls.KEYCHAIN_SERVICE,
                    "-a",
                    cls.KEYCHAIN_ACCOUNT,
                    "-w",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
        return None

    def _make_secret(self) -> str:
        """根据当天日期生成请求头凭证，不记录或输出凭证内容。"""
        plain = date.today().isoformat().encode("utf-8")
        padder = PKCS7(128).padder()
        padded = padder.update(plain) + padder.finalize()
        cipher = Cipher(algorithms.AES(self._key_bytes), modes.ECB())
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(encrypted).decode("ascii")

    def _get(self, path: str, params: dict) -> dict:
        response = self.session.get(
            f"{self.base_url}{path}",
            params=params,
            headers={"secret": self._make_secret()},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("慧牧云接口返回格式异常")
        return payload

    def get_farm_list(self) -> dict:
        """读取随应用发布的慧牧云牧场编码表。"""
        path = Path(__file__).resolve().parent.parent / "config" / "hmy_farms.json"
        with path.open("r", encoding="utf-8") as file:
            farms = json.load(file)

        normalized = []
        for farm in farms:
            normalized.append(
                {
                    "farmCode": str(farm.get("farmCode", "")).strip(),
                    "name": str(farm.get("name", "")).strip(),
                    "area": "慧牧云",
                    "region": "全部牧场",
                    # 现有牧场筛选器以 None 表示“未分类”。
                    "farmType": None,
                    "isAvailable": 1,
                }
            )
        return {"code": 200, "data": normalized}

    def get_farm_herd(self, farm_code: str, page_size: int = 2000) -> dict:
        """分页下载指定牧场的完整牛群数据。"""
        records: List[dict] = []
        total: Optional[int] = None
        page_num = 1

        while total is None or len(records) < total:
            payload = self._get(
                "/outside/yl/cow",
                {
                    "farmCode": str(farm_code),
                    "pageSize": page_size,
                    "pageNum": page_num,
                },
            )
            if total is None:
                total = int(payload.get("count") or 0)

            page_records = payload.get("data") or []
            if not isinstance(page_records, list):
                raise ValueError("慧牧云牛群接口 data 字段格式异常")
            if not page_records:
                break

            records.extend(page_records)
            page_num += 1
            if page_num > 10000:
                raise RuntimeError("慧牧云牛群接口分页异常，已停止下载")

        if total is not None and len(records) != total:
            raise ValueError(f"慧牧云牛群数据下载不完整：接口报告 {total} 条，实际取得 {len(records)} 条")

        return {"code": 200, "count": len(records), "data": records}
