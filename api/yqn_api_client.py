"""
伊起牛API客户端

封装所有伊起牛API调用，提供统一的错误处理和重试机制。
"""
import requests
from typing import Optional, List, Dict
import logging


class YQNApiClient:
    """伊起牛API客户端"""

    BASE_URL = "https://yqnapi.yqndairy.com"
    TIMEOUT = 30  # 超时30秒

    def __init__(self, token: str):
        """
        初始化API客户端

        参数:
            token: 伊起牛访问令牌（Bearer Token）
        """
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self.logger = logging.getLogger(__name__)

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """
        统一请求方法，包含错误处理和重试逻辑

        参数:
            method: HTTP方法 (GET, POST等)
            endpoint: API端点路径
            **kwargs: 传递给requests的其他参数

        返回:
            API响应数据

        异常:
            TimeoutError: 连接超时
            ConnectionError: 网络连接错误
            ValueError: API返回错误
        """
        url = f"{self.BASE_URL}{endpoint}"
        kwargs.setdefault('timeout', self.TIMEOUT)
        kwargs.setdefault('headers', self.headers)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.logger.info(f"API请求: {method} {url}")
                response = requests.request(method, url, **kwargs)
                response.raise_for_status()

                result = response.json()

                # 检查API返回的业务状态码
                if result.get("code") != 200:
                    raise ValueError(f"API错误: {result.get('msg', '未知错误')}")

                self.logger.info(f"API请求成功")
                return result

            except requests.exceptions.Timeout:
                if attempt == max_retries - 1:
                    self.logger.error("连接超时")
                    raise TimeoutError("连接伊起牛服务器超时，请检查网络连接")
                self.logger.warning(f"请求超时，重试 {attempt + 1}/{max_retries}")

            except requests.exceptions.ConnectionError:
                if attempt == max_retries - 1:
                    self.logger.error("网络连接错误")
                    raise ConnectionError("无法连接到伊起牛服务器，请检查网络连接")
                self.logger.warning(f"连接失败，重试 {attempt + 1}/{max_retries}")

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    raise ValueError("Token已过期或无效，请重新登录")
                self.logger.error(f"HTTP错误: {e}")
                raise

            except Exception as e:
                if attempt == max_retries - 1:
                    self.logger.exception("API请求失败")
                    raise
                self.logger.warning(f"请求失败，重试 {attempt + 1}/{max_retries}: {e}")

    def get_user_info(self) -> dict:
        """
        获取用户信息和牧场列表

        返回:
            {
                "code": 200,
                "msg": "操作成功",
                "data": {
                    "user": {...},
                    "currentFarm": {...},
                    "farms": [
                        {"farmCode": "10042", "farmName": "XX牧场", ...},
                        ...
                    ]
                }
            }
        """
        self.logger.info("获取用户信息和牧场列表")
        return self._request("GET", "/system/user/getInfo")

    def get_farm_herd(self, farm_code: str) -> dict:
        """
        获取牧场牛群数据

        参数:
            farm_code: 牧场站号

        返回:
            {
                "code": 200,
                "msg": null,
                "data": [
                    {
                        "earNum": "牛号",
                        "fatherNum": "父号",
                        ...
                    },
                    ...
                ]
            }
        """
        self.logger.info(f"获取牧场 {farm_code} 的牛群数据")
        params = {
            "farmCode": farm_code,
            "equipment": "afilmilk"
        }
        return self._request("GET", "/cattle/farmcow/getHerd", params=params)

    def search_farms(self, keyword: str, user_farms: List[dict]) -> List[dict]:
        """
        搜索牧场（本地搜索，从用户牧场列表中筛选）

        参数:
            keyword: 搜索关键词（站号或名称）
            user_farms: 用户牧场列表

        返回:
            匹配的牧场列表
        """
        keyword = keyword.strip()
        if not keyword:
            return user_farms

        self.logger.info(f"搜索牧场: '{keyword}'")

        # 判断是否为纯数字（站号精确查询）
        if keyword.isdigit():
            self.logger.info("纯数字，作为站号精确查询")
            matched = [f for f in user_farms if f.get("farmCode", "") == keyword]
        else:
            # 名称模糊搜索（不区分大小写）
            self.logger.info("文字，作为名称模糊搜索")
            keyword_lower = keyword.lower()
            matched = [
                f for f in user_farms
                if keyword_lower in f.get("farmName", "").lower()
            ]

        self.logger.info(f"找到 {len(matched)} 个匹配的牧场")
        return matched
