from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from services.backup_service import create_backup, restore_backup, validate_backup


class BackupServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.data_dir = Path(self.temporary_directory.name) / "data"
        (self.data_dir / "uploads").mkdir(parents=True)
        (self.data_dir / "triagem.db").write_bytes(b"database")
        (self.data_dir / "uploads" / "cnis.pdf").write_bytes(b"document")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_backup_and_restore_preserve_operational_files(self) -> None:
        backup = create_backup(self.data_dir, datetime(2026, 8, 13, 12, 0, 0))
        content = backup.read_bytes()
        self.assertEqual(validate_backup(content), ["triagem.db", "uploads/cnis.pdf"])
        (self.data_dir / "uploads" / "cnis.pdf").write_bytes(b"changed")

        restored = restore_backup(self.data_dir, content)

        self.assertIn(self.data_dir / "uploads" / "cnis.pdf", restored)
        self.assertEqual((self.data_dir / "uploads" / "cnis.pdf").read_bytes(), b"document")
        self.assertTrue(any((self.data_dir / "backups").glob("*.zip")))

    def test_backup_rejects_unsafe_archive_members(self) -> None:
        import io
        import zipfile

        content = io.BytesIO()
        with zipfile.ZipFile(content, "w") as archive:
            archive.writestr("manifest.json", '{"format":"robo-inss-backup-v1"}')
            archive.writestr("../outside.txt", "no")
        with self.assertRaises(ValueError):
            validate_backup(content.getvalue())


if __name__ == "__main__":
    unittest.main()
