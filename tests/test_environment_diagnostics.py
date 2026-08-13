from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.environment_diagnostics import build_environment_diagnostic


class EnvironmentDiagnosticsTests(unittest.TestCase):
    def test_reports_ready_environment_without_exposing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = build_environment_diagnostic(
                Path(directory) / "data", Path(directory) / "data" / "triagem.db",
                lambda: {"pdf_ready": True, "neural_ready": True, "tesseract_ready": False, "privacy_mode": "local"},
            )
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["privacy_mode"], "local")
        self.assertEqual({item["key"] for item in result["checks"]}, {"python", "data_directory", "sqlite", "pdf", "neural_ocr", "tesseract"})
        self.assertFalse(any(directory in item["detail"] for item in result["checks"]))

    def test_reports_missing_document_dependencies_as_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = build_environment_diagnostic(
                Path(directory) / "data", Path(directory) / "data" / "triagem.db",
                lambda: {"pdf_ready": False, "neural_ready": False, "tesseract_ready": False, "privacy_mode": "local"},
            )
        self.assertEqual(result["status"], "error")
        pdf = next(item for item in result["checks"] if item["key"] == "pdf")
        self.assertEqual(pdf["status"], "error")
        self.assertIn("Reinstale", pdf["detail"])


if __name__ == "__main__":
    unittest.main()
