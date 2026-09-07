"""Regressões P0.4: Font Awesome deve funcionar sem ampliar excessivamente a CSP."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = ROOT / "index.html"
API_SERVER = ROOT / "api_server.py"


class CSPFontAwesomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = INDEX_HTML.read_text(encoding="utf-8")
        cls.server = API_SERVER.read_text(encoding="utf-8")

    def test_fontawesome_stylesheet_uses_expected_cdn(self) -> None:
        self.assertIn(
            "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css",
            self.html,
        )

    def test_csp_allows_fontawesome_font_origin(self) -> None:
        self.assertIn(
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com;",
            self.server,
        )

    def test_font_src_remains_restricted(self) -> None:
        match = re.search(r'font-src ([^;]+);', self.server)
        self.assertIsNotNone(match, "Diretiva font-src não encontrada.")

        directive = match.group(1)

        self.assertNotIn("*", directive)
        self.assertNotIn("data:", directive)
        self.assertNotIn("'unsafe-inline'", directive)

        self.assertIn("'self'", directive)
        self.assertIn("https://fonts.gstatic.com", directive)
        self.assertIn("https://cdnjs.cloudflare.com", directive)


if __name__ == "__main__":
    unittest.main()
