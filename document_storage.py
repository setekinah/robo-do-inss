"""Armazenamento local de uploads da fase documental."""

from __future__ import annotations

import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "data" / "uploads"


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return sanitized or "arquivo"


def save_uploaded_document(attendance_id: int, document_code: str, uploaded_file) -> str:
    target_dir = UPLOADS_DIR / f"atendimento_{attendance_id}"
    target_dir.mkdir(parents=True, exist_ok=True)

    original_name = getattr(uploaded_file, "name", "arquivo.bin")
    safe_name = sanitize_filename(original_name)
    target_path = target_dir / f"{document_code}_{safe_name}"

    target_path.write_bytes(uploaded_file.getbuffer())
    return str(target_path)
