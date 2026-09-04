import unittest

from modules.cnis_analyzer import analyze_cnis_documents, analyze_cnis_text


class CNISAnalyzerTests(unittest.TestCase):
    def test_finds_p_ext_and_keeps_page_evidence(self):
        result = analyze_cnis_text(raw_text="[Página 2]\nIndicadores: PEXT\nVínculo 01/01/2010 até 01/01/2012", document_id=17)

        self.assertEqual(result["status"], "revisao_humana_obrigatoria")
        self.assertEqual(result["source"]["id"], "pt990_anexo_v")
        pext = next(item for item in result["findings"] if item["code"] == "PEXT")
        self.assertEqual(pext["evidence"][0]["document_id"], 17)
        self.assertEqual(pext["evidence"][0]["page"], 2)

    def test_special_reference_never_becomes_an_eligibility_decision(self):
        result = analyze_cnis_text(raw_text="[Página 1] PPP e agente nocivo informado")

        special = next(item for item in result["findings"] if item["code"] == "POSSIVEL_PERIODO_ESPECIAL")
        self.assertIn("não comprova", special["guidance"])
        self.assertIn("não calcula", " ".join(result["warnings"]))

    def test_missing_cnis_has_safe_fallback(self):
        result = analyze_cnis_documents([{"document_code": "CTPS", "raw_text": "vínculo"}])

        self.assertEqual(result["status"], "documento_ausente")
        self.assertEqual(result["findings"], [])

    def test_empty_extraction_has_safe_fallback(self):
        result = analyze_cnis_text(raw_text="", document_id=9)

        self.assertEqual(result["status"], "nao_analisado")
        self.assertEqual(result["findings"], [])


if __name__ == "__main__":
    unittest.main()
