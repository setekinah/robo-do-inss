from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import api_server

from filone_storage import (
    FilOneConfig, FilOneStorageService, StorageConfigurationError, build_storage_key,
    configured_max_document_bytes, load_local_filone_environment, validate_upload_metadata,
)


class FakeS3:
    def __init__(self) -> None:
        self.objects = {}
        self.deleted = []

    def put_object(self, **kwargs):
        self.objects[kwargs["Key"]] = {"ContentLength": len(kwargs["Body"]), "ContentType": kwargs["ContentType"], "ETag": '"etag"', "Metadata": {}}
        return {"ETag": '"etag"'}

    def generate_presigned_url(self, operation, Params, ExpiresIn, HttpMethod):
        return f"https://private.example/{operation}/{Params['Key']}?expires={ExpiresIn}"

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            error = Exception("not found")
            error.response = {"Error": {"Code": "404"}}
            raise error
        return self.objects[Key]

    def delete_object(self, Bucket, Key):
        self.deleted.append(Key)
        self.objects.pop(Key, None)

    def list_objects_v2(self, Bucket, Prefix, MaxKeys):
        return {"Contents": [
            {"Key": key, "Size": item["ContentLength"], "ETag": item["ETag"]}
            for key, item in self.objects.items() if key.startswith(Prefix)
        ][:MaxKeys]}


class AccessDeniedHeadS3(FakeS3):
    def head_object(self, Bucket, Key):
        error = Exception("access denied")
        error.response = {"Error": {"Code": "AccessDenied"}}
        raise error


class AccessDeniedEverywhereS3(AccessDeniedHeadS3):
    def list_objects_v2(self, Bucket, Prefix, MaxKeys):
        error = Exception("access denied")
        error.response = {"Error": {"Code": "AccessDenied"}}
        raise error


class FilOneStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = FakeS3()
        self.service = FilOneStorageService(FilOneConfig("https://endpoint.example", "region-1", "key", "secret", "private-bucket"), self.client)

    def test_presigned_upload_download_upload_metadata_and_delete(self) -> None:
        key = build_storage_key(attendance_id=7, document_id=9, filename="extrato.pdf")
        self.assertNotIn("CPF", key)
        self.assertIn("put_object", self.service.create_presigned_upload_url(key=key, content_type="application/pdf", expires_in=600))
        self.service.upload(key=key, content=b"%PDF-test", content_type="application/pdf")
        self.assertTrue(self.service.exists(key=key))
        self.assertEqual(self.service.get_metadata(key=key)["size_bytes"], 9)
        self.assertIn("get_object", self.service.create_presigned_download_url(key=key, expires_in=300))
        self.service.delete(key=key)
        self.assertFalse(self.service.exists(key=key))

    def test_rejects_invalid_type_name_and_size(self) -> None:
        with self.assertRaises(ValueError):
            validate_upload_metadata(filename="../cpf.pdf", mime_type="application/pdf", size_bytes=1)
        with self.assertRaises(ValueError):
            validate_upload_metadata(filename="arquivo.exe", mime_type="application/octet-stream", size_bytes=1)
        with self.assertRaises(ValueError):
            validate_upload_metadata(filename="arquivo.pdf", mime_type="application/pdf", size_bytes=51 * 1024 * 1024)

    def test_maximum_size_policy_is_explicit_and_cannot_be_relaxed(self) -> None:
        original = os.environ.get("FILONE_MAX_DOCUMENT_MB")
        try:
            os.environ["FILONE_MAX_DOCUMENT_MB"] = "12"
            self.assertEqual(configured_max_document_bytes(), 12 * 1024 * 1024)
            os.environ["FILONE_MAX_DOCUMENT_MB"] = "51"
            with self.assertRaises(StorageConfigurationError):
                configured_max_document_bytes()
        finally:
            if original is None:
                os.environ.pop("FILONE_MAX_DOCUMENT_MB", None)
            else:
                os.environ["FILONE_MAX_DOCUMENT_MB"] = original

    def test_first_validation_loads_local_environment(self) -> None:
        with patch("filone_storage.load_local_filone_environment") as loader:
            configured_max_document_bytes()
        loader.assert_called_once()

    def test_local_environment_accepts_utf8_bom(self) -> None:
        original = os.environ.get("FILONE_MAX_DOCUMENT_MB")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / ".env").write_bytes(b"\xef\xbb\xbfFILONE_MAX_DOCUMENT_MB=12\n")
            os.environ.pop("FILONE_MAX_DOCUMENT_MB", None)
            with patch("filone_storage.Path", return_value=root / "filone_storage.py"):
                load_local_filone_environment()
            self.assertEqual(os.environ["FILONE_MAX_DOCUMENT_MB"], "12")
        if original is None:
            os.environ.pop("FILONE_MAX_DOCUMENT_MB", None)
        else:
            os.environ["FILONE_MAX_DOCUMENT_MB"] = original

    def test_missing_configuration_fails_clearly(self) -> None:
        original = dict(os.environ)
        try:
            for name in ("FILONE_ENDPOINT", "FILONE_REGION", "FILONE_ACCESS_KEY", "FILONE_SECRET_KEY", "FILONE_BUCKET"):
                os.environ.pop(name, None)
            with patch("filone_storage.load_local_filone_environment"):
                with self.assertRaises(StorageConfigurationError):
                    FilOneConfig.from_environment()
        finally:
            os.environ.clear()
            os.environ.update(original)

    def test_access_denied_head_uses_exact_list_fallback(self) -> None:
        key = "private/missing.pdf"
        client = AccessDeniedHeadS3()
        client.objects[key] = {"ContentLength": 1, "ContentType": "application/pdf", "ETag": '"etag"', "Metadata": {}}
        service = FilOneStorageService(self.service._config, client)
        self.assertTrue(service.exists(key=key))
        self.assertFalse(service.exists(key="private/absent.pdf"))

    def test_access_denied_metadata_uses_same_exact_list_fallback(self) -> None:
        key = "private/document.pdf"
        client = AccessDeniedHeadS3()
        client.objects[key] = {"ContentLength": 7, "ContentType": "application/pdf", "ETag": '"etag"', "Metadata": {}}
        metadata = FilOneStorageService(self.service._config, client).get_metadata(key=key)
        self.assertEqual(metadata["source"], "list")
        self.assertEqual(metadata["size_bytes"], 7)
        self.assertEqual(metadata["mime_type"], "")

    def test_access_denied_list_is_not_masked_as_absence(self) -> None:
        service = FilOneStorageService(self.service._config, AccessDeniedEverywhereS3())
        with self.assertRaises(Exception):
            service.exists(key="private/absent.pdf")

    def test_invalid_max_size_becomes_controlled_upload_intent_error(self) -> None:
        handler = object.__new__(api_server.SofiPreviRequestHandler)
        responses = []
        handler._read_json_body = lambda: {"document_id": 1, "filename": "arquivo.pdf", "mime_type": "application/pdf", "size_bytes": 1}
        handler._send_json = lambda payload, status=200: responses.append((payload, status))
        with patch("api_server.validate_upload_metadata", side_effect=StorageConfigurationError("limite inválido")):
            handler.handle_post_document_upload_intent(1)
        self.assertEqual(responses, [({"success": False, "error": "limite inválido"}, 503)])


if __name__ == "__main__":
    unittest.main()
