from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CNISReportIntegrityTests(unittest.TestCase):
    def test_empty_catalog_does_not_hide_extracted_indicators(self) -> None:
        source = (ROOT / "api_server.py").read_text(encoding="utf-8")

        self.assertIn('max(\n                int(cnis_report["metricas"].get("alertas_contagem") or 0),', source)
        self.assertIn("len(catalog_matches)", source)

    def test_interface_does_not_call_document_competencies_completed_carencia(self) -> None:
        markup = (ROOT / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("COMPETÊNCIAS LOCALIZADAS", markup)
        self.assertNotIn("CARÊNCIA CUMPRIDA", markup)
        self.assertIn("indicadores para revisão", script)


if __name__ == "__main__":
    unittest.main()
