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

    def test_cnis_table_layout_extracts_vinculos_without_empresa_label(self) -> None:
        text = (
            "1 50.604.552/0001-87 PEREIRA E MATSUBARA ADVOGADOS ASSOCIADOS Empregado ou Agente\n"
            "Publico 01/08/1979 21/10/1980\n"
            "2 60.746.948/0035-61 BANCO BRADESCO S.A. Empregado ou Agente\n"
            "Publico 24/10/1980 29/06/1985"
        )

        vinculos = intelligence.extract_cnis_vinculos(text)

        self.assertEqual(len(vinculos), 2)
        self.assertEqual(vinculos[0]["empregador"], "PEREIRA E MATSUBARA ADVOGADOS ASSOCIADOS")
        self.assertEqual(vinculos[0]["data_inicio"], "01/08/1979")
        self.assertEqual(vinculos[1]["data_fim"], "29/06/1985")

    def test_cnis_multisection_layout_keeps_contributions_and_indicators(self) -> None:
        # Caso anonimizado que reproduz o layout nativo de extrato CNIS:
        # tabela de empregadores, recolhimentos próprios e indicadores fora
        # da linha principal do vínculo. Nenhum dado pessoal é usado no teste.
        text = (
            "NIT: 123.45678.90-0 CPF: 529.982.247-25 Nome: PESSOA EXEMPLO SILVA\n"
            "Data de nascimento: 18/03/1988\n"
            "1 50.604.552/0001-87 EMPRESA EXEMPLO S.A. Empregado\n"
            "04/10/2004 09/02/2006\n"
            "2 Contribuinte Individual 01/11/2016 30/09/2017\n"
            "RECOLHIMENTO IREC-INDPEND IREC-MEI\n"
            "Competência 01/2017 02/2017 Indicador IREM-SEM-DIAS-INTERM PREM-FVIN"
        )
        fields = intelligence.extract_structured_fields(text, ["nome", "cpf", "nit", "data_nascimento"])
        report = intelligence.build_cnis_report(text, fields)

        self.assertEqual(fields["nome"], "PESSOA EXEMPLO SILVA")
        self.assertEqual(fields["data_nascimento"], "18/03/1988")
        self.assertEqual(len(report["vinculos"]), 2)
        self.assertEqual(report["vinculos"][1]["tipo_filiacao"], "Contribuinte Individual")
        self.assertEqual(report["metricas"]["alertas_contagem"], 4)
        self.assertIn("IREC-INDPEND", report["metricas"]["alertas_nota"])
        self.assertIn("localizadas", report["metricas"]["carencia_cumprida"])

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

    def test_identity_documents_use_specific_rg_cpf_and_cnh_schemas(self) -> None:
        cases = [
            (
                "identidade.pdf",
                "REGISTRO GERAL\nNome: ANA MARIA SOUZA\nCPF: 529.982.247-25\n"
                "RG: 123456789\nOrgao emissor: SSP/SP\nData de expedicao: 12/05/2020",
                "RG",
                {"rg": "123456789", "orgao_emissor": "SSP/SP"},
            ),
            (
                "comprovante-cpf.pdf",
                "COMPROVANTE DE SITUACAO CADASTRAL NO CPF\nRECEITA FEDERAL\n"
                "Nome: ANA MARIA SOUZA\nCPF: 529.982.247-25\nSituacao Cadastral: REGULAR\n"
                "Data de inscricao: 12/05/2001",
                "CPF",
                {"situacao_cadastral": "REGULAR"},
            ),
            (
                "cnh-digital.pdf",
                "CARTEIRA NACIONAL DE HABILITACAO\nNome: ANA MARIA SOUZA\nCPF: 529.982.247-25\n"
                "Numero de Registro: 12345678901\nCategoria: AB\nValidade: 30/06/2030\n"
                "Primeira Habilitacao: 20/03/2002\nDETRAN/SP",
                "CNH",
                {"numero_cnh": "12345678901", "categoria_cnh": "AB", "validade": "30/06/2030"},
            ),
        ]
        for file_name, text, expected_type, expected_fields in cases:
            with self.subTest(file_name=file_name):
                classification = intelligence.classify_document(file_name, text)
                fields = intelligence.extract_document_fields(classification["code"], text)
                values = {field["key"]: field["value"] for field in fields}
                self.assertEqual(classification["code"], expected_type)
                self.assertEqual(values["nome"], "ANA MARIA SOUZA")
                self.assertEqual(values["cpf"], "529.982.247-25")
                for key, value in expected_fields.items():
                    self.assertEqual(values[key], value)

    def test_signed_cnh_with_only_certificate_text_requires_visual_recovery(self) -> None:
        certificate_only = (
            "REPUBLICA FEDERATIVA DO BRASIL\nSECRETARIA NACIONAL DE TRANSITO\n"
            "Documento assinado com certificado digital. Validade confirmada pelo Assinador Serpro."
        )

        self.assertTrue(
            intelligence.needs_identity_visual_recovery(
                Path("05-CNH-cliente.pdf"), certificate_only, 0.10
            )
        )
        self.assertFalse(
            intelligence.needs_identity_visual_recovery(
                Path("05-CNH-cliente.pdf"), "CPF: 529.982.247-25", 0.10
            )
        )

    def test_cnh_ocr_column_order_uses_senatran_and_recovers_fields(self) -> None:
        text = (
            "SECRETARIA NACIONAL DE TRANSITO - SENATRAN\n"
            "CARTEIRA NACIONAL DE HABILITACAO\n"
            "2 E 1 NOME E SOBRENOME\nANA MARIA SOUZA\n"
            "4D CPF\n5 N° REGISTRO\n9 CAT HAB\n52998224725\n12345678901\nB\n"
            "30/06/2030 4B VALIDADE\n"
        )

        classification = intelligence.classify_document("05-CNH-cliente.pdf", text)
        fields = intelligence.extract_document_fields(classification["code"], text)
        values = {field["key"]: field["value"] for field in fields}

        self.assertEqual(classification["code"], "CNH")
        self.assertEqual(values["nome"], "ANA MARIA SOUZA")
        self.assertEqual(values["numero_cnh"], "12345678901")
        self.assertEqual(values["categoria_cnh"], "B")
        self.assertEqual(values["validade"], "30/06/2030")

    def test_name_with_nascimento_as_surname_is_accepted(self) -> None:
        self.assertEqual(
            intelligence.extract_person_name("Nome e Sobrenome\nWILLIAN NASCIMENTO DOS SANTOS"),
            "WILLIAN NASCIMENTO DOS SANTOS",
        )

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

    def test_ctps_digital_contract_blocks_extract_employer_and_dates(self) -> None:
        text = (
            "Extrato de Outros Vinculos\nCarteira de Trabalho Digital\n"
            "Dados Pessoais\nNome Civil: MARIA APARECIDA DOS SANTOS\n"
            "CPF: 529.982.247-25\nData de Nascimento: 10/03/1978\n"
            "Contratos de Trabalho\n"
            "05/08/2013 - 06/03/2019\n"
            "EXITO INDUSTRIA E COMERCIO DE ARTEFATOS LTDA\n"
            "CNPJ: 07.973.526/0001-05\n"
            "Relacao de trabalho: Empregado\n"
            "12/01/2004 - 06/08/2010\n"
            "ESTRELA DA MANHA PRODUTOS LTDA\n"
            "CNPJ: 05.073.191/0001-35\n"
        )

        vinculos = intelligence.extract_ctps_vinculos(text)
        fields = intelligence.extract_document_fields("CTPS", text)
        values = {field["key"]: field["value"] for field in fields}

        self.assertEqual(len(vinculos), 2)
        self.assertEqual(vinculos[0]["empregador"], "EXITO INDUSTRIA E COMERCIO DE ARTEFATOS LTDA")
        self.assertEqual(vinculos[0]["data_inicio"], "05/08/2013")
        self.assertEqual(values["nome"], "MARIA APARECIDA DOS SANTOS")
        self.assertEqual(values["empresa"], "EXITO INDUSTRIA E COMERCIO DE ARTEFATOS LTDA")
        self.assertEqual(values["vinculos_identificados"], "2")

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

    def test_cat_is_routed_to_accident_specific_schema(self) -> None:
        text = (
            "COMUNICACAO DE ACIDENTE DE TRABALHO\n"
            "Nome: JOAO DA SILVA\nCPF: 529.982.247-25\n"
            "Empresa: Alfa Servicos Ltda\nData do acidente: 05/03/2025\n"
            "Descricao do acidente: Queda durante atividade laboral.\nCID: S82.0"
        )

        classification = intelligence.classify_document("cat-acidente.pdf", text)
        fields = intelligence.extract_document_fields(classification["code"], text)
        values = {field["key"]: field["value"] for field in fields}
        assessment = intelligence.assess_document_extraction(
            classification, fields, raw_text=text, source_confidence=0.94
        )

        self.assertEqual(classification["code"], "CAT")
        self.assertEqual(values["data_acidente"], "05/03/2025")
        self.assertEqual(values["empresa"], "Alfa Servicos Ltda")
        self.assertEqual(assessment["status"], "extraido")

    def test_blank_official_ppp_template_is_not_misclassified_as_cat(self) -> None:
        text = (
            "ANEXO XVII\nPERFIL PROFISSIOGRAFICO PREVIDENCIARIO - PPP\n"
            "12 - CAT REGISTRADA\n12.1 - Data do Registro\n"
            "15 - EXPOSICAO A FATORES DE RISCOS\n"
        )

        classification = intelligence.classify_document("PPP ANEX XVII.pdf", text)
        fields = intelligence.extract_document_fields(classification["code"], text)
        assessment = intelligence.assess_document_extraction(
            classification, fields, raw_text=text, source_confidence=0.94
        )

        self.assertEqual(classification["code"], "PPP")
        self.assertEqual(assessment["status"], "parcial")

    def test_special_benefit_documents_are_not_forced_into_cnis_schema(self) -> None:
        cases = [
            ("certidao-obito.pdf", "CERTIDAO DE OBITO\nNome do falecido: MARIA DA SILVA\nData do obito: 04/02/2024", "CERTIDAO_OBITO"),
            ("gps-2024.pdf", "GUIA DA PREVIDENCIA SOCIAL\nCompetencia: 03/2024\nValor: R$ 120,00", "GPS"),
            ("certidao-carceraria.pdf", "CERTIDAO CARCERARIA\nNome: JOSE DA SILVA\nData de recolhimento: 02/01/2025\nRegime: fechado", "CERTIDAO_RECOLHIMENTO"),
        ]
        for filename, text, expected in cases:
            with self.subTest(filename=filename):
                self.assertEqual(intelligence.classify_document(filename, text)["code"], expected)

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
