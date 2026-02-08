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

        # 创建独立的session
        # 禁用代理，直接连接（测试证明直连即可访问伊起牛API）
        self.session = requests.Session()
        self.session.trust_env = False  # 不使用环境变量中的代理
        self.session.proxies = {
            'http': None,
            'https': None,
        }

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
                # 使用self.session而不是直接使用requests，以便使用代理
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()

                # 先保存响应文本，再解析JSON
                response_text = response.text
                self.logger.info(f"响应状态码: {response.status_code}")
                self.logger.info(f"响应大小: {len(response_text)} 字符")

                result = response.json()
                self.logger.info(f"result keys: {list(result.keys()) if isinstance(result, dict) else 'not dict'}")

                # 如果是get_user_info，打印data内容
                if endpoint == "/system/user/getInfo":
                    import json
                    self.logger.info(f"=== get_user_info 响应前500字符 ===")
                    self.logger.info(response_text[:500])
                    data = result.get("data", {})
                    self.logger.info(f"data类型: {type(data)}")
                    if isinstance(data, dict):
                        self.logger.info(f"data keys: {list(data.keys())}")
                        farms = data.get("farms", [])
                        self.logger.info(f"farms: {type(farms)}, 长度={len(farms) if farms else 0}")

                # 检查API返回的业务状态码（200=通用成功，0=部分接口成功码）
                if result.get("code") not in (0, 200):
                    raise ValueError(f"API错误: {result.get('msg', '未知错误')}")

                self.logger.info(f"API请求成功")
                return result

            except requests.exceptions.Timeout:
                if attempt == max_retries - 1:
                    self.logger.error("连接超时")
                    raise TimeoutError(
                        "连接伊起牛服务器超时。\n\n"
                        "可能原因：\n"
                        "1. 网络连接不稳定\n"
                        "2. 当前IP未加入伊起牛API白名单\n\n"
                        "解决方案：\n"
                        "- 检查网络连接\n"
                        "- 尝试连接VPN\n"
                        "- 联系伊起牛技术支持添加您的IP到白名单"
                    )
                self.logger.warning(f"请求超时，重试 {attempt + 1}/{max_retries}")

            except requests.exceptions.ConnectionError:
                if attempt == max_retries - 1:
                    self.logger.error("网络连接错误")
                    raise ConnectionError(
                        "无法连接到伊起牛服务器。\n\n"
                        "可能原因：\n"
                        "1. 网络连接问题\n"
                        "2. 当前IP未加入伊起牛API白名单（最常见）\n\n"
                        "解决方案：\n"
                        "- 检查网络连接\n"
                        "- 尝试连接VPN\n"
                        "- 联系伊起牛技术支持，提供您的公网IP申请加入白名单"
                    )
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
        获取牧场牛群数据（含不在场牛）

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
                        "living": True/False,  # 是否在场
                        ...
                    },
                    ...
                ]
            }
        """
        self.logger.info(f"获取牧场 {farm_code} 的牛群数据（含不在场牛）")
        params = {
            "farmCode": farm_code
        }
        return self._request("GET", "/cattle/farmcow/getNewHerd", params=params)

    def get_farm_list(self) -> dict:
        """
        获取牧场列表（大区/区域/牧场结构）

        返回:
            {
                "code": 200,
                "msg": "操作成功",
                "data": [
                    {
                        "farmCode": "10042",
                        "name": "XX牧场",
                        "region": "龙江区域",
                        "area": "东部奶源大区",
                        "isAvailable": 1,  # 1=可用, 0=关停
                        ...
                    },
                    ...
                ]
            }
        """
        self.logger.info("获取牧场列表（带大区/区域信息）")
        return self._request("GET", "/system/farm/getFarmList")

    def get_breeding_records(self, farm_code: str) -> dict:
        """
        获取配种记录

        参数:
            farm_code: 牧场站号（必传）

        返回:
            {
                "code": 0,
                "msg": "",
                "data": {
                    "total": 123,
                    "rows": [
                        {
                            "earNum": "牛号",
                            "insemDate": "配种时间",
                            "frozenSpermNum": "冻精号",
                            "frozenSpermType": "冻精类型（FST001=性控, FST002=常规）",
                            "eventInseminationTimes": "本胎次配次",
                            "cowLactation": "胎次",
                            "cowMonthAge": "月龄",
                            "cowBirthday": "出生日期",
                            ...
                        }
                    ]
                }
            }
        """
        self.logger.info(f"获取牧场 {farm_code} 的配种记录")
        params = {
            "farmCode": farm_code,
            "insemType": "IT001"  # 必传，固定值
        }
        return self._request("GET", "/breed/insem/getInsemList", params=params)

    def get_stock_detail(self, farm_code: str) -> dict:
        """
        获取牧场冻精库存详情

        参数:
            farm_code: 牧场站号

        返回:
            {
                "code": 200,
                "msg": null,
                "data": [
                    {
                        "materialNum": "291HO22028",
                        "stockSum": 135.0,
                        "materialClassify": "DJ",
                        ...
                    },
                    ...
                ]
            }
        """
        self.logger.info(f"获取牧场 {farm_code} 的冻精库存")
        params = {
            "farmCode": farm_code,
            "materialClassify": "DJ"
        }
        return self._request("GET", "/stock/stock/getStockDetail", params=params)

    def batch_add_selection(self, records: list) -> dict:
        """
        批量新增选配结果

        参数:
            records: 选配记录列表，每条格式:
                {
                    "farmCode": "11432",
                    "earNum": "1055",
                    "indexScore": 85.5,
                    "sexedSemen1": "", ..., "sexedSemen4": "",
                    "conventionalSemen1": "", ..., "conventionalSemen4": "",
                    "beefCattleFrozenSemen": ""
                }

        返回:
            {"code": 200, "msg": "共N条数据，成功N条，失败N条", "data": [失败详情]}
        """
        self.logger.info(f"批量推送选配结果: {len(records)} 条")
        return self._request("POST", "/breed/selection/batchAdd", json=records)

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
            matched = []
            for f in user_farms:
                farm_code = f.get("farmCode", "")
                # 转为字符串进行比较，处理可能的数字类型
                if str(farm_code).strip() == keyword:
                    matched.append(f)
                    self.logger.debug(f"匹配到牧场: {f.get('farmName', '')} (站号: {farm_code})")
        else:
            # 名称模糊搜索（不区分大小写）
            self.logger.info("文字，作为名称模糊搜索")
            keyword_lower = keyword.lower()
            matched = []
            for f in user_farms:
                farm_name = str(f.get("farmName", ""))
                if keyword_lower in farm_name.lower():
                    matched.append(f)
                    self.logger.debug(f"匹配到牧场: {farm_name}")

        self.logger.info(f"找到 {len(matched)} 个匹配的牧场")
        return matched
