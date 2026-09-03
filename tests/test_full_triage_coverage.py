"""Coverage guard for every public guided-triage option and its decision paths."""

from __future__ import annotations

import unittest

from document_rules import get_flow_document_strategy
from flows_data import FLOW_DEFINITIONS
from triage_engine import answer_current_question, create_state, get_current_node


class FullTriageCoverageTests(unittest.TestCase):
    def test_all_public_flows_have_a_document_strategy(self):
        self.assertEqual(len(FLOW_DEFINITIONS), 10)
        for flow_id in FLOW_DEFINITIONS:
            with self.subTest(flow_id=flow_id):
                strategy = get_flow_document_strategy(flow_id)
                self.assertTrue(strategy["documents"])
                self.assertGreater(strategy["required_total"], 0)

    def test_every_answer_in_every_flow_reaches_a_valid_terminal_result(self):
        for flow_id, flow in FLOW_DEFINITIONS.items():
            with self.subTest(flow_id=flow_id):
                reached_results: set[str] = set()
                covered_answers: set[tuple[str, str]] = set()

                def walk(state, path: tuple[str, ...] = ()):
                    node = get_current_node(state, flow)
                    self.assertIsNotNone(node)
                    self.assertNotIn(node["id"], path, "A árvore não pode conter ciclo")
                    self.assertTrue(node["options"], "Toda pergunta precisa oferecer resposta")
                    for option in node["options"]:
                        covered_answers.add((node["id"], option["label"]))
                        next_state, result = answer_current_question(state, flow, option["label"])
                        if result is not None:
                            self.assertIn(next_state.result_key, flow["results"])
                            self.assertTrue(result.get("title"))
                            self.assertTrue(result.get("summary"))
                            self.assertTrue(result.get("next_step"))
                            reached_results.add(next_state.result_key)
                        else:
                            walk(next_state, (*path, node["id"]))

                walk(create_state(flow_id, flow))
                declared_answers = {
                    (node["id"], option["label"])
                    for node in flow["nodes"].values()
                    for option in node["options"]
                }
                self.assertSetEqual(covered_answers, declared_answers)
                self.assertSetEqual(reached_results, set(flow["results"]))


if __name__ == "__main__":
    unittest.main()
