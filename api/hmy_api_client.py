"""慧牧云只读数据接口客户端。

客户端只携带软件登录 JWT，请求由 Genetic Improve 服务端代理并完成慧牧云鉴权。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import requests


class HMYApiClient:
    """通过自有认证服务访问慧牧云牛群数据。"""

    DEFAULT_PROXY_BASE_URL = "https://api.genepop.com"

    def __init__(
        self,
        auth_token: Optional[str] = None,
        proxy_base_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ):
        self.base_url = (
            proxy_base_url
            or self._load_proxy_base_url()
            or self.DEFAULT_PROXY_BASE_URL
        ).rstrip("/")
        self._auth_token = auth_token or self._load_auth_token()
        if not self._auth_token:
            raise ValueError("登录状态已失效，请重新登录后使用慧牧云数据源")

        self.session = session or requests.Session()
        self.session.trust_env = False
        self.session.proxies = {"http": None, "https": None}
        self.session.headers.update(
            {"Authorization": f"Bearer {self._auth_token}"}
        )

    @staticmethod
    def _load_auth_token() -> Optional[str]:
        """从软件现有令牌管理器读取登录 JWT。"""
        try:
            from auth.token_manager import get_token_manager

            return get_token_manager().get_token()
        except Exception:
            return None

    @staticmethod
    def _load_proxy_base_url() -> Optional[str]:
        """复用软件 API 环境配置，避免在功能代码中硬编码环境。"""
        path = Path(__file__).resolve().parent.parent / "config" / "api_config.json"
        try:
            with path.open("r", encoding="utf-8") as file:
                config = json.load(file)
            environment = config.get("current_environment", "production")
            return (
                config.get("environments", {})
                .get(environment, {})
                .get("api_base_url")
            )
        except (OSError, ValueError, TypeError):
            return None

    def _get_cow_page(
        self,
        farm_code: str,
        page_size: int,
        page_num: int,
    ) -> dict:
        try:
            response = self.session.get(
                f"{self.base_url}/api/auth/hmy/cows",
                params={
                    "farmCode": str(farm_code),
                    "pageSize": int(page_size),
                    "pageNum": int(page_num),
                },
                timeout=35,
            )
        except requests.RequestException as exc:
            raise RuntimeError("无法连接慧牧云数据代理服务") from exc

        if response.status_code == 401:
            raise RuntimeError("登录状态已失效，请重新登录后再试")
        if response.status_code == 403:
            raise RuntimeError("当前账号未开通慧牧云功能")
        if response.status_code in (502, 503):
            raise RuntimeError("慧牧云服务暂时不可用，请稍后重试")

        try:
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError("慧牧云数据代理返回异常") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("慧牧云数据代理返回格式异常")
        rows = payload.get("data") or []
        if not isinstance(rows, list):
            raise RuntimeError("慧牧云数据代理 data 字段格式异常")
        try:
            count = int(payload.get("count") or 0)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("慧牧云数据代理 count 字段格式异常") from exc

        return {"code": payload.get("code", 200), "count": count, "data": rows}

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
                    "farmType": None,
                    "isAvailable": 1,
                }
            )
        return {"code": 200, "data": normalized}

    def get_farm_herd(self, farm_code: str, page_size: int = 2000) -> dict:
        """通过受控代理分页下载指定牧场的完整牛群数据。"""
        records: List[dict] = []
        total: Optional[int] = None
        page_num = 1

        while total is None or len(records) < total:
            payload = self._get_cow_page(
                farm_code=farm_code,
                page_size=page_size,
                page_num=page_num,
            )
            if total is None:
                total = payload["count"]

            page_records = payload["data"]
            if not page_records:
                break

            records.extend(page_records)
            page_num += 1
            if page_num > 10000:
                raise RuntimeError("慧牧云牛群接口分页异常，已停止下载")

        if total is not None and len(records) != total:
            raise ValueError(
                f"慧牧云牛群数据下载不完整：接口报告 {total} 条，"
                f"实际取得 {len(records)} 条"
            )

        return {"code": 200, "count": len(records), "data": records}
