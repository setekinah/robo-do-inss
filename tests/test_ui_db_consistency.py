from __future__ import annotations

import re
import unittest
from pathlib import Path


APP_JS = (Path(__file__).resolve().parents[1] / "app.js").read_text(encoding="utf-8")


def function_body(name: str, next_name: str) -> str:
    start = re.search(rf"  async {name}\([^)]*\) \{{", APP_JS)
    end_marker = re.search(rf"\n  (?:async )?{next_name}\(", APP_JS)
    if not start or not end_marker or end_marker.start() <= start.end():
        raise AssertionError(f"Função {name} não encontrada")
    return APP_JS[start.end() : end_marker.start()]


class UiDatabaseConsistencyTests(unittest.TestCase):
    def test_activity_is_added_only_after_persistence_succeeds(self) -> None:
        body = function_body("addActivity", "renderModalDocs")

        self.assertIn("if (!response.ok || !data.success)", body)
        self.assertLess(body.index("if (!response.ok || !data.success)"), body.index("lead.activities.unshift"))
        self.assertIn("const lead = this.currentLead", body)
        self.assertIn("alert(error.message || 'Não foi possível registrar a atividade.')", body)

    def test_document_status_changes_only_after_persistence_succeeds(self) -> None:
        body = function_body("toggleDocStatus", "loadModalContract")

        self.assertIn("if (!response.ok || !data.success)", body)
        self.assertLess(body.index("if (!response.ok || !data.success)"), body.index("d.status = data.status"))
        self.assertIn("const lead = this.currentLead", body)
        self.assertIn("alert(error.message || 'Não foi possível atualizar o status do documento.')", body)

    def test_stage_changes_only_after_confirmed_response_and_reports_failure(self) -> None:
        body = function_body("advanceStage", "openLeadModal")

        self.assertIn("if (!response.ok || !data.success)", body)
        self.assertLess(body.index("if (!response.ok || !data.success)"), body.index("item.crm_stage = data.stage"))
        self.assertIn("alert(error.message || 'Não foi possível atualizar a etapa do lead.')", body)

    def test_case_document_upload_retains_its_existing_rollback(self) -> None:
        body = function_body("uploadCaseDocument", "toggleDocStatus")

        self.assertIn("const originalStatus = doc.status", body)
        self.assertIn("doc.status = originalStatus", body)
        self.assertLess(body.index("doc.status = originalStatus"), body.index("alert(error.message"))


if __name__ == "__main__":
    unittest.main()
