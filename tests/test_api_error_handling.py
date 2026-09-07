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


class ApiErrorHandlingTests(unittest.TestCase):
    def test_request_helper_handles_network_and_non_json_responses(self) -> None:
        self.assertIn("async function requestJson", APP_JS)
        self.assertIn("API_NETWORK_MESSAGE", APP_JS)
        self.assertIn("await response.json()", APP_JS)
        self.assertIn("Resposta inválida da API.", APP_JS)
        self.assertIn("data === null", APP_JS)

    def test_safe_backend_messages_are_used_without_exposing_technical_content(self) -> None:
        self.assertIn("function safeBackendMessage", APP_JS)
        self.assertIn("data?.error", APP_JS)
        self.assertIn("data?.message", APP_JS)
        self.assertRegex(APP_JS, r"traceback.*failed to fetch.*unexpected token")
        self.assertNotIn("alert(error.message", APP_JS)
        self.assertNotIn("textContent=error.message", APP_JS)

    def test_http_statuses_have_friendly_fallbacks(self) -> None:
        for status in ("401", "403", "404", "409", "413", "429"):
            self.assertIn(f"{status}:", APP_JS)
        self.assertIn("O servidor encontrou um problema. Tente novamente em instantes.", APP_JS)

    def test_p0_6_operations_use_the_standardized_handler(self) -> None:
        for name, next_name in (
            ("advanceStage", "openLeadModal"),
            ("addActivity", "renderModalDocs"),
            ("toggleDocStatus", "loadModalContract"),
        ):
            body = function_body(name, next_name)
            self.assertIn("requestJson(", body)
            self.assertIn("showUserError(", body)

    def test_authentication_and_upload_use_the_standardized_handler(self) -> None:
        self.assertIn("requestJson('/api/auth/status'", APP_JS)
        self.assertIn("requestJson('/api/auth/register'", APP_JS)
        self.assertIn("requestJson('/api/auth/login'", APP_JS)
        upload = function_body("uploadCaseDocument", "toggleDocStatus")
        self.assertGreaterEqual(upload.count("requestJson("), 2)
        self.assertIn("showUserError(error", upload)

    def test_p0_6_regression_test_remains_present(self) -> None:
        self.assertTrue((Path(__file__).resolve().parent / "test_ui_db_consistency.py").exists())


if __name__ == "__main__":
    unittest.main()
