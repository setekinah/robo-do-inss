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

    def test_document_uploader_is_presented_in_portuguese(self) -> None:
        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn("Arraste e solte os arquivos aqui", app_source)
        self.assertIn("Selecionar arquivos", app_source)
        self.assertIn("Limite de 200 MB por arquivo", app_source)
        self.assertIn('data-testid="stFileUploaderDropzone"', app_source)


if __name__ == "__main__":
    unittest.main()
