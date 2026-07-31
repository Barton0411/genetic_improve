from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import requests

from api.api_client import APIClient, _sanitize_for_log


class APILogSanitizationTests(unittest.TestCase):
    def test_case_insensitive_headers_and_nested_credentials_are_redacted(self):
        sanitized = _sanitize_for_log(
            requests.structures.CaseInsensitiveDict(
                {
                    "Content-Type": "application/json",
                    "Authorization": "value-must-not-be-logged",
                    "Cookie": "value-must-not-be-logged",
                    "X-Api-Key": "value-must-not-be-logged",
                    "data": {"token": "value-must-not-be-logged"},
                }
            )
        )

        self.assertEqual(sanitized["Content-Type"], "application/json")
        self.assertEqual(sanitized["Authorization"], "***")
        self.assertEqual(sanitized["Cookie"], "***")
        self.assertEqual(sanitized["X-Api-Key"], "***")
        self.assertEqual(sanitized["data"]["token"], "***")
        self.assertNotIn("value-must-not-be-logged", repr(sanitized))

    def test_debug_log_redacts_request_and_response_headers(self):
        client = APIClient.__new__(APIClient)
        client.base_url = "https://api.example.test"
        client.timeout = 1
        client.verify_ssl = True
        client.session = MagicMock()
        client.session.headers = requests.structures.CaseInsensitiveDict(
            {
                "Authorization": "request-value-must-not-be-logged",
                "Cookie": "request-value-must-not-be-logged",
                "Content-Type": "application/json",
            }
        )
        response = MagicMock()
        response.status_code = 200
        response.headers = requests.structures.CaseInsensitiveDict(
            {
                "Set-Cookie": "response-value-must-not-be-logged",
                "X-Access-Token": "response-value-must-not-be-logged",
                "Content-Type": "application/json",
            }
        )
        response.json.return_value = {"success": True}
        client.session.get.return_value = response

        with self.assertLogs("api.api_client", level="DEBUG") as logs:
            success, _ = client._make_request("GET", "/safe-endpoint")

        output = "\n".join(logs.output)
        self.assertTrue(success)
        self.assertIn("Request headers:", output)
        self.assertIn("Response headers:", output)
        self.assertNotIn("request-value-must-not-be-logged", output)
        self.assertNotIn("response-value-must-not-be-logged", output)


if __name__ == "__main__":
    unittest.main()
