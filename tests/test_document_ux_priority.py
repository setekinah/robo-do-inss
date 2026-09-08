from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SCRIPT = (ROOT / "app.js").read_text(encoding="utf-8")


class DocumentUxPriorityTests(unittest.TestCase):
    def test_checklist_precedes_secondary_analysis_tools(self) -> None:
        docs_panel = re.search(r'<div id="modaltab-docs".*?</div>\s*\n\s*<div id="modaltab-contract"', HTML, re.DOTALL)
        self.assertIsNotNone(docs_panel)
        panel = docs_panel.group(0)
        self.assertLess(panel.index('class="docs-checklist"'), panel.index('class="docs-analysis-tools"'))
        self.assertIn('<summary>Ferramentas de análise', panel)
        self.assertIn('id="modal-docs-audit-button"', panel)
        self.assertIn('id="modal-evidence-matrix"', panel)
        self.assertIn('id="modal-retirement-dossier-result"', panel)

    def test_checklist_actions_use_the_existing_case_upload_flow(self) -> None:
        self.assertIn('Enviar documento', SCRIPT)
        self.assertIn('Adicionar nova versão', SCRIPT)
        self.assertIn('Visualizar', SCRIPT)
        self.assertIn('this.uploadCaseDocument(file, doc)', SCRIPT)
        self.assertIn('this.toggleDocStatus(Number(doc.id), safeStatus)', SCRIPT)
        self.assertIn('async toggleDocStatus', SCRIPT)
        upload = re.search(r'  async uploadCaseDocument\([^)]*\) \{.*?\n  \}', SCRIPT, re.DOTALL)
        self.assertIsNotNone(upload)
        self.assertIn('/upload-intents', upload.group(0))
        self.assertIn("method: 'PUT'", upload.group(0))
        self.assertIn('/complete', upload.group(0))
        self.assertNotIn("doc.status = 'recebido'", upload.group(0))
        self.assertIn('const attendanceId = this.currentLead.id', upload.group(0))
        self.assertIn('this.currentLead = refreshedLead', upload.group(0))
        self.assertIn('Arquivo armazenado com sucesso, mas a tela não pôde ser atualizada.', upload.group(0))
        self.assertIn('Não foi possível enviar o arquivo ao armazenamento privado.', upload.group(0))

    def test_analysis_features_remain_available_without_mock_documents(self) -> None:
        for method in ('async runDocumentAudit', 'async loadEvidenceMatrix', 'async runRetirementDossier'):
            self.assertIn(method, SCRIPT)
        render = re.search(r'  renderModalDocs\(\) \{.*?\n  async loadEvidenceMatrix', SCRIPT, re.DOTALL)
        self.assertIsNotNone(render)
        for fake_document in ('Cliente Exemplo', 'CNIS - Extrato Previdenciário', 'Carteira de Trabalho (CTPS)'):
            self.assertNotIn(fake_document, render.group(0))

    def test_real_document_state_controls_summary_and_readable_evidence_gate(self) -> None:
        render = re.search(r'  renderModalDocs\(\) \{.*?\n  async loadEvidenceMatrix', SCRIPT, re.DOTALL)
        self.assertIsNotNone(render)
        body = render.group(0)
        self.assertIn('Array.isArray(this.currentLead?.documents)', body)
        self.assertIn('Nenhum documento cadastrado neste caso.', body)
        self.assertIn('doc.document_code', body)
        self.assertIn('const hasReadableEvidence', body)
        self.assertIn("String(doc.raw_text || '').trim().length > 0", body)
        gate = re.search(r'const hasReadableEvidence.*?const auditAvailable', body, re.DOTALL)
        self.assertIsNotNone(gate)
        self.assertNotIn('version_count', gate.group(0))
        self.assertIn('auditButton.disabled = !auditAvailable', body)
        self.assertIn('Disponível após a leitura técnica de CNIS e CTPS.', HTML)
        self.assertNotIn('Disponível após receber CNIS e CTPS.', HTML)

    def test_audit_finally_reapplies_the_readable_evidence_gate(self) -> None:
        audit = re.search(r'  async runDocumentAudit\(\) \{.*?\n  \}', SCRIPT, re.DOTALL)
        self.assertIsNotNone(audit)
        self.assertIn('this.renderModalDocs();', audit.group(0))
        self.assertNotIn('button.disabled = false', audit.group(0))

    def test_opening_another_case_clears_previous_analytical_data(self) -> None:
        modal = re.search(r'  async openLeadModal\([^)]*\) \{.*?\n  \}', SCRIPT, re.DOTALL)
        self.assertIsNotNone(modal)
        self.assertIn('this.currentEvidenceMatrix = null', modal.group(0))

    def test_asset_release_token_is_coherent(self) -> None:
        portal = (ROOT / "portal.html").read_text(encoding="utf-8")
        references = re.findall(r'(?:styles\.css|app\.js|portal\.js)\?v=([^"\']+)', HTML + portal)
        self.assertEqual(set(references), {'a0.4-20260907'})


if __name__ == '__main__':
    unittest.main()
