import unittest

import official_catalog


class OfficialCatalogTests(unittest.TestCase):
    def test_anexo_v_parser_keeps_only_rows_preceded_by_indicator_type(self) -> None:
        pages = [
            """ANEXO V
CsPendencia
CONTRIBUICOES
PSC-MEN-SM-EC103
Pendencia que sinaliza competencia abaixo do minimo
O indicador e exibido no CNIS e requer analise.
CsAlerta
VINCULOS
PEXT
Vinculo extemporaneo
Trata-se de alerta para conferencia documental.
TITULO SEM VALOR
"""
        ]

        rows = official_catalog._indicator_rows_from_pdf_pages(
            pages, "https://portalin.inss.gov.br/assets/anexos/pt990/AnexoV.pdf"
        )

        self.assertEqual([row["code"] for row in rows], ["PSC-MEN-SM-EC103", "PEXT"])
        self.assertEqual(rows[0]["indicator_type"], "CsPendencia")
        self.assertEqual(rows[1]["indicator_group"], "VINCULOS")
        self.assertIn("requer analise", rows[0]["official_clarification"])


if __name__ == "__main__":
    unittest.main()
