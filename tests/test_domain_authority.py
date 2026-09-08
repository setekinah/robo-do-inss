"""Regressões D0.2 para a autoridade server-side dos estados legados."""

from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

import api_server
import auth_security
import database
import office_settings


class _ServerFixture:
    def __init__(self) -> None:
        self.httpd = api_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), api_server.SofiPreviRequestHandler
        )
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def request(self, method: str, path: str, body: dict | None = None, cookie: str | None = None) -> tuple[int, dict]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        encoded = json.dumps(body).encode("utf-8") if body is not None else None
        try:
            connection.request(method, path, body=encoded, headers=headers)
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload
        finally:
            connection.close()

    def register(self) -> str:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(
                "POST",
                "/api/auth/register",
                body=json.dumps(
                    {
                        "email": "advogada@exemplo.com.br",
                        "password": "SenhaForte2026",
                        "office_name": "Escritório Exemplo",
                        "oab": "12345",
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            response.read()
            if response.status != 201:
                raise AssertionError("Não foi possível criar a sessão de teste.")
            return str(response.getheader("Set-Cookie")).split(";", 1)[0]
        finally:
            connection.close()

    def shutdown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class DomainAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.original_credentials_path = auth_security.CREDENTIALS_PATH
        cls.original_settings_path = office_settings.SETTINGS_PATH
        cls.original_db_path = database.DB_PATH
        cls.original_sessions = dict(auth_security._SESSIONS)
        auth_security.CREDENTIALS_PATH = Path(cls.temp_dir.name) / "auth.json"
        office_settings.SETTINGS_PATH = Path(cls.temp_dir.name) / "office.json"
        database.DB_PATH = Path(cls.temp_dir.name) / "domain_authority.db"
        auth_security._SESSIONS.clear()
        database.init_database()
        cls.server = _ServerFixture()
        cls.cookie = cls.server.register()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        auth_security.CREDENTIALS_PATH = cls.original_credentials_path
        office_settings.SETTINGS_PATH = cls.original_settings_path
        database.DB_PATH = cls.original_db_path
        auth_security._SESSIONS.clear()
        auth_security._SESSIONS.update(cls.original_sessions)
        cls.temp_dir.cleanup()

    def _create_attendance(self) -> int:
        status, payload = self.server.request(
            "POST",
            "/api/atendimentos",
            {
                "lead_name": "Cliente de teste",
                "lead_phone": "11999999999",
                "lead_email": "cliente@example.com.br",
                "lead_source": "teste",
                "flow_id": "aposentadoria",
                "status": "revisao",
                # Campo legado ainda é aceito para compatibilidade, mas a API
                # deriva o estágio e não o toma como autoridade.
                "crm_stage": "triagem",
            },
            self.cookie,
        )
        self.assertEqual(status, 201, payload)
        return int(payload["id"])

    def _create_relationship_attendance(self) -> int:
        status, payload = self.server.request(
            "POST",
            "/api/atendimentos",
            {
                "lead_name": "Lead para reativação",
                "lead_phone": "11999999998",
                "flow_id": "aposentadoria",
                "status": "desqualificado",
                "crm_stage": "relacionamento",
                "relationship_status": "aguardando_revisao",
            },
            self.cookie,
        )
        self.assertEqual(status, 201, payload)
        return int(payload["id"])

    def test_invalid_stage_is_rejected(self) -> None:
        attendance_id = self._create_attendance()
        status, payload = self.server.request(
            "PUT", f"/api/atendimentos/{attendance_id}/stage", {"stage": "qualquer_coisa"}, self.cookie
        )
        self.assertEqual(status, 422)
        self.assertIn("Etapa", payload["error"])

    def test_impossible_stage_transition_is_rejected(self) -> None:
        attendance_id = self._create_attendance()
        status, payload = self.server.request(
            "PUT", f"/api/atendimentos/{attendance_id}/stage", {"stage": "concluido"}, self.cookie
        )
        self.assertEqual(status, 409)
        self.assertIn("Transição", payload["error"])

    def test_missing_attendance_returns_404_for_stage_transition(self) -> None:
        status, payload = self.server.request(
            "PUT", "/api/atendimentos/999999/stage", {"stage": "qualificacao"}, self.cookie
        )
        self.assertEqual(status, 404)
        self.assertIn("não encontrado", payload["error"].lower())

    def test_post_rejects_arbitrary_stage_and_status(self) -> None:
        base_payload = {
            "lead_name": "Cliente",
            "lead_phone": "11999999999",
            "flow_id": "aposentadoria",
        }
        status, _ = self.server.request(
            "POST", "/api/atendimentos", {**base_payload, "crm_stage": "admin"}, self.cookie
        )
        self.assertEqual(status, 422)
        status, _ = self.server.request(
            "POST", "/api/atendimentos", {**base_payload, "status": "decidido_pelo_cliente"}, self.cookie
        )
        self.assertEqual(status, 422)

    def test_conflict_and_privacy_require_explicit_valid_input(self) -> None:
        attendance_id = self._create_attendance()
        status, _ = self.server.request(
            "POST", f"/api/atendimentos/{attendance_id}/conflito", {}, self.cookie
        )
        self.assertEqual(status, 422)
        status, _ = self.server.request(
            "POST", f"/api/atendimentos/{attendance_id}/lgpd", {"legal_basis": ""}, self.cookie
        )
        self.assertEqual(status, 422)

    def test_reactivation_only_allows_the_relationship_lead_state(self) -> None:
        relationship_id = self._create_relationship_attendance()
        status, payload = self.server.request(
            "POST", f"/api/atendimentos/{relationship_id}/reativar", {}, self.cookie
        )
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["stage"], "triagem")
        details = database.get_attendance_details(relationship_id)
        self.assertEqual(details["status"], "revisao")
        with database.get_connection() as conn:
            relationship_status = conn.execute(
                "SELECT relationship_status FROM atendimentos WHERE id = ?", (relationship_id,)
            ).fetchone()["relationship_status"]
        self.assertEqual(relationship_status, "reativado")

        status, _ = self.server.request(
            "POST", f"/api/atendimentos/{relationship_id}/reativar", {}, self.cookie
        )
        self.assertEqual(status, 409)
        unchanged = database.get_attendance_details(relationship_id)
        self.assertEqual(unchanged["status"], "revisao")
        self.assertEqual(unchanged["crm_stage"], "triagem")

    def test_reactivation_rejects_non_relationship_stages_without_mutation(self) -> None:
        attendance_id = self._create_attendance()
        for stage in ("triagem", "documentos", "caso_ativo", "concluido", "encerrado"):
            with database.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE atendimentos
                    SET status = 'revisao', crm_stage = ?, relationship_status = 'nao_aplicavel'
                    WHERE id = ?
                    """,
                    (stage, attendance_id),
                )
            status, _ = self.server.request(
                "POST", f"/api/atendimentos/{attendance_id}/reativar", {}, self.cookie
            )
            self.assertEqual(status, 409, stage)
            details = database.get_attendance_details(attendance_id)
            self.assertEqual(details["crm_stage"], stage)
            self.assertEqual(details["status"], "revisao")

    def test_reactivation_returns_404_for_unknown_attendance(self) -> None:
        status, _ = self.server.request("POST", "/api/atendimentos/999999/reativar", {}, self.cookie)
        self.assertEqual(status, 404)

    def test_lgpd_requires_explicit_acknowledgement_and_persists_only_on_success(self) -> None:
        attendance_id = self._create_attendance()
        for payload in (
            {"legal_basis": "procedimentos_preliminares"},
            {"legal_basis": "procedimentos_preliminares", "privacy_notice_acknowledged": False},
            {"privacy_notice_acknowledged": True},
        ):
            status, _ = self.server.request("POST", f"/api/atendimentos/{attendance_id}/lgpd", payload, self.cookie)
            self.assertEqual(status, 422)
            unchanged = database.get_attendance_details(attendance_id)
            self.assertEqual(unchanged["privacy_notice_acknowledged"], 0)
            self.assertFalse(unchanged["privacy_legal_basis"])
            self.assertIsNone(unchanged["privacy_acknowledged_at"])

        status, payload = self.server.request(
            "POST",
            f"/api/atendimentos/{attendance_id}/lgpd",
            {"legal_basis": "procedimentos_preliminares", "privacy_notice_acknowledged": True},
            self.cookie,
        )
        self.assertEqual(status, 200, payload)
        details = database.get_attendance_details(attendance_id)
        self.assertEqual(details["privacy_notice_acknowledged"], 1)
        self.assertEqual(details["privacy_legal_basis"], "procedimentos_preliminares")
        self.assertIsNotNone(details["privacy_acknowledged_at"])

    def test_empty_task_and_activity_do_not_create_placeholder_facts(self) -> None:
        attendance_id = self._create_attendance()
        status, payload = self.server.request(
            "POST", f"/api/atendimentos/{attendance_id}/tarefas", {}, self.cookie
        )
        self.assertEqual(status, 422)
        self.assertNotIn("Retornar ao cliente", payload["error"])
        status, payload = self.server.request(
            "POST", f"/api/atendimentos/{attendance_id}/atividades", {}, self.cookie
        )
        self.assertEqual(status, 422)
        self.assertNotIn("Interacao registrada", payload["error"])

    def test_valid_existing_paths_remain_operational(self) -> None:
        attendance_id = self._create_attendance()
        status, payload = self.server.request(
            "PUT", f"/api/atendimentos/{attendance_id}/stage", {"stage": "qualificacao"}, self.cookie
        )
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["stage"], "qualificacao")

        status, payload = self.server.request(
            "POST",
            f"/api/atendimentos/{attendance_id}/conflito",
            {"status": "liberado", "notes": "Consulta concluída.", "parties": "Cliente e empresa"},
            self.cookie,
        )
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["conflict_status"], "liberado")

        status, payload = self.server.request(
            "POST",
            f"/api/atendimentos/{attendance_id}/lgpd",
            {"legal_basis": "procedimentos_preliminares", "privacy_notice_acknowledged": True},
            self.cookie,
        )
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["privacy_legal_basis"], "procedimentos_preliminares")

        status, _ = self.server.request(
            "POST", f"/api/atendimentos/{attendance_id}/tarefas", {"title": "Revisar CNIS"}, self.cookie
        )
        self.assertEqual(status, 200)
        status, _ = self.server.request(
            "POST",
            f"/api/atendimentos/{attendance_id}/atividades",
            {"activity_type": "nota", "body": "Cliente contatado."},
            self.cookie,
        )
        self.assertEqual(status, 200)

        details = database.get_attendance_details(attendance_id)
        self.assertEqual(details["crm_stage"], "qualificacao")
        self.assertEqual(details["conflict_status"], "liberado")
        self.assertEqual(details["privacy_legal_basis"], "procedimentos_preliminares")


if __name__ == "__main__":
    unittest.main()
