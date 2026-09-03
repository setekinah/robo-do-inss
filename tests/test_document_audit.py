from __future__ import annotations

import unittest

import document_audit


class DocumentAuditTests(unittest.TestCase):
    def test_confirms_matching_cnis_and_ctps_link_with_page_evidence(self) -> None:
        cnis = (
            "[Página 2]\nEmpresa: Alfa Servicos Ltda\nCNPJ: 12.345.678/0001-95\n"
            "Admissao: 01/02/2010\nRescisao: 31/01/2012"
        )
        ctps = (
            "[Página 4]\n01/02/2010 - 31/01/2012\nAlfa Servicos Ltda\n"
            "CNPJ: 12.345.678/0001-95"
        )

        report = document_audit.build_cnis_ctps_audit(cnis_raw_text=cnis, ctps_raw_text=ctps)

        self.assertEqual(report["status"], "confirmada")
        self.assertEqual(report["resumo"]["confirmados"], 1)
        finding = report["achados"][0]
        self.assertEqual(finding["status"], "confirmado")
        self.assertEqual(finding["evidencias"][0]["pagina"], 2)
        self.assertEqual(finding["evidencias"][1]["pagina"], 4)

    def test_marks_date_difference_for_human_review(self) -> None:
        cnis = (
            "Empresa: Alfa Servicos Ltda\nCNPJ: 12.345.678/0001-95\n"
            "Admissao: 01/02/2010\nRescisao: 31/01/2012"
        )
        ctps = (
            "01/02/2010 - 30/06/2012\nAlfa Servicos Ltda\n"
            "CNPJ: 12.345.678/0001-95"
        )

        report = document_audit.build_cnis_ctps_audit(cnis_raw_text=cnis, ctps_raw_text=ctps)

        self.assertEqual(report["status"], "revisao_necessaria")
        finding = report["achados"][0]
        self.assertEqual(finding["status"], "divergente")
        self.assertTrue(finding["requer_revisao"])
        self.assertEqual(finding["diferencas"][0]["campo"], "Data de saída")
        self.assertEqual(finding["diferencas"][0]["diferenca_dias"], 151)

    def test_does_not_match_same_name_without_same_cnpj(self) -> None:
        cnis = (
            "Empresa: Alfa Servicos Ltda\nCNPJ: 12.345.678/0001-95\n"
            "Admissao: 01/02/2010\nRescisao: 31/01/2012"
        )
        ctps = (
            "01/02/2010 - 31/01/2012\nAlfa Servicos Ltda\n"
            "CNPJ: 60.746.948/0035-61"
        )

        report = document_audit.build_cnis_ctps_audit(cnis_raw_text=cnis, ctps_raw_text=ctps)

        self.assertEqual(report["resumo"]["confirmados"], 0)
        self.assertEqual(report["resumo"]["nao_localizados"], 2)


if __name__ == "__main__":
    unittest.main()
