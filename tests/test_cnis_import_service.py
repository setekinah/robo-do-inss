from __future__ import annotations

import unittest
from unittest.mock import patch

from services.cnis_import_service import build_cnis_preview


class CnisImportServiceTests(unittest.TestCase):
    @patch("services.cnis_import_service.analyze_document_bundle")
    def test_preview_keeps_only_reviewable_extraction_data(self, analyze_bundle) -> None:
        analyze_bundle.return_value = {
            "extraction_status": "extraido", "extraction_confidence": 0.88,
            "extracted_data": {"cpf": "529.982.247-25", "nit": "", "competencias": "01/2020"},
            "technical_notes": "Texto nativo.", "raw_text": "CNIS exemplo",
        }
        preview = build_cnis_preview(["C:/tmp/cnis.pdf"])
        self.assertEqual(preview["confidence"], 0.88)
        self.assertEqual(preview["fields"]["competencias"], "01/2020")
        self.assertEqual(preview["text_excerpt"], "CNIS exemplo")


if __name__ == "__main__":
    unittest.main()
