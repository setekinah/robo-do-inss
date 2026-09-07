from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import api_server


class FilOneCspTests(unittest.TestCase):
    def test_https_filone_origin_is_the_only_external_connect_source(self) -> None:
        with patch.dict(os.environ, {"FILONE_ENDPOINT": "https://eu-west-1.s3.filonecontent.com/path"}, clear=False), patch(
            "api_server.load_local_filone_environment"
        ):
            policy = api_server.content_security_policy()

        self.assertIn("connect-src 'self' https://eu-west-1.s3.filonecontent.com", policy)
        self.assertNotIn("connect-src *", policy)
        self.assertNotIn("connect-src https:", policy)

    def test_missing_or_invalid_filone_endpoint_keeps_connect_src_self_only(self) -> None:
        for endpoint in ("", "http://storage.example", "https://user:password@storage.example"):
            with self.subTest(endpoint=endpoint), patch.dict(os.environ, {"FILONE_ENDPOINT": endpoint}, clear=False), patch(
                "api_server.load_local_filone_environment"
            ):
                policy = api_server.content_security_policy()
            self.assertIn("connect-src 'self'", policy)
            self.assertNotIn("storage.example", policy)

    def test_policy_never_contains_filone_credentials_or_wildcards(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FILONE_ENDPOINT": "https://storage.example:9443",
                "FILONE_ACCESS_KEY": "access-key-must-not-appear",
                "FILONE_SECRET_KEY": "secret-key-must-not-appear",
                "FILONE_BUCKET": "private-bucket-must-not-appear",
            },
            clear=False,
        ), patch("api_server.load_local_filone_environment"):
            policy = api_server.content_security_policy()

        self.assertIn("connect-src 'self' https://storage.example:9443", policy)
        for secret in ("access-key-must-not-appear", "secret-key-must-not-appear", "private-bucket-must-not-appear", "*"):
            self.assertNotIn(secret, policy)


if __name__ == "__main__":
    unittest.main()
