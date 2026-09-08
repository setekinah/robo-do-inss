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

    def test_dashboard_keeps_decisions_separate_from_creation(self):
        markup = Path("index.html").read_text(encoding="utf-8")
        css = Path("styles.css").read_text(encoding="utf-8")

        self.assertIn("dashboard-command-center", markup)
        self.assertIn("smart-pending-panel", markup)
        self.assertIn("global-create-menu", markup)
        self.assertIn("Painel de decisões", markup)
        self.assertIn("Casos em andamento", markup)
        self.assertIn("Entrada de leads", markup)
        self.assertNotIn('id="btn-novo-atendimento"', markup)
        self.assertIn(".dashboard-command-center", css)

    def test_dashboard_action_cards_have_distinct_operational_states(self):
        markup = Path("index.html").read_text(encoding="utf-8")
        css = Path("styles.css").read_text(encoding="utf-8")

        self.assertIn("metric-card--documents", markup)
        self.assertIn("metric-card--automation", markup)
        self.assertIn("EM ACOMPANHAMENTO", markup)
        self.assertIn(".metric-card--action", css)

    def test_dashboard_has_no_simulated_operational_status_center(self):
        markup = Path("index.html").read_text(encoding="utf-8")
        source = Path("app.js").read_text(encoding="utf-8")

        self.assertNotIn("STATUS CENTER", markup)
        self.assertNotIn("Robô PrevIA Online", markup)
        self.assertNotIn("navigator.onLine", source)
        self.assertNotIn("renderOperationalStatus", source)

    def test_primary_runtime_keeps_decorative_audio_and_neural_surface(self):
        markup = Path("index.html").read_text(encoding="utf-8")
        source = Path("app.js").read_text(encoding="utf-8")
        css = Path("styles.css").read_text(encoding="utf-8")

        for marker in ("AudioSynth", "NeuralCanvas", "window.AudioContext", "webkitAudioContext"):
            self.assertIn(marker, source)
        self.assertIn('id="bg-canvas"', markup)
        self.assertIn("#bg-canvas", css)
        self.assertIn("new NeuralCanvas('bg-canvas')", source)
        self.assertIn("prefers-reduced-motion: reduce", source)
        self.assertNotIn("Robô operando sem alertas", markup)
        self.assertNotIn("ONNX Engine carregado", markup)
        self.assertNotIn("Motor Neural", markup)
        self.assertNotIn("98.7%", markup)

    def test_success_audio_follows_confirmed_login_and_triage_persistence(self):
        source = Path("app.js").read_text(encoding="utf-8")
        registration = source[source.index("async submitRegistration()"):source.index("async submitLogin()")]
        login = source[source.index("async submitLogin()"):source.index("switchTab(tabId)")]
        triage_save = source[source.index("async saveTriageLead()"):source.index("async renderRelationshipBase()")]

        self.assertLess(registration.index("await this.bootstrap();"), registration.index("audio.success();"))
        self.assertLess(login.index("await this.bootstrap();"), login.index("audio.success();"))
        self.assertLess(triage_save.index("newLead.id = data.id;"), triage_save.index("audio.success();"))


if __name__ == "__main__":
    unittest.main()
