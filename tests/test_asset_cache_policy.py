from __future__ import annotations

import http.client
import re
import threading
import unittest
from pathlib import Path

import api_server


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class _ServerFixture:
    def __init__(self) -> None:
        self.httpd = api_server.ThreadingHTTPServer(("127.0.0.1", 0), api_server.SofiPreviRequestHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def get(self, path: str) -> tuple[int, dict[str, str]]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            response.read()
            return response.status, {key.lower(): value for key, value in response.getheaders()}
        finally:
            conn.close()

    def shutdown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class AssetCachePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = _ServerFixture()
        cls.index = (REPOSITORY_ROOT / "index.html").read_text(encoding="utf-8")
        cls.portal = (REPOSITORY_ROOT / "portal.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def test_html_is_revalidated_and_api_is_not_stored(self) -> None:
        for path in ("/", "/index.html", "/portal.html"):
            status, headers = self.server.get(path)
            self.assertEqual(status, 200)
            self.assertEqual(headers.get("cache-control"), "no-cache, max-age=0, must-revalidate")
            self.assertNotIn("immutable", headers["cache-control"])

        status, headers = self.server.get("/api/auth/status")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("cache-control"), "no-store")

    def test_versioned_assets_are_immutable_and_query_preserves_allowlist_access(self) -> None:
        for path in ("/styles.css?v=p1.1-20260907", "/app.js?v=p1.1-20260907", "/portal.js?v=p1.1-20260907"):
            status, headers = self.server.get(path)
            self.assertEqual(status, 200)
            self.assertEqual(headers.get("cache-control"), "public, max-age=31536000, immutable")

    def test_first_party_html_references_use_one_release_token(self) -> None:
        self.assertNotIn("control-icons-20260903", self.index)
        references = re.findall(r'(?:styles\.css|app\.js|portal\.js)\?v=([^"\']+)', self.index + self.portal)
        self.assertEqual(set(references), {"p1.1-20260907"})

    def test_cache_policy_keeps_security_headers(self) -> None:
        _, headers = self.server.get("/app.js?v=p1.1-20260907")
        self.assertIn("default-src 'self'", headers.get("content-security-policy", ""))
        self.assertEqual(headers.get("x-content-type-options"), "nosniff")


if __name__ == "__main__":
    unittest.main()
