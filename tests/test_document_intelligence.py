from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf
from PIL import Image, ImageDraw, ImageFilter

import document_intelligence as intelligence


class DocumentIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.temp_dir = Path(self.temporary_directory.name)
        intelligence._extract_text_cached.cache_clear()
        intelligence.get_rapidocr_engine.cache_clear()

    def tearDown(self) -> None:
        intelligence._extract_text_cached.cache_clear()
        intelligence.get_rapidocr_engine.cache_clear()
        self.temporary_directory.cleanup()

    def create_native_pdf(self, name: str = "native.pdf") -> Path:
        target = self.temp_dir / name
        document = pymupdf.open()
        page = document.new_page()
        page.insert_textbox(
            pymupdf.Rect(60, 60, 530, 500),
            (
                "CADASTRO PREVIDENCIARIO\n"
                "Nome: Cliente de Teste\n"
                "CPF: 529.982.247-25\n"
                "Data de nascimento: 10/05/1970\n"
                "Indicador PEXT vinculo pendente de comprovacao.\n"
            ),
            fontsize=12,
        )
        document.save(target)
        document.close()
        return target

    def create_scanned_pdf(self, name: str = "scan.pdf") -> Path:
        target = self.temp_dir / name
        image = Image.new("RGB", (1400, 1900), "white")
        draw = ImageDraw.Draw(image)
        draw.text((120, 160), "COMPROVANTE DE RESIDENCIA", fill="black")
        draw.text((120, 240), "Endereco: Rua Exemplo, 100", fill="black")
        image.filter(ImageFilter.GaussianBlur(radius=0.3)).save(target, "PDF", resolution=170)
        return target

    def test_native_pdf_uses_fast_text_layer_without_ocr(self) -> None:
        target = self.create_native_pdf()

        with patch.object(intelligence, "run_ocr_image") as mocked_ocr:
            result = intelligence.extract_text_from_pdf(target)

        mocked_ocr.assert_not_called()
        self.assertEqual(result["source_type"], "pdf_nativo_pymupdf")
        self.assertIn("Cliente de Teste", result["text"])
        self.assertGreater(result["source_confidence"], 0.90)

    def test_scanned_pdf_renders_page_and_uses_neural_ocr(self) -> None:
        target = self.create_scanned_pdf()
        mocked_result = {
            "text": "Endereco: Rua Exemplo, 100\nData de emissao: 01/08/2026",
            "confidence": 0.91,
            "source_type": "imagem_ocr_neural",
            "technical_note": "OCR neural simulado.",
            "dependency_missing": False,
            "hard_failure": False,
        }

        with patch.object(intelligence, "run_ocr_image", return_value=mocked_result) as mocked_ocr:
            result = intelligence.extract_text_from_pdf(target)

        self.assertEqual(mocked_ocr.call_count, 1)
        self.assertEqual(result["source_type"], "pdf_ocr_neural")
        self.assertIn("Rua Exemplo", result["text"])
        self.assertEqual(result["source_confidence"], 0.91)

    def test_low_confidence_neural_result_retries_enhanced_image(self) -> None:
        image = Image.new("RGB", (900, 1200), "#dddddd")
        weak = {"engine": "rapidocr", "text": "ruld0", "confidence": 0.31, "line_count": 1}
        strong = {
            "engine": "rapidocr",
            "text": "Laudo medico com informacao legivel",
            "confidence": 0.93,
            "line_count": 1,
        }

        with patch.object(intelligence, "ocr_with_rapidocr", side_effect=[weak, strong]) as mocked:
            result = intelligence.run_ocr_image(image, source_label="laudo degradado")

        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(result["text"], strong["text"])
        self.assertEqual(result["source_type"], "imagem_ocr_neural")
        self.assertGreater(result["confidence"], 0.90)
        self.assertIn("contraste adaptativo", result["technical_note"])

    def test_bundle_extracts_and_validates_critical_fields(self) -> None:
        target = self.create_native_pdf()

        result = intelligence.analyze_document_bundle(
            document_code="identidade",
            uploaded_files=[str(target)],
            critical_fields=["nome", "cpf", "data_nascimento", "indicadores"],
        )

        self.assertEqual(result["extracted_data"]["cpf"], "529.982.247-25")
        self.assertEqual(result["extracted_data"]["data_nascimento"], "10/05/1970")
        self.assertIn("PEXT", result["extracted_data"]["indicadores"])
        self.assertGreaterEqual(result["extraction_confidence"], 0.80)

    def test_invalid_cpf_is_not_accepted_as_a_critical_field(self) -> None:
        text = "Nome: Teste\nCPF: 111.111.111-11\nData de nascimento: 45/13/2020"

        result = intelligence.extract_structured_fields(text, ["cpf", "data_nascimento"])

        self.assertEqual(result["cpf"], "")
        self.assertEqual(result["data_nascimento"], "")

    def test_corrupted_pdf_reports_hard_failure_without_crashing(self) -> None:
        target = self.temp_dir / "corrupted.pdf"
        target.write_bytes(b"not a valid pdf")

        result = intelligence.extract_text_from_file(target)

        self.assertEqual(result["source_type"], "pdf_erro")
        self.assertTrue(result["hard_failure"])
        self.assertEqual(result["text"], "")

    def test_capabilities_report_local_privacy_mode(self) -> None:
        capabilities = intelligence.get_ocr_capabilities()

        self.assertTrue(capabilities["neural_ready"])
        self.assertTrue(capabilities["pdf_ready"])
        self.assertEqual(capabilities["privacy_mode"], "local")
        self.assertIn("RapidOCR", capabilities["packages"])


if __name__ == "__main__":
    unittest.main()
