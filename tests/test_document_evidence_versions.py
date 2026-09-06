from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import database


class DocumentEvidenceVersionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = Path(self.temporary_directory.name) / "evidence.db"
        database.init_database()
        self.attendance_id = database.save_attendance(
            lead_name="Cliente de Evidência", lead_phone="11999999999", flow_id="aposentadoria",
            flow_name="Aposentadoria", status="aprovado", result_title="Análise", summary="",
            next_step="", notes="", history=[],
        )
        self.document_id = int(database.list_attendance_documents(self.attendance_id)[0]["id"])

    def tearDown(self) -> None:
        database.DB_PATH = self.original_db_path
        self.temporary_directory.cleanup()

    def _record(self, text: str, path: str) -> int:
        return database.record_document_version(
            attendance_id=self.attendance_id, document_id=self.document_id,
            content_hash=hashlib.sha256(text.encode()).hexdigest(), original_name="prova.pdf",
            stored_path=path, raw_text=text, extracted_data={"campo": text},
            source_type="pdf_nativo", extraction_status="extraido", extraction_confidence=.95,
            technical_notes="ok",
        )

    def test_versions_are_preserved_and_counted_independently(self) -> None:
        first = self._record("primeira leitura", "/privado/v1.pdf")
        second = self._record("segunda leitura", "/privado/v2.pdf")

        summary = database.document_evidence_summary(self.attendance_id)[self.document_id]
        self.assertEqual(summary["version_count"], 2)
        self.assertEqual(summary["latest_version_id"], second)
        with database.get_connection() as conn:
            rows = conn.execute("SELECT raw_text FROM atendimento_documento_versoes ORDER BY id").fetchall()
        self.assertEqual([row["raw_text"] for row in rows], ["primeira leitura", "segunda leitura"])
        self.assertIsNotNone(database.get_document_version_by_hash(self.document_id, hashlib.sha256(b"primeira leitura").hexdigest()))
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
