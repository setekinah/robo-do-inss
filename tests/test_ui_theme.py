from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class UiThemeTests(unittest.TestCase):
    def test_streamlit_theme_uses_the_current_admin_palette(self) -> None:
        config_path = PROJECT_ROOT / ".streamlit" / "config.toml"
        with config_path.open("rb") as config_file:
            theme = tomllib.load(config_file)["theme"]

        self.assertEqual(theme["primaryColor"].lower(), "#2448a8")
        self.assertEqual(theme["backgroundColor"].lower(), "#f6f8fc")
        self.assertEqual(theme["secondaryBackgroundColor"].lower(), "#ffffff")
        self.assertEqual(theme["textColor"].lower(), "#17243b")

    def test_file_upload_language_is_portuguese_and_clear_for_cnis(self) -> None:
        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        calculations_source = (PROJECT_ROOT / "views" / "calculations.py").read_text(encoding="utf-8")

        self.assertIn("Arraste o arquivo aqui", app_source)
        self.assertIn("ou clique em Procurar arquivos", app_source)
        self.assertIn("Ainda não há dossiês para anexar documentos", app_source)
        self.assertIn("CNIS do cliente — arraste o documento aqui", calculations_source)
        self.assertIn('type=["pdf", "png", "jpg", "jpeg", "tif", "tiff"]', calculations_source)


if __name__ == "__main__":
    unittest.main()
