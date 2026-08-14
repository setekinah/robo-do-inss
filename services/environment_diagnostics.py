"""Diagnóstico seguro do ambiente local de operação."""

from __future__ import annotations

import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from document_intelligence import get_ocr_capabilities


def _check_data_directory(data_dir: Path) -> dict[str, str]:
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".diagnostic-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return {"key": "data_directory", "label": "Diretório de dados", "status": "ok", "detail": "Gravação local disponível."}
    except OSError:
        return {"key": "data_directory", "label": "Diretório de dados", "status": "error", "detail": "Sem permissão de gravação. Verifique a pasta configurada para os dados locais."}


def _check_sqlite(database_path: Path) -> dict[str, str]:
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        try:
            connection.execute("SELECT 1")
        finally:
            connection.close()
        return {"key": "sqlite", "label": "Banco local", "status": "ok", "detail": "SQLite disponível para leitura e gravação."}
    except sqlite3.Error:
        return {"key": "sqlite", "label": "Banco local", "status": "error", "detail": "Não foi possível abrir o banco local. Restaure um backup ou verifique permissões."}


def build_environment_diagnostic(
    data_dir: Path,
    database_path: Path,
    capabilities_provider: Callable[[], dict[str, Any]] = get_ocr_capabilities,
) -> dict[str, Any]:
    """Retorna um snapshot sem PII nem caminho absoluto do usuário."""
    checks = [
        {
            "key": "python",
            "label": "Python",
            "status": "ok" if sys.version_info >= (3, 10) else "error",
            "detail": f"Versão {sys.version_info.major}.{sys.version_info.minor} detectada.",
        },
        _check_data_directory(Path(data_dir)),
        _check_sqlite(Path(database_path)),
    ]
    capabilities = capabilities_provider()
    checks.append({
        "key": "pdf",
        "label": "Leitura de PDF",
        "status": "ok" if capabilities["pdf_ready"] else "error",
        "detail": "Leitura de PDF disponível." if capabilities["pdf_ready"] else "PyMuPDF não está disponível. Reinstale as dependências do aplicativo.",
    })
    checks.append({
        "key": "neural_ocr",
        "label": "OCR local",
        "status": "ok" if capabilities["neural_ready"] else "warning",
        "detail": "OCR neural local disponível." if capabilities["neural_ready"] else "OCR neural indisponível; PDFs nativos ainda podem ser lidos quando houver texto.",
    })
    checks.append({
        "key": "tesseract",
        "label": "Fallback Tesseract",
        "status": "ok" if capabilities["tesseract_ready"] else "warning",
        "detail": "Fallback OCR disponível." if capabilities["tesseract_ready"] else "Opcional e não instalado; o OCR neural continua sendo o mecanismo principal.",
    })
    overall = "error" if any(item["status"] == "error" for item in checks) else "warning" if any(item["status"] == "warning" for item in checks) else "ok"
    return {"status": overall, "checks": checks, "privacy_mode": capabilities.get("privacy_mode", "local")}
