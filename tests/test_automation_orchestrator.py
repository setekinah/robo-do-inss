from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import database
from automation_orchestrator import process_event, receive_and_process_event, receive_event


class AutomationOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = Path(self.temporary_directory.name) / "automation.db"
        database.init_database()
        self.attendance_id = database.save_attendance(
            lead_name="Maria da Silva",
            lead_phone="11999999999",
            lead_email="maria@example.com",
            lead_source="Site",
            flow_id="aposentadoria",
            flow_name="Aposentadoria",
            status="aprovado",
            result_title="Caso qualificado",
            summary="Triagem concluída.",
            next_step="Revisar documentos.",
            notes="",
            history=[],
        )

    def tearDown(self) -> None:
        database.DB_PATH = self.original_db_path
        self.temporary_directory.cleanup()

    def test_duplicate_publication_creates_only_one_reviewable_task(self) -> None:
        first = receive_event(
            event_type="publication.received",
            source="publicacoes",
            attendance_id=self.attendance_id,
            external_reference="pub-2026-001",
            payload={"summary": "Intimação disponibilizada para análise."},
        )
        duplicate = receive_event(
            event_type="publication.received",
            source="publicacoes",
            attendance_id=self.attendance_id,
            external_reference="pub-2026-001",
            payload={"summary": "Conteúdo repetido não deve criar outra tarefa."},
        )

        self.assertTrue(first.created)
        self.assertFalse(duplicate.created)
        self.assertEqual(first.event_id, duplicate.event_id)

        result = process_event(first.event_id)
        repeated_processing = process_event(first.event_id)
        tasks = database.list_crm_tasks(self.attendance_id)

        self.assertEqual(result.status, "concluido")
        self.assertEqual(repeated_processing.status, "ignorado")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["priority"], "alta")
        self.assertEqual(tasks[0]["review_status"], "pendente")
        self.assertIn("não um prazo fatal", tasks[0]["description"])

        audit_actions = {
            row["action"] for row in database.list_integration_audit(first.event_id)
        }
        self.assertEqual(audit_actions, {"evento_recebido", "tarefa_criada"})

    def test_review_gate_blocks_completion_until_human_approval(self) -> None:
        result = receive_and_process_event(
            event_type="inss.requirement.detected",
            source="meu_inss",
            attendance_id=self.attendance_id,
            external_reference="exigencia-123",
            payload={
                "summary": "Apresentar documentos complementares.",
                "suggested_due_at": "2026-08-15",
            },
        )
        task = database.list_crm_tasks(self.attendance_id)[0]

        with self.assertRaises(ValueError):
            database.complete_crm_task(int(task["id"]))

        database.review_crm_task(
            task_id=int(task["id"]),
            approved=True,
            due_at="2026-08-18",
        )
        database.complete_crm_task(int(task["id"]))
        reviewed_task = database.list_crm_tasks(self.attendance_id, include_done=True)[0]

        self.assertEqual(result.status, "concluido")
        self.assertEqual(reviewed_task["review_status"], "aprovada")
        self.assertEqual(reviewed_task["status"], "concluida")
        self.assertEqual(reviewed_task["due_at"], "2026-08-18")

    def test_qualified_lead_sets_next_action_without_review_gate(self) -> None:
        result = receive_and_process_event(
            event_type="lead.qualified",
            source="triagem_crm",
            attendance_id=self.attendance_id,
            external_reference=f"triagem-{self.attendance_id}",
            payload={"summary": "Lead aprovado pela triagem previdenciária."},
        )
        task = database.list_crm_tasks(self.attendance_id)[0]
        attendance = database.get_attendance_details(self.attendance_id)

        self.assertEqual(result.status, "concluido")
        self.assertEqual(task["review_status"], "nao_aplicavel")
        self.assertEqual(task["task_type"], "triagem_inicial")
        self.assertEqual(attendance["next_action"], task["title"])
        self.assertEqual(attendance["next_action_at"], task["due_at"])

    def test_unknown_event_type_and_missing_case_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            receive_event(
                event_type="astrea.activity.created",
                source="astrea",
                attendance_id=self.attendance_id,
            )
        with self.assertRaises(ValueError):
            receive_event(
                event_type="publication.received",
                source="publicacoes",
                attendance_id=99999,
            )

    def test_event_payload_is_auditable_json(self) -> None:
        receipt = receive_event(
            event_type="process.movement.received",
            source="datajud",
            attendance_id=self.attendance_id,
            external_reference="mov-42",
            payload={"summary": "Juntada de documento", "code": 85},
        )
        event = database.get_integration_event(receipt.event_id)

        self.assertEqual(json.loads(event["payload_json"])["code"], 85)
        self.assertEqual(event["event_key"], receipt.event_key)


if __name__ == "__main__":
    unittest.main()
