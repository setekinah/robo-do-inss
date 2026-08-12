from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import database
from repositories.reference_data_repository import ReferenceDataRepository
from services.date_calculation_service import calculate_day_interval
from services.reference_data_service import ReferenceDataset


class ReferenceDataAndDatesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = Path(self.temporary_directory.name) / "references.db"
        database.init_database()

    def tearDown(self) -> None:
        database.DB_PATH = self.original_db_path
        self.temporary_directory.cleanup()

    def test_reference_snapshot_is_versioned_and_retrievable(self) -> None:
        dataset = ReferenceDataset("indices", "2026.01", "https://www.gov.br/exemplo", date(2026, 1, 1), {"2026-01": 1.0})
        repository = ReferenceDataRepository()
        self.assertGreater(repository.save(dataset), 0)
        self.assertEqual(repository.latest("indices"), dataset)

    def test_invalid_source_and_date_interval_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ReferenceDataRepository().save(ReferenceDataset("indices", "v1", "http://inseguro", date.today(), {"x": 1}))
        self.assertEqual(calculate_day_interval(date(2026, 1, 1), date(2026, 1, 2)), 1)
        self.assertEqual(calculate_day_interval(date(2026, 1, 1), date(2026, 1, 2), True), 2)
        with self.assertRaises(ValueError):
            calculate_day_interval(date(2026, 1, 2), date(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
