from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import database
from repositories.calculation_repository import CalculationRepository
from services.calculation_service import get_calculation_module, validate_calculation_request
from services.validation_service import validate_contribution_time, validate_cpf, validate_number


class CalculationFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = Path(self.temporary_directory.name) / "calculos.db"
        database.init_database()
        self.attendance_id = database.save_attendance(
            lead_name="Cliente de cálculo", lead_phone="", flow_id="aposentadoria", flow_name="Aposentadoria",
            status="revisao", result_title="Revisão jurídica", summary="Caso de teste.",
            next_step="Conferir CNIS.", notes="", history=[],
        )

    def tearDown(self) -> None:
        database.DB_PATH = self.original_db_path
        self.temporary_directory.cleanup()

    def test_validation_rejects_invalid_cpf_and_contribution_time(self) -> None:
        self.assertTrue(validate_cpf("529.982.247-25").is_valid)
        self.assertFalse(validate_cpf("111.111.111-11").is_valid)
        self.assertFalse(validate_contribution_time(20, 12, 0).is_valid)
        self.assertFalse(validate_number(float("nan"), "Renda").is_valid)

    def test_calculation_catalog_requires_a_known_module_and_valid_input_shape(self) -> None:
        module = get_calculation_module("bpc_loas")
        self.assertTrue(module.requires_human_review)
        self.assertFalse(validate_calculation_request("bpc_loas", {"renda": 450.0}).errors)
        self.assertTrue(validate_calculation_request("bpc_loas", {"renda": float("inf")}).errors)
        with self.assertRaises(ValueError):
            get_calculation_module("motor_nao_auditado")

    def test_repository_persists_an_auditable_calculation_lifecycle(self) -> None:
        repository = CalculationRepository()
        calculation_id = repository.create(
            attendance_id=self.attendance_id,
            calculation_type="planejamento_rgps",
            title="Planejamento preliminar",
            inputs={"contribuicoes": 180, "observacao": "Conferir CNIS"},
            ruleset_version="pendente-de-revisao-juridica",
        )
        repository.save_result(calculation_id, {"notice": "Resultado exige revisão humana."})

        records = repository.list_for_attendance(self.attendance_id)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].status, "aguardando_revisao")
        self.assertTrue(records[0].requires_human_review)
        self.assertEqual(records[0].inputs["contribuicoes"], 180)
        self.assertEqual(records[0].result["notice"], "Resultado exige revisão humana.")
        repository.mark_reviewed(calculation_id, "CNIS conferido; manter validação final da advogada.")
        reviewed = repository.list_for_attendance(self.attendance_id)[0]
        self.assertEqual(reviewed.status, "revisado")
        self.assertEqual(reviewed.review_notes, "CNIS conferido; manter validação final da advogada.")
        self.assertIsNotNone(reviewed.reviewed_at)


if __name__ == "__main__":
    unittest.main()
