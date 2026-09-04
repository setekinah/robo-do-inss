import os
import unittest
from unittest.mock import patch

from modules.notification_dispatcher import build_minimal_payload, dispatch


class NotificationDispatcherTests(unittest.TestCase):
    def test_payload_excludes_client_and_document_data(self):
        payload = build_minimal_payload(event_type="dossie_requer_revisao", attendance_id=42, event_id="evt-42")

        self.assertEqual(payload["case_id"], 42)
        self.assertNotIn("cpf", payload)
        self.assertNotIn("cnis", payload)
        self.assertNotIn("cliente", payload)

    def test_dispatch_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            result = dispatch(event_type="pendencia_inteligente", attendance_id=7, event_id="evt-7")

        self.assertEqual(result["reason"], "notificacoes_desativadas")
        self.assertFalse(result["sent"])

    def test_destination_requires_https_allowlist_and_secret(self):
        environment = {
            "ROBO_INSS_NOTIFICATION_ENABLED": "1",
            "ROBO_INSS_NOTIFICATION_WEBHOOK_URL": "http://example.test/hook",
            "ROBO_INSS_NOTIFICATION_ALLOWED_HOSTS": "example.test",
            "ROBO_INSS_NOTIFICATION_WEBHOOK_SECRET": "segredo",
        }
        with patch.dict(os.environ, environment, clear=True):
            result = dispatch(event_type="pendencia_inteligente", attendance_id=7, event_id="evt-7")

        self.assertEqual(result["reason"], "destino_nao_autorizado")


if __name__ == "__main__":
    unittest.main()
