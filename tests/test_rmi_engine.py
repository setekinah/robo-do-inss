import unittest

from modules.rmi_engine import build_scenario_catalog


class ScenarioCatalogTests(unittest.TestCase):
    def test_missing_evidence_blocks_simulation_readiness(self):
        report = build_scenario_catalog(dossier={"hipoteses": []}, triage_profile={})

        self.assertEqual(report["status"], "revisao_humana_obrigatoria")
        self.assertEqual(len(report["cenarios"]), 5)
        self.assertTrue(all(item["status"] == "base_incompleta" for item in report["cenarios"]))

    def test_catalog_never_claims_rmi_or_eligibility(self):
        report = build_scenario_catalog(dossier={"hipoteses": []}, triage_profile={})

        self.assertIn("não é um cálculo", report["conclusao"])
        self.assertIn("Não calcula RMI", report["cenarios"][0]["orientacao"])


if __name__ == "__main__":
    unittest.main()
