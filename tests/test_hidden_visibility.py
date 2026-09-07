from __future__ import annotations

import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class HiddenVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.styles = (REPOSITORY_ROOT / "styles.css").read_text(encoding="utf-8")
        cls.html = (REPOSITORY_ROOT / "index.html").read_text(encoding="utf-8")
        cls.script = (REPOSITORY_ROOT / "app.js").read_text(encoding="utf-8")

    def test_hidden_attribute_has_an_explicit_display_rule(self) -> None:
        rule = re.search(r"\[hidden\]\s*\{(?P<body>[^}]*)\}", self.styles)

        self.assertIsNotNone(rule)
        self.assertRegex(rule.group("body"), r"display\s*:\s*none\s*!important\s*;")

    def test_doc_audit_result_keeps_grid_layout_when_visible(self) -> None:
        rule = re.search(r"\.doc-audit-result\s*\{(?P<body>[^}]*)\}", self.styles)

        self.assertIsNotNone(rule)
        self.assertRegex(rule.group("body"), r"display\s*:\s*grid\s*;")

    def test_relevant_components_continue_to_use_semantic_hidden_state(self) -> None:
        self.assertIn('id="modal-retirement-dossier-result" class="doc-audit-result" hidden', self.html)
        self.assertIn('id="modal-docs-audit-result" class="doc-audit-result" hidden', self.html)
        self.assertIn('id="modal-evidence-matrix" class="doc-audit-result evidence-matrix" hidden', self.html)
        self.assertIn("container.hidden = true", self.script)
        self.assertIn("container.hidden = false", self.script)

    def test_hidden_rule_does_not_use_visual_only_workarounds(self) -> None:
        rule = re.search(r"\[hidden\]\s*\{(?P<body>[^}]*)\}", self.styles)

        self.assertIsNotNone(rule)
        self.assertNotRegex(rule.group("body"), r"visibility\s*:\s*hidden")
        self.assertNotRegex(rule.group("body"), r"opacity\s*:\s*0")


if __name__ == "__main__":
    unittest.main()
