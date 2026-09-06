from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import database


class ClientPortalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = Path(self.temporary_directory.name) / "portal.db"
        database.init_database()
        self.attendance_id = database.save_attendance(
            lead_name="Maria de Souza",
            lead_phone="11999999999",
            flow_id="aposentadoria",
            flow_name="Aposentadoria",
            status="aprovado",
            result_title="Análise",
            summary="Não deve sair pelo portal.",
            next_step="CPF e CNIS precisam de revisão interna.",
            notes="Dados sensíveis.",
            history=[],
        )

    def tearDown(self) -> None:
        database.DB_PATH = self.original_db_path
        self.temporary_directory.cleanup()

    def test_view_is_minimized_and_token_is_not_persisted_in_plaintext(self) -> None:
        access = database.create_client_portal_access(self.attendance_id)
        portal = database.get_client_portal_view(access["access_token"])

        self.assertEqual(portal["cliente"], "Maria")
        self.assertEqual(portal["beneficio"], "Aposentadoria")
        self.assertNotIn("precisam de revisão interna", portal["proxima_etapa"])
        self.assertNotIn("11999999999", str(portal))
        with database.get_connection() as conn:
            stored = conn.execute("SELECT token_hash FROM client_portal_access").fetchone()["token_hash"]
        self.assertNotEqual(stored, access["access_token"])

    def test_new_link_revokes_the_previous_link(self) -> None:
        first = database.create_client_portal_access(self.attendance_id)
        second = database.create_client_portal_access(self.attendance_id)

        self.assertIsNone(database.get_client_portal_view(first["access_token"]))
        self.assertIsNotNone(database.get_client_portal_view(second["access_token"]))


if __name__ == "__main__":
    unittest.main()
