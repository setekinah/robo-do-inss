from __future__ import annotations

import unittest
from datetime import date

from services.rgps_planning_service import RgpsPlanningInput, RULESET_VERSION, screen_rgps_planning, serialize_planning_result


class RgpsPlanningServiceTests(unittest.TestCase):
    reference_date = date(2026, 8, 12)

    def test_pre_reform_woman_is_screened_against_general_and_transition_rules(self) -> None:
        result = screen_rgps_planning(
            RgpsPlanningInput(
                birth_date=date(1964, 1, 1), sex="F", contribution_months=30 * 12,
                carencia_months=180, affiliation_date=date(2010, 1, 1),
            ),
            self.reference_date,
        )

        self.assertEqual(result.ruleset_version, RULESET_VERSION)
        self.assertEqual([screening.code for screening in result.screenings], [
            "regra_geral", "transicao_pontos", "transicao_idade_progressiva",
        ])
        self.assertTrue(result.screenings[0].eligible)
        self.assertFalse(result.screenings[1].eligible)
        self.assertTrue(result.screenings[2].eligible)
        serialized = serialize_planning_result(result)
        self.assertEqual(serialized["reference_date"], "2026-08-12")
        self.assertTrue(serialized["screenings"][0]["eligible"])

    def test_post_reform_man_requires_twenty_years_and_skips_transition_rules(self) -> None:
        result = screen_rgps_planning(
            RgpsPlanningInput(
                birth_date=date(1961, 8, 12), sex="M", contribution_months=20 * 12,
                carencia_months=180, affiliation_date=date(2020, 1, 1),
            ),
            self.reference_date,
        )

        self.assertEqual(len(result.screenings), 1)
        self.assertTrue(result.screenings[0].eligible)
        self.assertIn("não foram avaliadas", result.notices[-1])

    def test_invalid_or_out_of_scope_inputs_are_rejected(self) -> None:
        data = RgpsPlanningInput(date(2027, 1, 1), "F", 0, 0, date(2020, 1, 1))
        with self.assertRaises(ValueError):
            screen_rgps_planning(data, self.reference_date)
        with self.assertRaises(ValueError):
            screen_rgps_planning(
                RgpsPlanningInput(date(1960, 1, 1), "M", 240, 180, date(2010, 1, 1)),
                date(2027, 1, 1),
            )


if __name__ == "__main__":
    unittest.main()
