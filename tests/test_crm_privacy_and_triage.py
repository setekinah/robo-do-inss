from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import database
from flows_data import FLOW_DEFINITIONS
from triage_engine import answer_current_question, create_state


class CrmPrivacyAndRetirementTriageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = Path(self.temporary_directory.name) / "crm.db"
        database.init_database()

    def tearDown(self) -> None:
        database.DB_PATH = self.original_db_path
        self.temporary_directory.cleanup()

    def test_retirement_flow_reaches_strategy_cnis_and_objective_questions(self) -> None:
        flow = FLOW_DEFINITIONS["aposentadoria"]
        state = create_state("aposentadoria", flow)
        answers = [
            "Sim",
            "Comum",
            "Quase",
            "Nao calculado",
            "Com divergencias",
            "Rural",
            "Planejamento",
            "Parcial",
        ]

        result = None
        for answer in answers:
            state, result = answer_current_question(state, flow, answer)

        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "revisao")
        self.assertEqual(
            [item["node_code"] for item in state.history],
            ["AP-01", "AP-02", "AP-03", "AP-06", "AP-07", "AP-08", "AP-09", "AP-10"],
        )

    def test_privacy_notice_and_structured_profile_are_persisted_and_auditable(self) -> None:
        profile = {
            "birth_date": "1970-05-10",
            "calculation_criterion": "Mulher",
            "contribution_estimate": "28 anos",
            "cnis_status": "Com divergências",
            "relevant_periods": ["Rural", "RPPS/CTC"],
            "objective": "Planejamento e acerto do CNIS",
        }
        attendance_id = database.save_attendance(
            lead_name="Cliente de teste",
            lead_phone="11999999999",
            lead_email="cliente@example.com",
            lead_source="Indicação",
            flow_id="aposentadoria",
            flow_name="Aposentadoria",
            status="revisao",
            result_title="Revisão jurídica",
            summary="Caso de teste.",
            next_step="Conferir CNIS.",
            notes="",
            history=[],
            privacy_notice_acknowledged=True,
            privacy_legal_basis="procedimentos_preliminares",
            triage_profile=profile,
        )

        details = database.get_attendance_details(attendance_id)

        self.assertEqual(details["privacy_notice_acknowledged"], 1)
        self.assertEqual(details["privacy_legal_basis"], "procedimentos_preliminares")
        self.assertIsNotNone(details["privacy_acknowledged_at"])
        self.assertEqual(json.loads(details["triage_profile_json"]), profile)

    def test_crm_update_requires_base_legal_and_records_privacy_notice(self) -> None:
        attendance_id = database.save_attendance(
            lead_name="Cliente legado",
            lead_phone="",
            flow_id="aposentadoria",
            flow_name="Aposentadoria",
            status="revisao",
            result_title="Revisão jurídica",
            summary="Caso legado.",
            next_step="Conferir documentos.",
            notes="",
            history=[],
        )

        with self.assertRaises(ValueError):
            database.update_crm_case(
                attendance_id=attendance_id,
                crm_stage="triagem",
                conflict_status="pendente",
                assigned_to="Advogada responsável",
                next_action="Checar conflito",
                next_action_at="2026-08-02",
                privacy_notice_acknowledged=True,
                privacy_legal_basis="",
            )

        database.update_crm_case(
            attendance_id=attendance_id,
            crm_stage="triagem",
            conflict_status="pendente",
            assigned_to="Advogada responsável",
            next_action="Checar conflito",
            next_action_at="2026-08-02",
            privacy_notice_acknowledged=True,
            privacy_legal_basis="exercicio_regular_direitos",
        )
        details = database.get_attendance_details(attendance_id)
        self.assertEqual(details["privacy_notice_acknowledged"], 1)
        self.assertEqual(details["privacy_legal_basis"], "exercicio_regular_direitos")


if __name__ == "__main__":
    unittest.main()
