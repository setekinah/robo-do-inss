"""Logs locais estruturados, com remoção de dados pessoais e conteúdo documental."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LOGS_DIR_NAME = "logs"
LOG_FILE_NAME = "technical-events.jsonl"
SENSITIVE_FIELD_MARKERS = ("password", "senha", "token", "cookie", "cpf", "nit", "nis", "email", "phone", "whatsapp", "document", "text", "content", "path")


def _safe_context(context: dict[str, Any] | None) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in (context or {}).items():
        normalized = str(key).casefold()
        if any(marker in normalized for marker in SENSITIVE_FIELD_MARKERS):
            safe[str(key)] = "[redacted]"
        elif isinstance(value, (str, int, float, bool)) or value is None:
            safe[str(key)] = value
        else:
            safe[str(key)] = "[structured-value]"
    return safe


def log_technical_event(
    data_dir: Path,
    *,
    event: str,
    level: str = "info",
    component: str,
    correlation_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persiste um evento JSONL local sem conteúdo de cliente ou documento."""
    if level not in {"info", "warning", "error"}:
        raise ValueError("Nível de log inválido.")
    logs_dir = Path(data_dir) / LOGS_DIR_NAME
    logs_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "level": level,
        "event": event,
        "component": component,
        "correlation_id": correlation_id or "",
        "context": _safe_context(context),
    }
    with (logs_dir / LOG_FILE_NAME).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    return record


def read_recent_events(data_dir: Path, limit: int = 20) -> list[dict[str, Any]]:
    log_path = Path(data_dir) / LOGS_DIR_NAME / LOG_FILE_NAME
    if not log_path.is_file():
        return []
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()[-max(1, limit):]
        return [json.loads(line) for line in reversed(lines) if line.strip()]
    except (OSError, json.JSONDecodeError):
        return []
