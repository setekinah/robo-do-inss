from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ReactiveDashboardUiTests(unittest.TestCase):
    def test_dashboard_exposes_stage_and_benefit_filters(self) -> None:
        markup = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="dashboard-stage-filter"', markup)
        self.assertIn('id="dashboard-benefit-filter"', markup)
        self.assertIn('id="btn-dashboard-clear"', markup)
        self.assertIn('id="dashboard-filter-summary"', markup)

    def test_dashboard_calculates_chart_from_current_data(self) -> None:
        script = (PROJECT_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("populateDashboardBenefitFilter()", script)
        self.assertIn("applyDashboardFilters()", script)
        self.assertIn("const values = stageKeys.map", script)
        self.assertNotIn("const values = [36, 24, 18.5, 32, 28, 10]", script)


if __name__ == "__main__":
    unittest.main()
