from __future__ import annotations

import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path

import database
from repositories.cnis_import_repository import CnisImportRepository

from services.cnis_import_service import build_cnis_preview


class CnisImportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = Path(self.temporary_directory.name) / "cnis.db"
        database.init_database()
        self.attendance_id = database.save_attendance(lead_name="Cliente", lead_phone="", flow_id="aposentadoria", flow_name="Aposentadoria", status="revisao", result_title="Revisão", summary="", next_step="", notes="", history=[])

    def tearDown(self) -> None:
        database.DB_PATH = self.original_db_path
        self.temporary_directory.cleanup()
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

    def test_preview_is_persisted_and_can_be_confirmed(self) -> None:
        repository = CnisImportRepository()
        import_id = repository.create(self.attendance_id, "C:/tmp/cnis.pdf", {"extraction_status": "extraido", "confidence": 0.9, "fields": {"cpf": ""}, "technical_notes": "ok", "text_excerpt": "texto"})
        repository.confirm(import_id)
        records = repository.list_for_attendance(self.attendance_id)
        self.assertEqual(records[0]["id"], import_id)
        self.assertIsNotNone(records[0]["confirmed_at"])


if __name__ == "__main__":
    unittest.main()
