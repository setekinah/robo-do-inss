"""Armazenamento local de uploads da fase documental."""

from __future__ import annotations

import re
import os
import uuid
from pathlib import Path

from runtime_paths import DATA_DIR


UPLOADS_DIR = DATA_DIR / "uploads"
MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return sanitized or "arquivo"


def save_uploaded_document(attendance_id: int, document_code: str, uploaded_file) -> str:
    original_name = getattr(uploaded_file, "name", "arquivo.bin")
    return save_document_bytes(
        attendance_id=attendance_id,
        document_code=document_code,
        original_name=original_name,
        content=bytes(uploaded_file.getbuffer()),
    )


def save_document_bytes(
    *,
    attendance_id: int,
    document_code: str,
    original_name: str,
    content: bytes,
) -> str:
    """Persist API and Streamlit uploads using the same private storage policy."""
    target_dir = UPLOADS_DIR / f"atendimento_{attendance_id}"
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    safe_name = sanitize_filename(original_name)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("Formato de documento não permitido.")
    if not content or len(content) > MAX_DOCUMENT_BYTES:
        raise ValueError("Arquivo vazio ou acima do limite de 50 MB.")
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise ValueError("O arquivo informado como PDF não possui assinatura PDF válida.")

    # Impede que uploads com o mesmo nome sobrescrevam evidências anteriores.
    target_path = target_dir / f"{sanitize_filename(document_code)}_{uuid.uuid4().hex}_{safe_name}"

    descriptor = os.open(str(target_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
    except Exception:
        target_path.unlink(missing_ok=True)
        raise
    return str(target_path)
