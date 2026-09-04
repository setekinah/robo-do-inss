from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import database
import retirement_dossier


class IntelligentPendingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = Path(self.temporary_directory.name) / "pending.db"
        database.init_database()
        self.attendance_id = database.save_attendance(
            lead_name="Cliente Prioritário",
            lead_phone="11999999999",
            flow_id="aposentadoria",
            flow_name="Aposentadoria",
            status="revisao",
            result_title="Análise documental",
            summary="Caso de teste.",
            next_step="",
            notes="",
            history=[],
        )

    def tearDown(self) -> None:
        database.DB_PATH = self.original_db_path
        self.temporary_directory.cleanup()

    def test_queue_explains_critical_review_conflict_and_missing_dossier(self) -> None:
        database.create_crm_task(
            attendance_id=self.attendance_id,
            title="Revisar publicação recebida",
            due_at="2000-01-01",
            assigned_to="Dra. Ana",
            description="Confirmar providência antes de qualquer prazo jurídico.",
            priority="alta",
            requires_review=True,
            task_type="publicacao",
        )

        queue = database.list_intelligent_pending_items()
        item = next(row for row in queue["items"] if row["attendance_id"] == self.attendance_id)
        reasons = {reason["code"] for reason in item["reasons"]}

        self.assertEqual(item["priority"], "critica")
        self.assertTrue({"tarefa_revisao", "conflito", "proxima_acao", "dossie_ausente"}.issubset(reasons))
        self.assertIn("exigem confirmação humana", queue["notice"])

    def test_human_reviewed_dossier_is_not_returned_as_pending_review(self) -> None:
        report = retirement_dossier.build_retirement_dossier(documents=[], triage_profile={})
        report = retirement_dossier.apply_human_decision(
            report,
            status="prosseguir_analise",
            responsible="Dra. Ana",
            note="Prosseguir com conferência técnica.",
        )
        database.save_attendance_audit(
            attendance_id=self.attendance_id,
            audit_type=retirement_dossier.AUDIT_TYPE_RETIREMENT_DOSSIER,
            status=report["status"],
            report=report,
        )

        queue = database.list_intelligent_pending_items()
        item = next(row for row in queue["items"] if row["attendance_id"] == self.attendance_id)
        reasons = {reason["code"] for reason in item["reasons"]}

        self.assertNotIn("dossie_ausente", reasons)
        self.assertNotIn("dossie_revisao", reasons)


if __name__ == "__main__":
    unittest.main()
