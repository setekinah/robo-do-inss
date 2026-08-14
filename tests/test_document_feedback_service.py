from __future__ import annotations

import unittest

from services.document_feedback_service import build_document_feedback


class DocumentFeedbackServiceTests(unittest.TestCase):
    def test_feedback_covers_operational_document_states(self) -> None:
        self.assertEqual(build_document_feedback("extraido", 0.90)["level"], "success")
        self.assertEqual(build_document_feedback("parcial", 0.50)["level"], "warning")
        self.assertEqual(build_document_feedback("dependencia_ausente")["level"], "warning")
        self.assertEqual(build_document_feedback("erro")["level"], "error")
        self.assertIn("Anexe", build_document_feedback("nao_processado")["message"])


if __name__ == "__main__":
    unittest.main()
