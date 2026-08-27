"""Armazenamento local de uploads da fase documental."""

from __future__ import annotations

import re
from pathlib import Path

from runtime_paths import DATA_DIR


UPLOADS_DIR = DATA_DIR / "uploads"
MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return sanitized or "arquivo"


def sanitize_document_code(code: str) -> str:
    """Return a filesystem-safe document identifier.

    Document codes are persisted as part of the filename. Keeping this separate
    from the user-provided filename prevents a malformed integration payload
    from changing the target directory.
    """
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "_", str(code).strip())
    return sanitized.strip("._-")


def save_uploaded_document(attendance_id: int, document_code: str, uploaded_file) -> str:
    if attendance_id <= 0:
        raise ValueError("Atendimento invalido para armazenamento de documento.")

    safe_code = sanitize_document_code(document_code)
    if not safe_code:
        raise ValueError("Codigo de documento invalido.")

    content = uploaded_file.getbuffer()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError("O documento excede o limite de 25 MB.")

    target_dir = UPLOADS_DIR / f"atendimento_{attendance_id}"
    target_dir.mkdir(parents=True, exist_ok=True)

    original_name = getattr(uploaded_file, "name", "arquivo.bin")
    safe_name = sanitize_filename(original_name)
    target_path = target_dir / f"{safe_code}_{safe_name}"

    target_path.write_bytes(content)
    return str(target_path)
