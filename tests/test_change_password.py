"""本地账号修改密码回归测试。"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.api_client import APIClient
from config.hmy_access import can_use_interface_data, is_hmy_user_allowed
from gui.change_password_dialog import validate_password_change


TEST_DB_MATERIAL = "test-db-value"
TEST_JWT_MATERIAL = "test-jwt-signing-value"


class ChangePasswordValidationTests(unittest.TestCase):
    def test_accepts_valid_password_change(self):
        self.assertEqual(
            validate_password_change("old-password", "new-password", "new-password"),
            "",
        )

    def test_rejects_invalid_password_change(self):
        self.assertIn(
            "不一致",
            validate_password_change("old-password", "new-password", "different"),
        )
        self.assertIn(
            "至少",
            validate_password_change("old-password", "short", "short"),
        )
        self.assertIn(
            "不能与",
            validate_password_change("same-password", "same-password", "same-password"),
        )


class TemporaryAccountAccessTests(unittest.TestCase):
    def test_temporary_account_cannot_use_interface_data(self):
        self.assertFalse(can_use_interface_data("01062799"))
        self.assertFalse(is_hmy_user_allowed("01062799"))


class APIClientChangePasswordTests(unittest.TestCase):
    def test_sends_authenticated_password_change(self):
        client = APIClient.__new__(APIClient)
        client.token = "test-client-token"
        client._make_request = MagicMock(
            return_value=(True, {"success": True, "message": "密码修改成功"})
        )

        success, message = client.change_password(
            "old-password",
            "new-password",
        )

        self.assertTrue(success)
        self.assertEqual(message, "密码修改成功")
        method, endpoint, data = client._make_request.call_args.args
        headers = client._make_request.call_args.kwargs["headers"]
        self.assertEqual(method, "POST")
        self.assertEqual(endpoint, "/api/auth/change-password")
        self.assertEqual(data["current_password"], "old-password")
        self.assertEqual(data["new_password"], "new-password")
        self.assertEqual(
            headers["Authorization"],
            "Bearer test-client-token",
        )


class _FakeConnection:
    def __init__(self, rowcount):
        self.rowcount = rowcount
        self.params = None

    def execute(self, _statement, params):
        self.params = params
        return SimpleNamespace(rowcount=self.rowcount)


class _FakeBegin:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, traceback):
        return False


class _FakeEngine:
    def __init__(self, rowcount):
        self.connection = _FakeConnection(rowcount)

    def begin(self):
        return _FakeBegin(self.connection)


class ChangePasswordRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment = patch.dict(
            os.environ,
            {
                "DB_PASSWORD": TEST_DB_MATERIAL,
                "JWT_SECRET": TEST_JWT_MATERIAL,
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

    def _headers(self, username="local-user"):
        token = self.auth_api.create_access_token(username)
        return {"Authorization": f"Bearer {token}"}

    def _first_login_headers(self, username="local-user"):
        token = self.auth_api.create_access_token(
            username,
            must_change_password=True,
            auth_type="local",
        )
        return {"Authorization": f"Bearer {token}"}

    def test_changes_only_authenticated_users_own_password(self):
        engine = _FakeEngine(rowcount=1)
        with patch.object(
            self.auth_api,
            "get_db_engine",
            return_value=engine,
        ):
            response = self.client.post(
                "/api/auth/change-password",
                json={
                    "current_password": "old-password",
                    "new_password": "new-password",
                },
                headers=self._headers("local-user"),
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(engine.connection.params["username"], "local-user")

    def test_first_login_token_can_only_change_password(self):
        headers = self._first_login_headers()
        verify_response = self.client.post("/api/auth/verify", headers=headers)
        self.assertEqual(verify_response.status_code, 403)
        self.assertEqual(verify_response.json()["detail"], "必须先修改密码")

        with patch.object(
            self.auth_api,
            "get_db_engine",
            return_value=_FakeEngine(rowcount=1),
        ):
            change_response = self.client.post(
                "/api/auth/change-password",
                json={
                    "current_password": "old-password",
                    "new_password": "new-password",
                },
                headers=headers,
            )

        self.assertEqual(change_response.status_code, 200)
        payload = change_response.json()
        self.assertTrue(payload["success"])
        self.assertFalse(payload["data"]["must_change_password"])
        replacement = payload["data"]["token"]
        verified = self.client.post(
            "/api/auth/verify",
            headers={"Authorization": f"Bearer {replacement}"},
        )
        self.assertEqual(verified.status_code, 200)

    def test_rejects_incorrect_current_password(self):
        with patch.object(
            self.auth_api,
            "get_db_engine",
            return_value=_FakeEngine(rowcount=0),
        ):
            response = self.client.post(
                "/api/auth/change-password",
                json={
                    "current_password": "wrong-password",
                    "new_password": "new-password",
                },
                headers=self._headers(),
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])
        self.assertEqual(response.json()["message"], "当前密码错误")

    def test_requires_authentication(self):
        response = self.client.post(
            "/api/auth/change-password",
            json={
                "current_password": "old-password",
                "new_password": "new-password",
            },
        )

        self.assertIn(response.status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()
