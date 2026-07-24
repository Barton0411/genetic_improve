"""慧牧云服务端代理与桌面客户端回归测试。"""

from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import patch

import requests
from fastapi.testclient import TestClient

from api.hmy_api_client import HMYApiClient
from api.hmy_proxy import (
    HMYProxyClient,
    HMYProxyConfigError,
    is_hmy_user_allowed,
)

TEST_CIPHER_MATERIAL = "0123456789abcdef"
TEST_JWT_MATERIAL = "test-jwt-signing-value"
TEST_DB_MATERIAL = "test-db-value"
TEST_CLIENT_CREDENTIAL = "test-jwt-value"


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}
        self.trust_env = True
        self.proxies = {}

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class HMYProxyClientTests(unittest.TestCase):
    def test_proxy_encrypts_header_and_validates_response(self):
        material = TEST_CIPHER_MATERIAL
        session = FakeSession(
            [FakeResponse({"code": 200, "count": "1", "data": [{"id": 1}]})]
        )
        client = HMYProxyClient(
            aes_key=material,
            base_url="https://hmy.example.test",
            session=session,
        )

        payload = client.get_cow_page("farm-1", page_size=1, page_num=1)

        self.assertEqual(payload["count"], 1)
        self.assertEqual(len(payload["data"]), 1)
        _, request = session.calls[0]
        self.assertIn("secret", request["headers"])
        self.assertNotEqual(request["headers"]["secret"], material)
        self.assertFalse(session.trust_env)

    def test_proxy_secret_is_date_dependent_and_deterministic(self):
        material = TEST_CIPHER_MATERIAL
        client = HMYProxyClient(
            aes_key=material,
            base_url="https://hmy.example.test",
            session=FakeSession([]),
        )

        first = client._make_secret(date(2026, 7, 24))
        second = client._make_secret(date(2026, 7, 24))
        next_day = client._make_secret(date(2026, 7, 25))

        self.assertEqual(first, second)
        self.assertNotEqual(first, next_day)

    def test_proxy_requires_server_configuration(self):
        with patch.dict(
            os.environ,
            {"HMY_API_AES_KEY": "", "HMY_API_BASE_URL": ""},
            clear=False,
        ):
            with self.assertRaises(HMYProxyConfigError):
                HMYProxyClient()

    def test_server_whitelist(self):
        self.assertTrue(is_hmy_user_allowed("10075345"))
        self.assertFalse(is_hmy_user_allowed("not-allowed"))


class HMYDesktopClientTests(unittest.TestCase):
    def test_desktop_uses_jwt_proxy_and_merges_pages(self):
        material = TEST_CLIENT_CREDENTIAL
        session = FakeSession(
            [
                FakeResponse(
                    {"code": 200, "count": 3, "data": [{"id": 1}, {"id": 2}]}
                ),
                FakeResponse({"code": 200, "count": 3, "data": [{"id": 3}]}),
            ]
        )
        client = HMYApiClient(
            auth_token=material,
            proxy_base_url="https://api.example.test",
            session=session,
        )

        payload = client.get_farm_herd("farm-1", page_size=2)

        self.assertEqual(payload["count"], 3)
        self.assertEqual([row["id"] for row in payload["data"]], [1, 2, 3])
        self.assertEqual(
            session.headers["Authorization"],
            f"Bearer {material}",
        )
        self.assertTrue(
            all(
                call[0].endswith("/api/auth/hmy/cows")
                for call in session.calls
            )
        )
        self.assertTrue(
            all("secret" not in call[1].get("headers", {}) for call in session.calls)
        )

    def test_desktop_maps_forbidden_without_exposing_response(self):
        session = FakeSession([FakeResponse({"detail": "forbidden"}, 403)])
        client = HMYApiClient(
            auth_token=TEST_CLIENT_CREDENTIAL,
            proxy_base_url="https://api.example.test",
            session=session,
        )

        with self.assertRaisesRegex(RuntimeError, "未开通慧牧云功能"):
            client.get_farm_herd("farm-1")


class HMYAuthRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment = patch.dict(
            os.environ,
            {
                "DB_PASSWORD": TEST_DB_MATERIAL,
                "JWT_SECRET": TEST_JWT_MATERIAL,
                "HMY_API_AES_KEY": TEST_CIPHER_MATERIAL,
                "HMY_API_BASE_URL": "https://hmy.example.test",
            },
            clear=False,
        )
        cls.environment.start()
        from api import auth_api

        cls.auth_api = auth_api
        cls.client = TestClient(auth_api.app)

    @classmethod
    def tearDownClass(cls):
        cls.environment.stop()

    def _headers(self, username):
        credential = self.auth_api.create_access_token(username)
        return {"Authorization": f"Bearer {credential}"}

    def test_route_rejects_non_whitelisted_user(self):
        response = self.client.get(
            "/api/auth/hmy/cows",
            params={"farmCode": "farm-1", "pageSize": 1, "pageNum": 1},
            headers=self._headers("not-allowed"),
        )

        self.assertEqual(response.status_code, 403)

    def test_route_returns_page_for_whitelisted_user(self):
        expected = {"code": 200, "count": 1, "data": [{"id": 1}]}
        with patch.object(
            self.auth_api.HMYProxyClient,
            "get_cow_page",
            return_value=expected,
        ):
            response = self.client.get(
                "/api/auth/hmy/cows",
                params={"farmCode": "farm-1", "pageSize": 1, "pageNum": 1},
                headers=self._headers("10075345"),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)


if __name__ == "__main__":
    unittest.main()
