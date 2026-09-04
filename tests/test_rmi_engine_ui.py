from pathlib import Path
import unittest


class ScenarioCatalogUiTests(unittest.TestCase):
    def test_dossier_exposes_preparatory_scenarios_without_calculation_claim(self):
        source = Path("app.js").read_text(encoding="utf-8")

        self.assertIn("Cenários para futura simulação", source)
        self.assertIn("scenarioCatalog.cenarios", source)
        self.assertIn("não calcula RMI, pontos, pedágios, tempo ou elegibilidade", source)


if __name__ == "__main__":
    unittest.main()
