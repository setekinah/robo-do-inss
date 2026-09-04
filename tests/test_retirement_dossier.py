from __future__ import annotations

import json
import unittest

from retirement_dossier import apply_human_decision, build_retirement_dossier


def document(code: str, *, uploaded: bool = True, status: str = "recebido") -> dict:
    return {
        "id": 1,
        "document_code": code,
        "document_name": code,
        "status": status,
        "uploaded_files_json": json.dumps(["evidence.pdf"] if uploaded else []),
        "raw_text": "[Página 1] Evidência documental para teste.",
        "extraction_status": "extraido",
        "extraction_confidence": 0.92,
    }


class RetirementDossierTests(unittest.TestCase):
    def test_dossier_maps_all_retirement_hypotheses_without_approving_any(self) -> None:
        report = build_retirement_dossier(
            documents=[document("identidade"), document("cnis"), document("ctps")],
            triage_profile={"prequalification": {"age": 65, "contribution_years": 25, "affiliation": "antes_ec103"}},
        )

        self.assertEqual(report["status"], "revisao_humana_obrigatoria")
        self.assertEqual(len(report["hipoteses"]), 5)
        self.assertEqual(report["hipoteses"][0]["status"], "revisao_humana_obrigatoria")
        self.assertNotIn("aprovada", {item["status"] for item in report["hipoteses"]})
        self.assertEqual(report["hipoteses"][2]["status"], "base_incompleta")

    def test_missing_cnis_keeps_programmed_retirement_incomplete(self) -> None:
        report = build_retirement_dossier(
            documents=[document("identidade"), document("ctps")],
            triage_profile={"prequalification": {"age": 65, "contribution_years": 25, "affiliation": "antes_ec103"}},
        )

        programmed = report["hipoteses"][0]
        self.assertEqual(programmed["status"], "base_incompleta")
        self.assertIn("CNIS com vínculos, contribuições e indicadores", programmed["pendencias"])

    def test_human_decision_requires_responsible_and_reason(self) -> None:
        report = build_retirement_dossier(documents=[], triage_profile={})
        with self.assertRaisesRegex(ValueError, "responsável"):
            apply_human_decision(report, status="prosseguir_analise", responsible="", note="Conferência necessária")
        with self.assertRaisesRegex(ValueError, "nota"):
            apply_human_decision(report, status="prosseguir_analise", responsible="Dra. Ana", note="")

        updated = apply_human_decision(
            report, status="solicitar_provas", responsible="Dra. Ana", note="Solicitar CNIS atualizado."
        )
        self.assertEqual(updated["decisao_humana"]["status"], "solicitar_provas")


if __name__ == "__main__":
    unittest.main()
