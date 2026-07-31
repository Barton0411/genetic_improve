from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from auth.auth_service import AuthService


class AuthOnlineOnlyTests(unittest.TestCase):
    def test_network_exception_never_falls_back_to_embedded_credentials(self):
        service = object.__new__(AuthService)
        service.username = None
        service.api_client = MagicMock()
        service.token_manager = MagicMock()
        service.api_client.login.side_effect = ConnectionError(
            "simulated-sensitive-network-detail"
        )

        success, message = service.login("test-user", "test-password")

        self.assertFalse(success)
        self.assertEqual(
            message,
            "登录服务暂时不可用，请检查网络后重试",
        )
        self.assertNotIn("simulated-sensitive", message)


if __name__ == "__main__":
    unittest.main()
