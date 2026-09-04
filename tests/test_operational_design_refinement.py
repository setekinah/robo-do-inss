from pathlib import Path
import unittest


class OperationalDesignRefinementTests(unittest.TestCase):
    def test_login_hides_application_content_until_authentication(self):
        css = Path("styles.css").read_text(encoding="utf-8")

        self.assertIn('#login-overlay:not([style*="display: none"]) ~ .app-container', css)
        self.assertIn('visibility: hidden', css)

    def test_dashboard_prioritizes_documents_and_automation(self):
        source = Path("app.js").read_text(encoding="utf-8")
        css = Path("styles.css").read_text(encoding="utf-8")

        self.assertIn('metric-action-required', source)
        self.assertIn('metric-priority', source)
        self.assertIn('EXIGE AÇÃO', css)


if __name__ == "__main__":
    unittest.main()
