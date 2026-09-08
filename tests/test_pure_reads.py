"""D0.3: leituras HTTP não podem materializar ou alterar o dossiê."""

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


class _Server:
    def __init__(self) -> None:
        self.httpd = api_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), api_server.SofiPreviRequestHandler
        )
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def request(self, path: str, cookie: str) -> tuple[int, object]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request("GET", path, headers={"Cookie": cookie})
            response = connection.getresponse()
            return response.status, json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()

    def register(self) -> str:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            payload = {
                "email": "advogada@exemplo.com.br",
                "password": "SenhaForte2026",
                "office_name": "Escritório Exemplo",
                "oab": "12345",
            }
            connection.request(
                "POST", "/api/auth/register", body=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            response.read()
            if response.status != 201:
                raise AssertionError("Não foi possível criar a sessão de teste.")
            return str(response.getheader("Set-Cookie")).split(";", 1)[0]
        finally:
            connection.close()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class PureReadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.original_db_path = database.DB_PATH
        cls.original_credentials_path = auth_security.CREDENTIALS_PATH
        cls.original_settings_path = office_settings.SETTINGS_PATH
        cls.original_sessions = dict(auth_security._SESSIONS)
        database.DB_PATH = Path(cls.temp_dir.name) / "pure_reads.db"
        auth_security.CREDENTIALS_PATH = Path(cls.temp_dir.name) / "auth.json"
        office_settings.SETTINGS_PATH = Path(cls.temp_dir.name) / "office.json"
        auth_security._SESSIONS.clear()
        database.init_database()
        cls.server = _Server()
        cls.cookie = cls.server.register()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.close()
        database.DB_PATH = cls.original_db_path
        auth_security.CREDENTIALS_PATH = cls.original_credentials_path
        office_settings.SETTINGS_PATH = cls.original_settings_path
        auth_security._SESSIONS.clear()
        auth_security._SESSIONS.update(cls.original_sessions)
        cls.temp_dir.cleanup()

    def _save(self, status: str) -> int:
        return database.save_attendance(
            lead_name="Cliente sem checklist",
            lead_phone="11999999999",
            flow_id="aposentadoria",
            flow_name="Aposentadoria",
            status=status,
            result_title="Triagem",
            summary="",
            next_step="",
            notes="",
            history=[],
        )

    @staticmethod
    def _counts(attendance_id: int) -> tuple[int, int, int, int]:
        with database.get_connection() as conn:
            return tuple(
                int(conn.execute(query, (attendance_id,)).fetchone()[0])
                for query in (
                    "SELECT COUNT(*) FROM atendimento_documentos WHERE attendance_id = ?",
                    "SELECT COUNT(*) FROM crm_tarefas WHERE attendance_id = ?",
                    "SELECT COUNT(*) FROM crm_atividades WHERE attendance_id = ?",
                    "SELECT COUNT(*) FROM atendimento_auditorias WHERE attendance_id = ?",
                )
            )

    def test_get_attendance_is_pure_and_never_materializes_a_checklist(self) -> None:
        attendance_id = self._save("desqualificado")
        before = self._counts(attendance_id)

        for _ in range(2):
            status, payload = self.server.request(f"/api/atendimentos/{attendance_id}", self.cookie)
            self.assertEqual(status, 200, payload)
            self.assertEqual(payload["documents"], [])
            self.assertEqual(self._counts(attendance_id), before)

        self.assertEqual(before, (0, 0, 0, 0))

    def test_get_documents_is_pure_and_returns_empty_list_for_existing_attendance(self) -> None:
        attendance_id = self._save("pendente_documental")
        before = self._counts(attendance_id)

        for _ in range(2):
            status, payload = self.server.request(f"/api/atendimentos/{attendance_id}/documentos", self.cookie)
            self.assertEqual(status, 200, payload)
            self.assertEqual(payload, [])
            self.assertEqual(self._counts(attendance_id), before)

        self.assertEqual(before, (0, 0, 0, 0))

    def test_get_documents_returns_404_for_unknown_attendance(self) -> None:
        status, payload = self.server.request("/api/atendimentos/999999/documentos", self.cookie)
        self.assertEqual(status, 404)
        self.assertIn("não encontrado", payload["error"].lower())

    def test_write_materialization_and_bootstrap_backfill_remain_idempotent(self) -> None:
        approved_id = self._save("aprovado")
        revision_id = self._save("revisao")
        approved_count = self._counts(approved_id)[0]
        revision_count = self._counts(revision_id)[0]
        self.assertGreater(approved_count, 0)
        self.assertGreater(revision_count, 0)

        with database.get_connection() as conn:
            database.backfill_document_checklists(conn)
            database.backfill_document_checklists(conn)

        self.assertEqual(self._counts(approved_id)[0], approved_count)
        self.assertEqual(self._counts(revision_id)[0], revision_count)


if __name__ == "__main__":
    unittest.main()
