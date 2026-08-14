"""Armazenamento local de uploads da fase documental."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from runtime_paths import DATA_DIR


UPLOADS_DIR = DATA_DIR / "uploads"
ALLOWED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def _upload_limit_bytes() -> int:
    try:
        file_limit_mb = int(os.environ.get("DOCUMENT_MAX_FILE_MB", "50"))
    except ValueError:
        file_limit_mb = 50
    return min(max(file_limit_mb, 1), 250) * 1024 * 1024


MAX_UPLOAD_BYTES = _upload_limit_bytes()


def _make_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def _has_valid_signature(content: bytes, suffix: str) -> bool:
    """Reject files whose content does not match the extension offered to the OCR pipeline."""
    if suffix == ".pdf":
        return content.startswith(b"%PDF-")
    if suffix == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    if suffix in {".tif", ".tiff"}:
        return content.startswith((b"II*\x00", b"MM\x00*"))
    if suffix == ".bmp":
        return content.startswith(b"BM")
    if suffix == ".webp":
        return len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    return False


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    sanitized = sanitized.replace("..", "_").lstrip("._")
    return sanitized or "arquivo"


def save_uploaded_document(attendance_id: int, document_code: str, uploaded_file: Any) -> str:
    """Persist a supported document safely, without allowing name collisions or oversized files."""
    if attendance_id <= 0:
        raise ValueError("Atendimento inválido para o upload.")

    original_name = str(getattr(uploaded_file, "name", "arquivo.bin"))
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("Formato de arquivo não permitido.")

    content = bytes(uploaded_file.getbuffer())
    if not content:
        raise ValueError("Não é possível salvar um arquivo vazio.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"O arquivo excede o limite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )
    if not _has_valid_signature(content, suffix):
        raise ValueError("O conteúdo do arquivo não corresponde ao formato informado.")

    _make_private_directory(UPLOADS_DIR)
    target_dir = UPLOADS_DIR / f"atendimento_{attendance_id}"
    _make_private_directory(target_dir)
    safe_name = sanitize_filename(original_name)
    safe_document_code = sanitize_filename(document_code)
    content_digest = hashlib.sha256(content).hexdigest()[:12]
    target_path = target_dir / f"{safe_document_code}_{content_digest}_{safe_name}"

    if not target_path.exists():
        temporary_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
        temporary_path.write_bytes(content)
        try:
            os.chmod(temporary_path, 0o600)
        except OSError:
            pass
        temporary_path.replace(target_path)
        try:
            os.chmod(target_path, 0o600)
        except OSError:
            pass
    return str(target_path)
