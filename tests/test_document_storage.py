from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import document_storage


class UploadedFile:
    def __init__(self, name: str, content: bytes) -> None:
        self.name = name
        self._content = content

    def getbuffer(self) -> memoryview:
        return memoryview(self._content)


class DocumentStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.uploads_dir = Path(self.temporary_directory.name) / "uploads"
        self.patcher = patch.object(document_storage, "UPLOADS_DIR", self.uploads_dir)
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()
        self.temporary_directory.cleanup()

    def test_upload_uses_content_hash_to_prevent_same_name_collision(self) -> None:
        first = document_storage.save_uploaded_document(
            12, "identidade", UploadedFile("rg.pdf", b"%PDF-1.7 first")
        )
        second = document_storage.save_uploaded_document(
            12, "identidade", UploadedFile("rg.pdf", b"%PDF-1.7 second")
        )

        self.assertNotEqual(first, second)
        self.assertEqual(Path(first).read_bytes(), b"%PDF-1.7 first")
        self.assertEqual(Path(second).read_bytes(), b"%PDF-1.7 second")

    def test_upload_rejects_mismatched_extension_and_signature(self) -> None:
        with self.assertRaisesRegex(ValueError, "não corresponde"):
            document_storage.save_uploaded_document(
                12, "identidade", UploadedFile("documento.pdf", b"not a PDF")
            )

    def test_upload_rejects_path_traversal_in_document_code(self) -> None:
        path = document_storage.save_uploaded_document(
            12, "../identidade", UploadedFile("rg.pdf", b"%PDF-1.7 valid")
        )

        self.assertTrue(Path(path).is_relative_to(self.uploads_dir / "atendimento_12"))
        self.assertNotIn("..", Path(path).name)


if __name__ == "__main__":
    unittest.main()
