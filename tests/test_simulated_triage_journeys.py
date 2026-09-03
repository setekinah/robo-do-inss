"""Eleven non-persistent simulated client journeys using only PrevIA's local rules."""

from __future__ import annotations

import unittest

from flows_data import FLOW_DEFINITIONS
from retirement_prefilter import evaluate_retirement_prefilter
from triage_engine import answer_current_question, create_state


def simulate(flow_id: str, answers: list[str]) -> dict:
    flow = FLOW_DEFINITIONS[flow_id]
    state = create_state(flow_id, flow)
    result = None
    for answer in answers:
        state, result = answer_current_question(state, flow, answer)
    if result is None:
        raise AssertionError(f"A simulação de {flow_id} não terminou.")
    return result


class SimulatedTriageJourneysTests(unittest.TestCase):
    def test_eleven_simulated_clients_follow_local_rules(self):
        scenarios = [
            ("auxilioAcidente", ["Sim", "Sim", "Sim", "Sim"], "aprovado"),
            ("aposentadoria", ["Sim", "Comum", "Sim", "Regra de transicao", "Sem divergencias", "Nenhum", "Planejamento", "Sim"], "aprovado"),
            ("bpcLoas", ["Idoso 65+", "Sim", "Sim"], "aprovado"),
            ("salarioMaternidade", ["Sim", "CLT / empregada", "Sim", "Sim"], "aprovado"),
            ("auxilioDoenca", ["Sim", "Sim", "Sim"], "aprovado"),
            ("aposentadoriaInvalidez", ["Sim", "Sim", "Sim"], "aprovado"),
            ("pensaoMorte", ["Sim", "Sim", "Sim"], "aprovado"),
            ("auxilioReclusao", ["Sim", "Sim", "Sim"], "aprovado"),
            ("revisaoBeneficio", ["Sim", "Sim", "Sim"], "aprovado"),
            ("planejamentoPrevidenciario", ["Sim", "Sim", "Sim"], "aprovado"),
        ]
        for flow_id, answers, expected_status in scenarios:
            with self.subTest(flow_id=flow_id):
                self.assertEqual(simulate(flow_id, answers)["status"], expected_status)

        prefilter = evaluate_retirement_prefilter({
            "sex": "masculino", "age": 40, "contribution_years": 1,
            "has_cnis": "sim", "affiliation": "antes_ec103",
            "cnis_evidence": {
                "document_code": "CNIS", "file_name": "cnis-simulado.pdf",
                "segurado": {"data_nascimento": "01/01/1958"},
                "metricas": {"tempo_contribuicao_dias": 18 * 365},
                "indicator_matches": [],
            },
        })
        self.assertEqual(prefilter["route"], "triagem")
        self.assertTrue(prefilter["evidence"]["used"])


if __name__ == "__main__":
    unittest.main()
