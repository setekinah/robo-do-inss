"""Armazenamento local de uploads da fase documental."""

from __future__ import annotations

import re
from pathlib import Path

from runtime_paths import DATA_DIR


UPLOADS_DIR = DATA_DIR / "uploads"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
SIGNATURES = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".tif": (b"II*\x00", b"MM\x00*"),
    ".tiff": (b"II*\x00", b"MM\x00*"),
    ".bmp": (b"BM",),
    ".webp": (b"RIFF",),
}


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return sanitized or "arquivo"


def validate_uploaded_document(name: str, content: bytes) -> None:
    """Confere extensão e assinatura binária antes de persistir o arquivo."""
    suffix = Path(name).suffix.lower()
    if suffix not in SIGNATURES:
        raise ValueError("Formato não permitido. Envie PDF, PNG, JPG, TIFF, BMP ou WEBP.")
    if not content:
        raise ValueError("O arquivo enviado está vazio.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("O arquivo excede o limite de 50 MB para processamento local.")
    if not any(content.startswith(signature) for signature in SIGNATURES[suffix]):
        raise ValueError("O conteúdo do arquivo não corresponde à extensão informada. Selecione o documento original.")
    if suffix == ".webp" and content[8:12] != b"WEBP":
        raise ValueError("O conteúdo do arquivo não corresponde a uma imagem WEBP válida.")


def save_uploaded_document(attendance_id: int, document_code: str, uploaded_file) -> str:
    target_dir = UPLOADS_DIR / f"atendimento_{attendance_id}"
    target_dir.mkdir(parents=True, exist_ok=True)

    original_name = getattr(uploaded_file, "name", "arquivo.bin")
    content = bytes(uploaded_file.getbuffer())
    validate_uploaded_document(original_name, content)
    safe_name = sanitize_filename(original_name)
    target_path = target_dir / f"{document_code}_{safe_name}"

    target_path.write_bytes(content)
    return str(target_path)
