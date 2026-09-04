"""Despacho opcional e minimizado de notificações operacionais.

Nenhum destino é acionado por padrão. O módulo nunca recebe nem serializa CNIS,
CPF, nome do cliente, documentos ou conteúdo de dossiê.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


ALLOWED_EVENT_TYPES = {"pendencia_inteligente", "dossie_requer_revisao", "assinatura_atualizada"}


def _allowed_hosts() -> set[str]:
    return {item.strip().lower() for item in os.environ.get("ROBO_INSS_NOTIFICATION_ALLOWED_HOSTS", "").split(",") if item.strip()}


def _configuration() -> tuple[str, str, set[str]]:
    url = os.environ.get("ROBO_INSS_NOTIFICATION_WEBHOOK_URL", "").strip()
    secret = os.environ.get("ROBO_INSS_NOTIFICATION_WEBHOOK_SECRET", "").strip()
    return url, secret, _allowed_hosts()


def build_minimal_payload(*, event_type: str, attendance_id: int, event_id: str) -> dict[str, str | int]:
    """Create a payload containing only the operational identifiers needed by a queue."""
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError("Tipo de notificação não permitido.")
    if attendance_id <= 0 or not event_id.strip():
        raise ValueError("Identificador operacional inválido.")
    return {
        "event_type": event_type,
        "case_id": attendance_id,
        "event_id": event_id.strip(),
        "message": "Há uma atualização operacional para revisão no PrevIA.",
    }


def dispatch(*, event_type: str, attendance_id: int, event_id: str, timeout_seconds: int = 5) -> dict[str, Any]:
    """Send a signed minimal event only after explicit environment configuration.

    Return values intentionally omit webhook URL, secret and request body.
    """
    payload = build_minimal_payload(event_type=event_type, attendance_id=attendance_id, event_id=event_id)
    url, secret, hosts = _configuration()
    if os.environ.get("ROBO_INSS_NOTIFICATION_ENABLED") != "1":
        return {"sent": False, "reason": "notificacoes_desativadas", "event_id": payload["event_id"]}
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() not in hosts:
        return {"sent": False, "reason": "destino_nao_autorizado", "event_id": payload["event_id"]}
    if not secret:
        return {"sent": False, "reason": "segredo_ausente", "event_id": payload["event_id"]}

    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = hmac.new(secret.encode("utf-8"), timestamp.encode("ascii") + b"." + body, hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-PrevIA-Timestamp": timestamp,
            "X-PrevIA-Signature": signature,
            "Idempotency-Key": str(payload["event_id"]),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=max(1, min(timeout_seconds, 15))) as response:
            delivered = 200 <= response.status < 300
            return {"sent": delivered, "reason": "entregue" if delivered else "resposta_nao_sucesso", "event_id": payload["event_id"]}
    except (OSError, urllib.error.URLError):
        return {"sent": False, "reason": "falha_de_entrega", "event_id": payload["event_id"]}
