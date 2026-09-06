"""Regressões P0.3: o handler de OCR não deve conter código morto ou dados fictícios."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP_JS = ROOT / "app.js"


class OCRDeadCodeRemovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = APP_JS.read_text(encoding="utf-8")

    def test_handle_ocr_only_delegates_to_real_processor(self) -> None:
        pattern = (
            r"async handleOCRFileUpload\(file\)\s*\{"
            r"\s*if \(!file\) return;"
            r"\s*return this\.processOCRUpload\(file\);"
            r"\s*\}"
        )

        self.assertRegex(self.app, pattern)

    def test_real_ocr_processor_still_exists(self) -> None:
        self.assertIn(
            "async processOCRUpload(file) {",
            self.app,
        )

        self.assertIn(
            "formData.append('file', file, file.name);",
            self.app,
        )

        self.assertIn(
            "fetch('/api/documentos/analisar'",
            self.app,
        )

    def test_dead_ocr_fake_data_is_absent(self) -> None:
        forbidden = (
            "MARIA DAS DORES SILVA",
            "384.912.847-19",
            "128.94827.12-4",
            "98.7%",
            "RapidOCR + ONNX Engine local",
            "CLIENTE PROCESSADO LOCALMENTE",
            "32 anos, 2 meses e 15 dias",
            "386 contribuições",
            "Apto para Aposentadoria por Idade Urbana",
        )

        for value in forbidden:
            self.assertNotIn(value, self.app)


if __name__ == "__main__":
    unittest.main()
