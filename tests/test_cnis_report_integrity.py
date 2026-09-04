from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CNISReportIntegrityTests(unittest.TestCase):
    def test_empty_catalog_does_not_hide_extracted_indicators(self) -> None:
        source = (ROOT / "api_server.py").read_text(encoding="utf-8")

        self.assertIn('max(\n                int(cnis_report["metricas"].get("alertas_contagem") or 0),', source)
        self.assertIn("len(catalog_matches)", source)

    def test_interface_does_not_call_document_competencies_completed_carencia(self) -> None:
        markup = (ROOT / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("COMPETÊNCIAS LOCALIZADAS", markup)
        self.assertNotIn("CARÊNCIA CUMPRIDA", markup)
        self.assertIn("indicadores para revisão", script)

    def test_ocr_screen_allows_discarding_the_current_document(self) -> None:
        markup = (ROOT / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="btn-ocr-reset"', markup)
        self.assertIn("resetOCRAnalysis()", script)
        self.assertIn("this.ocrUploadSequence += 1", script)

    def test_cnis_print_action_generates_a_review_report_not_the_full_screen(self) -> None:
        markup = (ROOT / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn('data-action="print-cnis-report"', markup)
        self.assertIn("printCNISReviewReport()", script)
        self.assertIn("Relatório de revisão documental - CNIS", script)
        self.assertIn("não conclui direito, carência, RMI ou elegibilidade", script)

    def test_cnis_actions_have_a_real_lead_flow_and_product_button_styles(self) -> None:
        markup = (ROOT / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "styles.css").read_text(encoding="utf-8")

        self.assertIn("Criar lead com esta análise", markup)
        self.assertIn("convertCNISToLead()", script)
        self.assertIn("Criar lead a partir do CNIS", script)
        self.assertIn(".ocr-action-button", styles)


if __name__ == "__main__":
    unittest.main()
