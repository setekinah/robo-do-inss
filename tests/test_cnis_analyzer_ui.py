from pathlib import Path
import unittest


class CNISAnalyzerUiTests(unittest.TestCase):
    def test_dossier_renders_cnis_findings_with_review_boundary(self):
        source = Path("app.js").read_text(encoding="utf-8")

        self.assertIn("Leitura técnica preliminar do CNIS", source)
        self.assertIn("cnisAnalysis.findings", source)
        self.assertIn("não calcula tempo, carência, RMI ou elegibilidade", source)


if __name__ == "__main__":
    unittest.main()
