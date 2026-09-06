"""Regressões P0.2: nenhum dado fictício deve parecer operacional."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP_JS = ROOT / "app.js"
INDEX_HTML = ROOT / "index.html"


class NoFakeOperationalDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = APP_JS.read_text(encoding="utf-8")
        self.html = INDEX_HTML.read_text(encoding="utf-8")

    def _method(self, name: str) -> str:
        pattern = (
            rf"(?:async\s+)?{re.escape(name)}\s*\([^)]*\)\s*\{{.*?"
            rf"(?=\n  (?:async\s+)?[A-Za-z_$][\w$]*\s*\(|\n\}})"
        )
        match = re.search(pattern, self.app, re.DOTALL)
        self.assertIsNotNone(match, f"Não encontrei o método {name}().")
        return match.group(0)

    def test_registration_has_no_fake_office_or_oab_defaults(self) -> None:
        body = self._method("submitRegistration")

        self.assertNotIn("|| 'MADE'", body)
        self.assertNotIn("|| '524387'", body)
        self.assertIn("officeName", body)
        self.assertIn("officeOab", body)
        self.assertIn("if (!officeName || !officeOab || !email || !password)", body)

        self.assertNotIn(
            "status.oab || '524387'",
            self.app,
            "A interface não pode inventar uma OAB.",
        )
        self.assertIn("OAB não informada", self.app)

        self.assertNotIn('value="MADE"', self.html)
        self.assertNotIn('value="524387"', self.html)
        self.assertNotIn('OAB: 524387', self.html)
        self.assertNotIn('MADE Advocacia', self.html)
        self.assertNotIn('>MADE</div>', self.html)
        self.assertNotIn('Escritório MADE', self.html)
        self.assertIn('placeholder="Nome do escritório"', self.html)
        self.assertIn('placeholder="Número da OAB / UF"', self.html)

    def test_kanban_does_not_fabricate_value_phone_or_benefit(self) -> None:
        body = self._method("renderKanban")

        self.assertNotIn("12500", body)
        self.assertNotIn("98765-4321", body)

        self.assertIn("Valor não informado", body)
        self.assertIn("Telefone não informado", body)
        self.assertIn("Benefício não informado", body)

    def test_lead_modal_does_not_create_fake_client_or_history(self) -> None:
        modal = self._method("openLeadModal")
        history = self._method("renderModalHistory")

        self.assertNotIn("Cliente Exemplo", modal)
        self.assertIn("this.currentLead = null", modal)
        self.assertIn("return;", modal)

        self.assertNotIn("Atendimento inicial de triagem concluído", history)
        self.assertIn("Array.isArray", history)
        self.assertIn("Nenhuma atividade registrada", history)

    def test_document_modal_has_no_fake_document_checklist(self) -> None:
        body = self._method("renderModalDocs")

        for fake_document in (
            "Documento de Identidade com Foto",
            "CPF",
            "CNIS - Extrato Previdenciário",
            "Carteira de Trabalho (CTPS)",
        ):
            self.assertNotIn(fake_document, body)

        self.assertIn(
            "Array.isArray(this.currentLead?.documents)",
            body,
        )
        self.assertIn(
            "Nenhum documento cadastrado neste caso.",
            body,
        )

    def test_contract_failure_never_fabricates_legal_content(self) -> None:
        body = self._method("loadModalContract")

        self.assertNotIn("MADE Advocacia", body)
        self.assertNotIn("524387", body)
        self.assertNotIn("30% sobre o proveito", body)

        self.assertIn("!res.ok || !data.contract_text", body)
        self.assertIn("Contrato indisponível", body)

    def test_finance_controller_has_no_demo_kpis(self) -> None:
        body = self._method("switchFinanceTab")

        forbidden = (
            "4.122.000",
            "2.213.580",
            "817.810",
            "324.270",
            "301.942",
            "184.468",
            "852.209",
            "473 contratos",
            "68 clientes",
            "4 sócios",
        )

        for value in forbidden:
            self.assertNotIn(value, body)

        self.assertIn("Financeiro ainda não integrado", body)
        self.assertIn("const unavailable = ['—', '—', '—', '—']", body)

    def test_finance_html_starts_in_explicit_unintegrated_state(self) -> None:
        forbidden = (
            "R$ 4.122.000",
            "R$ 2.213.580",
            "R$ 817.810",
            "R$ 324.270",
            "31,4%",
            "36,9%",
            "12,3%",
            "46,8%",
            "26,1%",
            "15,2%",
            "11,9%",
        )

        for value in forbidden:
            self.assertNotIn(value, self.html)

        self.assertIn(
            "Integração financeira ainda não configurada",
            self.html,
        )
        self.assertIn("Dados não integrados", self.html)

        self.assertNotIn('<svg class="finance-chart"', self.html)
        self.assertNotIn('<svg class="finance-mini-chart"', self.html)
        self.assertNotIn('<div class="finance-donut">', self.html)


if __name__ == "__main__":
    unittest.main()
