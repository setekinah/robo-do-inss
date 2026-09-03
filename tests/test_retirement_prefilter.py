import unittest

from retirement_prefilter import evaluate_retirement_prefilter


class RetirementPrefilterTests(unittest.TestCase):
    def payload(self, **overrides):
        data = {
            "sex": "feminino", "age": 62, "contribution_years": 15,
            "has_cnis": "sim", "affiliation": "antes_ec103",
        }
        data.update(overrides)
        return data

    def test_missing_cnis_blocks_triage_and_routes_to_documents(self):
        result = evaluate_retirement_prefilter(self.payload(has_cnis="nao"))
        self.assertEqual(result["route"], "documentos")

    def test_incomplete_requirements_route_to_planning(self):
        result = evaluate_retirement_prefilter(self.payload(age=54, contribution_years=10))
        self.assertEqual(result["route"], "planejamento")
        self.assertEqual(result["requirements"]["faltam_anos_idade"], 8)

    def test_complete_minimum_allows_explicit_technical_triage(self):
        result = evaluate_retirement_prefilter(self.payload())
        self.assertEqual(result["route"], "triagem")

    def test_male_post_reform_uses_twenty_year_reference(self):
        result = evaluate_retirement_prefilter(self.payload(sex="masculino", age=65, contribution_years=15, affiliation="apos_ec103"))
        self.assertEqual(result["route"], "planejamento")
        self.assertEqual(result["requirements"]["tempo_minimo_referencia"], 20)

    def test_cnis_evidence_overrides_manual_age_and_contribution(self):
        result = evaluate_retirement_prefilter(self.payload(
            age=45,
            contribution_years=1,
            cnis_evidence={
                "document_code": "CNIS",
                "file_name": "extrato.pdf",
                "segurado": {"data_nascimento": "01/01/1960"},
                "metricas": {"tempo_contribuicao_dias": 15 * 365},
                "indicator_matches": [{"code": "PEXT"}],
            },
        ))
        self.assertEqual(result["route"], "triagem")
        self.assertTrue(result["evidence"]["used"])
        self.assertEqual(result["evidence"]["alerts"], 1)


if __name__ == "__main__":
    unittest.main()
