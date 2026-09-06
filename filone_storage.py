"""Adaptador Fil One S3. Credenciais e URLs nunca são persistidas ou registradas."""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
ALLOWED_MIME_TYPES = {
    "application/pdf", "image/png", "image/jpeg", "image/tiff", "image/webp", "image/bmp",
}
FILONE_ENV_NAMES = ("FILONE_ENDPOINT", "FILONE_REGION", "FILONE_ACCESS_KEY", "FILONE_SECRET_KEY", "FILONE_BUCKET")


class StorageConfigurationError(RuntimeError):
    """Raised only when a storage action needs missing Fil One configuration."""


def load_local_filone_environment() -> None:
    """Load only Fil One keys from the ignored local .env file, without logging values."""
    env_file = Path(__file__).with_name(".env")
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name in FILONE_ENV_NAMES and not os.environ.get(name):
            os.environ[name] = value.strip().strip('"').strip("'")


@dataclass(frozen=True)
class FilOneConfig:
    endpoint: str
    region: str
    access_key: str
    secret_key: str
    bucket: str

    @classmethod
    def from_environment(cls) -> "FilOneConfig":
        load_local_filone_environment()
        values = {name: os.environ.get(name, "").strip() for name in FILONE_ENV_NAMES}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise StorageConfigurationError("Configuração Fil One ausente: " + ", ".join(missing))
        return cls(values["FILONE_ENDPOINT"], values["FILONE_REGION"], values["FILONE_ACCESS_KEY"], values["FILONE_SECRET_KEY"], values["FILONE_BUCKET"])


def sanitize_filename(name: str) -> str:
    clean = Path(name).name.strip()
    if clean != name.strip() or not clean or ".." in clean:
        raise ValueError("Nome de arquivo inválido.")
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", clean)
    clean = re.sub(r"\.{2,}", "_", clean).strip("._")
    if not clean:
        raise ValueError("Nome de arquivo inválido.")
    return clean


def validate_upload_metadata(*, filename: str, mime_type: str, size_bytes: int) -> str:
    safe_name = sanitize_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    normalized_mime = mime_type.lower().split(";", 1)[0].strip()
    if suffix not in ALLOWED_SUFFIXES or normalized_mime not in ALLOWED_MIME_TYPES:
        raise ValueError("Tipo de arquivo não permitido.")
    if not isinstance(size_bytes, int) or not 0 < size_bytes <= MAX_DOCUMENT_BYTES:
        raise ValueError("Arquivo vazio ou acima do limite de 50 MB.")
    return safe_name


def build_storage_key(*, attendance_id: int, document_id: int, filename: str, organization_id: str | None = None) -> str:
    if attendance_id <= 0 or document_id <= 0:
        raise ValueError("Identificadores documentais inválidos.")
    safe_name = sanitize_filename(filename)
    # O segmento de organização é intencionalmente estável para futura multitenancy;
    # não contém CPF, nome ou outro dado pessoal.
    organization = organization_id or "unassigned"
    if not re.fullmatch(r"[A-Za-z0-9_-]+", organization):
        raise ValueError("Identificador de organização inválido.")
    return f"organizations/{organization}/attendances/{attendance_id}/documents/{document_id}/{uuid.uuid4().hex}/{safe_name}"


class FilOneStorageService:
    """Cliente S3 path-style conforme a documentação oficial do Fil One."""

    def __init__(self, config: FilOneConfig, client: Any) -> None:
        self._config = config
        self._client = client

    @classmethod
    def from_environment(cls) -> "FilOneStorageService":
        config = FilOneConfig.from_environment()
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover - covered by deployment requirements
            raise StorageConfigurationError("Dependência S3 ausente. Instale boto3 para usar o Fil One.") from exc
        client = boto3.client("s3", endpoint_url=config.endpoint, aws_access_key_id=config.access_key,
                              aws_secret_access_key=config.secret_key, region_name=config.region,
                              config=Config(s3={"addressing_style": "path"}))
        return cls(config, client)

    def upload(self, *, key: str, content: bytes, content_type: str) -> dict[str, Any]:
        return self._client.put_object(Bucket=self._config.bucket, Key=key, Body=content, ContentType=content_type)

    def create_presigned_upload_url(self, *, key: str, content_type: str, expires_in: int) -> str:
        return self._client.generate_presigned_url("put_object", Params={"Bucket": self._config.bucket, "Key": key, "ContentType": content_type}, ExpiresIn=expires_in, HttpMethod="PUT")

    def create_presigned_download_url(self, *, key: str, expires_in: int) -> str:
        return self._client.generate_presigned_url("get_object", Params={"Bucket": self._config.bucket, "Key": key}, ExpiresIn=expires_in, HttpMethod="GET")

    def exists(self, *, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._config.bucket, Key=key)
            return True
        except Exception as exc:
            if getattr(exc, "response", {}).get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def delete(self, *, key: str) -> None:
        self._client.delete_object(Bucket=self._config.bucket, Key=key)

    def get_metadata(self, *, key: str) -> dict[str, Any]:
        response = self._client.head_object(Bucket=self._config.bucket, Key=key)
        return {"key": key, "size_bytes": int(response.get("ContentLength", 0)), "mime_type": response.get("ContentType", ""), "etag": str(response.get("ETag", "")).strip('"'), "metadata": response.get("Metadata", {})}
