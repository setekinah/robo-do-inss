"""Regressões para o bootstrap de AppEngine em app.js.

Protege as regras P0.1:

- nenhuma API protegida é disparada pelo constructor antes da autenticação;
- auth status é consultado antes de qualquer carregamento operacional;
- indisponibilidade do backend é diferente de ausência de sessão;
- instalação ainda não configurada abre cadastro inicial;
- sessão ausente abre login;
- sessão válida carrega dados reais;
- verificação silenciosa do catálogo só ocorre depois da autenticação;
- login e cadastro reutilizam bootstrap();
- dados fictícios não são usados como fallback.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


APP_JS = Path(__file__).resolve().parent.parent / "app.js"


class AppEngineBootstrapSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = APP_JS.read_text(encoding="utf-8")

    def _method(self, name: str) -> str:
        pattern = rf"(?:async\s+)?{re.escape(name)}\s*\([^)]*\)\s*\{{.*?(?=\n  (?:async\s+)?[A-Za-z_$][\w$]*\s*\(|\n\}})"
        match = re.search(pattern, self.source, re.DOTALL)
        self.assertIsNotNone(match, f"Não encontrei o método {name}().")
        return match.group(0)

    def test_constructor_does_not_call_protected_services_before_auth(self) -> None:
        app_engine = re.search(r"class AppEngine \{.*", self.source, re.DOTALL)
        self.assertIsNotNone(app_engine)

        constructor = re.search(
            r"constructor\s*\(\)\s*\{.*?\n  \}",
            app_engine.group(0),
            re.DOTALL,
        )
        self.assertIsNotNone(constructor)

        body = constructor.group(0)

        self.assertIn("this.bootstrap();", body)
        self.assertNotIn("this.checkAuthStatus();", body)
        self.assertNotIn("this.loadData();", body)
        self.assertNotIn("this.runSilentCatalogCheck();", body)

    def test_check_auth_status_distinguishes_unavailable_backend(self) -> None:
        body = self._method("checkAuthStatus")

        self.assertIn("available: true", body)

        catch_block = body[body.index("catch"):]

        self.assertIn("available: false", catch_block)
        self.assertIn("authenticated: false", catch_block)
        self.assertIn("configured: null", catch_block)

    def test_bootstrap_handles_states_in_safe_order(self) -> None:
        body = self._method("bootstrap")

        auth_index = body.index("await this.checkAuthStatus()")
        unavailable_index = body.index("!status.available")
        configured_index = body.index("!status.configured")
        authenticated_index = body.index("!status.authenticated")
        profile_index = body.index("this.applyAuthenticatedProfile")
        load_index = body.index("await this.loadData()")
        catalog_index = body.index("this.runSilentCatalogCheck()")

        self.assertLess(auth_index, unavailable_index)
        self.assertLess(unavailable_index, configured_index)
        self.assertLess(configured_index, authenticated_index)
        self.assertLess(authenticated_index, profile_index)
        self.assertLess(profile_index, load_index)
        self.assertLess(load_index, catalog_index)

        self.assertIn("this.showAuthUnavailable()", body)
        self.assertIn("this.nextOnboardingStep(2)", body)
        self.assertIn("this.showLoginMode(status)", body)

    def test_load_data_never_falls_back_to_fake_operational_data(self) -> None:
        self.assertNotIn(
            "renderMockData",
            self.source,
            "renderMockData() não deve existir no frontend operacional.",
        )

        body = self._method("loadData")

        self.assertIn("401", body)
        self.assertIn("handleUnauthenticated", body)

    def test_login_and_registration_delegate_to_bootstrap(self) -> None:
        for name in ("submitLogin", "submitRegistration"):
            body = self._method(name)

            self.assertIn(
                "await this.bootstrap()",
                body,
                f"{name} deve voltar ao bootstrap após autenticação.",
            )

            self.assertNotIn(
                "await this.loadData()",
                body,
                f"{name} não deve duplicar diretamente o carregamento da aplicação.",
            )

            self.assertNotIn(
                "this.applyAuthenticatedProfile",
                body,
                f"{name} não deve duplicar regras do bootstrap.",
            )

    def test_catalog_check_occurs_only_inside_authenticated_bootstrap_path(self) -> None:
        occurrences = self.source.count("this.runSilentCatalogCheck();")

        self.assertEqual(
            occurrences,
            1,
            "runSilentCatalogCheck() deve ser chamado exatamente uma vez pelo fluxo autenticado.",
        )

        bootstrap = self._method("bootstrap")
        self.assertIn("this.runSilentCatalogCheck();", bootstrap)
        self.assertLess(
            bootstrap.index("await this.loadData()"),
            bootstrap.index("this.runSilentCatalogCheck();"),
        )

    def test_logout_still_calls_revoke_endpoint(self) -> None:
        body = self._method("logout")

        self.assertIn("/api/auth/logout", body)
        self.assertIn("POST", body)


if __name__ == "__main__":
    unittest.main()
