from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class IntelligentPendingUiTests(unittest.TestCase):
    def test_dashboard_exposes_explainable_pending_queue(self) -> None:
        markup = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
        script = (PROJECT_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="smart-pending-list"', markup)
        self.assertIn('id="btn-refresh-smart-pending"', markup)
        self.assertIn("loadSmartPending()", script)
        self.assertIn("renderSmartPending()", script)
        self.assertIn("Abrir caso", script)

    def test_api_has_pending_queue_endpoint(self) -> None:
        server = (PROJECT_ROOT / "api_server.py").read_text(encoding="utf-8")

        self.assertIn('path == "/api/pendencias-inteligentes"', server)
        self.assertIn("handle_get_intelligent_pending_items", server)


if __name__ == "__main__":
    unittest.main()
