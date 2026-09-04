import unittest

from pypdf import PdfReader

from modules.pdf_generator import build_review_draft_pdf


class PDFGeneratorTests(unittest.TestCase):
    def test_generates_readable_review_draft_with_clear_limits(self):
        payload = build_review_draft_pdf(
            attendance={"lead_name": "Maria da Silva"},
            dossier={
                "analise_cnis": {"conclusion": "Sinal localizado.", "findings": [{"code": "PEXT", "message": "Indicador localizado.", "guidance": "Conferir competência.", "evidence": [{"page": 2}]}]},
                "hipoteses": [{"titulo": "Aposentadoria programada", "status": "base_incompleta", "pendencias": ["CNIS atualizado"]}],
                "decisao_humana": {"status": "em_revisao"},
            },
        )

        reader = PdfReader(__import__("io").BytesIO(payload))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("RASCUNHO PARA CONFER", text)
        self.assertIn("PEXT", text)
        self.assertIn("não calcula tempo", text)
