from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RetirementDossierUiTests(unittest.TestCase):
    def test_retirement_dossier_is_available_only_from_the_case_documents(self) -> None:
        markup = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
        script = (PROJECT_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="modal-retirement-dossier-button"', markup)
        self.assertIn('id="modal-retirement-dossier-result"', markup)
        self.assertIn("runRetirementDossier()", script)
        self.assertIn("saveRetirementDossierDecision()", script)
        self.assertIn("flow_id === 'aposentadoria'", script)

    def test_api_exposes_a_protected_retirement_dossier_endpoint(self) -> None:
        server = (PROJECT_ROOT / "api_server.py").read_text(encoding="utf-8")

        self.assertIn('endswith("/dossie-probatorio")', server)
        self.assertIn("handle_post_retirement_dossier", server)
        self.assertIn("revisão humana", server)


if __name__ == "__main__":
    unittest.main()
