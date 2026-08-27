from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import document_storage


class UploadedFile:
    def __init__(self, name: str, content: bytes) -> None:
        self.name = name
        self._content = content

    def getbuffer(self) -> bytes:
        return self._content


class DocumentStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_uploads_dir = document_storage.UPLOADS_DIR
        document_storage.UPLOADS_DIR = Path(self.temporary_directory.name) / "uploads"

    def tearDown(self) -> None:
        document_storage.UPLOADS_DIR = self.original_uploads_dir
        self.temporary_directory.cleanup()

    def test_upload_uses_safe_document_code_and_filename(self) -> None:
        path = document_storage.save_uploaded_document(
            42,
            "../CNIS",
            UploadedFile("../meu documento.pdf", b"conteudo"),
        )

        saved_path = Path(path)
        self.assertTrue(saved_path.is_file())
        self.assertEqual(saved_path.parent, document_storage.UPLOADS_DIR / "atendimento_42")
        self.assertEqual(saved_path.name, "CNIS__meu_documento.pdf")
        self.assertEqual(saved_path.read_bytes(), b"conteudo")

    def test_invalid_identifiers_and_oversized_upload_are_rejected(self) -> None:
        file = UploadedFile("documento.pdf", b"conteudo")
        with self.assertRaises(ValueError):
            document_storage.save_uploaded_document(0, "CNIS", file)
        with self.assertRaises(ValueError):
            document_storage.save_uploaded_document(1, "../", file)
        with self.assertRaises(ValueError):
            document_storage.save_uploaded_document(
                1,
                "CNIS",
                UploadedFile("grande.pdf", b"x" * (document_storage.MAX_UPLOAD_SIZE_BYTES + 1)),
            )
