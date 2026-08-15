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

    def test_nit_requires_a_valid_check_digit(self) -> None:
        valid = intelligence.extract_structured_fields(
            "NIT/PIS: 123.45678.90-0",
            ["nit"],
        )
        invalid = intelligence.extract_structured_fields(
            "NIT/PIS: 123.45678.90-1",
            ["nit"],
        )

        self.assertEqual(valid["nit"], "123.45678.90-0")
        self.assertEqual(invalid["nit"], "")

    def test_competencies_do_not_capture_birth_or_issue_dates(self) -> None:
        text = (
            "Data de nascimento: 15/03/1958\n"
            "Data de emissao: 02/08/2026\n"
            "Competencia: 01/2020 a 12/2024"
        )

        result = intelligence.extract_structured_fields(text, ["competencias"])

        self.assertEqual(result["competencias"], "01/2020 | 12/2024")

    def test_cnis_report_only_exposes_documented_links_and_warnings(self) -> None:
        text = (
            "Nome do segurado: Cliente de Teste\n"
            "CPF: 529.982.247-25\n"
            "Data de nascimento: 10/05/1970\n"
            "Empresa: Alfa Servicos Ltda\n"
            "Admissao: 01/02/2010\n"
            "Rescisao: 31/01/2012\n"
            "Indicador: PEXT\n"
            "Competencias: 01/2010 02/2010 03/2010\n"
        )
        fields = intelligence.extract_structured_fields(
            text, ["nome", "cpf", "nit", "data_nascimento"]
        )
        report = intelligence.build_cnis_report(text, fields)

        self.assertEqual(len(report["vinculos"]), 1)
        self.assertEqual(report["vinculos"][0]["empregador"], "Alfa Servicos Ltda")
        self.assertEqual(report["metricas"]["alertas_contagem"], 1)
        self.assertEqual(report["metricas"]["rmi_estimada"], "Nao calculada")
        self.assertIn("preliminar", report["metricas"]["carencia_nota"])
        self.assertNotIn("inicio_data", report["vinculos"][0])

    def test_name_extraction_accepts_cnis_label_and_next_line_value(self) -> None:
        fields = intelligence.extract_structured_fields(
            "NOME DO FILIADO\nMARIA APARECIDA DOS SANTOS\nCPF: 529.982.247-25",
            ["nome", "cpf"],
        )

        self.assertEqual(fields["nome"], "MARIA APARECIDA DOS SANTOS")
        self.assertEqual(fields["cpf"], "529.982.247-25")

    def test_identity_document_is_not_classified_as_cnis(self) -> None:
        text = (
            "DEPARTAMENTO\nNILSON PAULO DA SILVA\nNOME\n"
            "DOC. IDENTIDADE / ORGAO EMISSOR / UF\n8654541 SSP/SP\n"
            "029.132.448-74 CPF\n30/08/1961 DATA NASCIMENTO"
        )
        classification = intelligence.classify_document("04.4-CHN.pdf", text)
        fields = intelligence.extract_document_fields(classification["code"], text)
        values = {field["key"]: field["value"] for field in fields}

        self.assertEqual(classification["code"], "RG")
        self.assertEqual(values["nome"], "NILSON PAULO DA SILVA")
        self.assertEqual(values["data_nascimento"], "30/08/1961")
        self.assertEqual(values["rg"], "8654541")

    def test_classification_does_not_turn_ctps_with_nit_into_cnis(self) -> None:
        text = (
            "CARTEIRA DE TRABALHO E PREVIDENCIA SOCIAL\n"
            "CTPS\nNome: MARIA APARECIDA DOS SANTOS\n"
            "NIT: 123.45678.90-0\nEmpresa: Alfa Servicos\nAdmissao: 01/02/2020"
        )

        classification = intelligence.classify_document("carteira-trabalho.pdf", text)
        fields = intelligence.extract_document_fields(classification["code"], text)
        assessment = intelligence.assess_document_extraction(
            classification, fields, raw_text=text, source_confidence=0.94
        )

        self.assertEqual(classification["code"], "CTPS")
        self.assertEqual(assessment["status"], "extraido")

    def test_document_specific_fields_support_medical_report(self) -> None:
        text = (
            "RELATORIO MEDICO\nNome completo: ANA MARIA SOUZA\n"
            "CID: M54.5\nCRM-SP: 123456"
        )

        classification = intelligence.classify_document("laudo.pdf", text)
        fields = intelligence.extract_document_fields(classification["code"], text)
        values = {field["key"]: field["value"] for field in fields}
        assessment = intelligence.assess_document_extraction(
            classification, fields, raw_text=text, source_confidence=0.91
        )

        self.assertEqual(classification["code"], "LAUDO_MEDICO")
        self.assertEqual(values["cid"], "M54.5")
        self.assertEqual(values["crm_medico"], "123456")
        self.assertEqual(assessment["status"], "extraido")

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
