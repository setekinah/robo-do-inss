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

    def test_dashboard_filters_use_operational_toolbar_treatment(self):
        source = Path("app.js").read_text(encoding="utf-8")
        css = Path("styles.css").read_text(encoding="utf-8")

        self.assertIn("dashboard-filter-bar", source)
        self.assertIn("Filtros operacionais", css)
        self.assertIn(".dashboard-filter-bar select", css)

    def test_dashboard_groups_actions_and_queue_as_operational_controls(self):
        markup = Path("index.html").read_text(encoding="utf-8")
        css = Path("styles.css").read_text(encoding="utf-8")

        self.assertIn("dashboard-command-center", markup)
        self.assertIn("smart-pending-panel", markup)
        self.assertIn("dashboard-action--primary", markup)
        self.assertIn(".dashboard-command-center", css)

    def test_dashboard_action_cards_have_distinct_operational_states(self):
        markup = Path("index.html").read_text(encoding="utf-8")
        css = Path("styles.css").read_text(encoding="utf-8")

        self.assertIn("metric-card--documents", markup)
        self.assertIn("metric-card--automation", markup)
        self.assertIn("EM ACOMPANHAMENTO", markup)
        self.assertIn(".metric-card--action", css)


if __name__ == "__main__":
    unittest.main()
