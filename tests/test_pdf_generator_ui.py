from pathlib import Path
import unittest


class PDFGeneratorUiTests(unittest.TestCase):
    def test_review_pdf_endpoint_and_button_are_available(self):
        api = Path("api_server.py").read_text(encoding="utf-8")
        ui = Path("app.js").read_text(encoding="utf-8")

        self.assertIn("kit-requerimento.pdf", api)
        self.assertIn("handle_get_review_draft_pdf", api)
        self.assertIn("Baixar rascunho PDF para revisão", ui)


if __name__ == "__main__":
    unittest.main()
