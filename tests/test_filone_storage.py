from __future__ import annotations

import os
import unittest

from filone_storage import (
    FilOneConfig, FilOneStorageService, StorageConfigurationError, build_storage_key,
    validate_upload_metadata,
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

    def test_missing_configuration_fails_clearly(self) -> None:
        original = dict(os.environ)
        try:
            for name in ("FILONE_ENDPOINT", "FILONE_REGION", "FILONE_ACCESS_KEY", "FILONE_SECRET_KEY", "FILONE_BUCKET"):
                os.environ.pop(name, None)
            with self.assertRaises(StorageConfigurationError):
                FilOneConfig.from_environment()
        finally:
            os.environ.clear()
            os.environ.update(original)


if __name__ == "__main__":
    unittest.main()
