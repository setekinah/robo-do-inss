from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import document_storage
import office_settings
from data_paths import migrate_legacy_data, resolve_data_dir
from services.contract_service import build_fee_contract_preview
from services.document_score_service import build_document_case_score
from services.maternity_benefit_service import (
    SALARIO_MINIMO_2026,
    TETO_INSS_2026,
    estimate_maternity_benefit,
)


class _Upload:
    name = "meu documento.pdf"

    def getbuffer(self) -> bytes:
        return b"arquivo de teste"


class DataPathsAndServicesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_configured_directory_has_priority_and_legacy_files_are_preserved(self) -> None:
        configured = self.root / "operational"
        legacy = self.root / "legacy"
        (legacy / "uploads").mkdir(parents=True)
        (legacy / "office_settings.json").write_text('{"office_name":"Legado"}', encoding="utf-8")
        (legacy / "uploads" / "cnis.pdf").write_bytes(b"cnis")

        resolved = resolve_data_dir({"ROBO_INSS_DATA_DIR": str(configured)}, self.root)
        migrated = migrate_legacy_data(resolved, [legacy])

        self.assertEqual(resolved, configured)
        self.assertEqual(len(migrated), 2)
        self.assertEqual((configured / "uploads" / "cnis.pdf").read_bytes(), b"cnis")
        (configured / "office_settings.json").write_text('{"office_name":"Atual"}', encoding="utf-8")
        migrate_legacy_data(configured, [legacy])
        self.assertIn("Atual", (configured / "office_settings.json").read_text(encoding="utf-8"))
        self.assertTrue((legacy / "office_settings.json").exists())

    def test_settings_and_uploads_can_share_the_resolved_directory(self) -> None:
        original_settings_path = office_settings.SETTINGS_PATH
        original_uploads_dir = document_storage.UPLOADS_DIR
        try:
            office_settings.SETTINGS_PATH = self.root / "data" / "office_settings.json"
            document_storage.UPLOADS_DIR = self.root / "data" / "uploads"
            office_settings.save_office_settings({"office_name": "Escritório Teste"})
            saved_upload = document_storage.save_uploaded_document(7, "RG", _Upload())
            self.assertEqual(office_settings.load_office_settings()["office_name"], "Escritório Teste")
            self.assertTrue(Path(saved_upload).is_file())
            self.assertEqual(Path(saved_upload).parents[2], self.root / "data")
        finally:
            office_settings.SETTINGS_PATH = original_settings_path
            document_storage.UPLOADS_DIR = original_uploads_dir

    def test_domain_calculations_are_deterministic(self) -> None:
        score = build_document_case_score([
            {"required": 1, "status": "validado", "extraction_status": "extraido", "document_name": "RG"},
            {"required": 1, "status": "pendente", "extraction_status": "nao_processado", "document_name": "CNIS"},
        ])
        self.assertEqual(score, {"score": 56, "label": "Dossie parcialmente consolidado", "critical_gaps": ["CNIS"], "processed": 1})

        benefit = estimate_maternity_benefit("CLT", [10000])
        self.assertEqual(benefit["monthly_value"], TETO_INSS_2026)
        self.assertEqual(estimate_maternity_benefit("MEI", mei_standard=True)["monthly_value"], SALARIO_MINIMO_2026)

        contract = build_fee_contract_preview("BPC/LOAS", "Ana", {"fee_percentages": {"BPC/LOAS": 25}}, date(2026, 8, 12))
        self.assertIn("Ana", contract)
        self.assertIn("25%", contract)
        self.assertIn("12/08/2026", contract)


if __name__ == "__main__":
    unittest.main()
