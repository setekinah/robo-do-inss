"""Configuração e verificação local da integração com DocuSeal.

O token é mantido fora do repositório, no diretório privado de dados do
usuário. Nenhuma rota HTTP devolve esse segredo ao navegador.
"""

from __future__ import annotations

import json
import os
import hashlib
import hmac
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from runtime_paths import DATA_DIR


CONFIG_PATH = DATA_DIR / "docuseal.json"
DEFAULT_URL = "http://127.0.0.1:3000"


def _read_config() -> dict[str, str]:
    try:
        # Windows PowerShell 5 pode gerar UTF-8 com BOM; aceite os dois
        # formatos para não exigir que o usuário recopie a chave.
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def get_connection_config() -> tuple[str, str]:
    """Return URL and token, preferring explicit process environment variables."""
    stored = _read_config()
    url = os.environ.get("DOCUSEAL_URL", stored.get("url", DEFAULT_URL)).rstrip("/")
    token = os.environ.get("DOCUSEAL_API_TOKEN", stored.get("api_token", "")).strip()
    return url, token


def status() -> dict[str, Any]:
    url, token = get_connection_config()
    stored = _read_config()
    return {
        "configured": bool(token),
        "url": url,
        "template_configured": bool(stored.get("template_id")),
        "storage": str(CONFIG_PATH.parent),
    }


def verify_connection(timeout_seconds: int = 8) -> dict[str, Any]:
    """Validate the token against the local service without exposing it."""
    result = status()
    if not result["configured"]:
        return {**result, "connected": False, "message": "Token DocuSeal ainda não configurado."}

    url, token = get_connection_config()
    request = urllib.request.Request(
        f"{url}/api/templates",
        headers={"X-Auth-Token": token, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            result["connected"] = 200 <= response.status < 300
            result["message"] = "DocuSeal conectado." if result["connected"] else "DocuSeal respondeu com erro."
    except urllib.error.HTTPError as exc:
        result.update({"connected": False, "message": f"DocuSeal recusou a chave ({exc.code})."})
    except (urllib.error.URLError, TimeoutError, OSError):
        result.update({"connected": False, "message": "Não foi possível alcançar o DocuSeal local."})
    return result


def create_submission(*, client_name: str, client_email: str, office_name: str, office_email: str, attendance_id: int) -> dict[str, Any]:
    """Create a signing request only after an explicit CRM action."""
    stored = _read_config()
    url, token = get_connection_config()
    template_id = stored.get("template_id")
    if not token or not template_id:
        raise ValueError("DocuSeal ou modelo contratual não configurado.")
    payload = {
        "template_id": int(template_id), "send_email": True, "order": "preserved",
        "submitters": [
            {"role": "CONTRATANTE", "name": client_name, "email": client_email,
             "external_id": f"attendance:{attendance_id}:client"},
            {"role": "CONTRATADA", "name": office_name, "email": office_email,
             "external_id": f"attendance:{attendance_id}:office"},
        ],
    }
    request = urllib.request.Request(
        f"{url}/api/submissions", data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"X-Auth-Token": token, "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise ValueError(f"DocuSeal recusou a solicitação ({exc.code}): {detail}") from exc


def verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    """Validate DocuSeal HMAC over the unmodified request payload."""
    secret = _read_config().get("webhook_hmac_secret", "").strip()
    if not secret or not signature_header:
        return False
    timestamp, separator, received = signature_header.partition(".")
    if not separator or not timestamp.isdigit() or not received:
        return False
    if abs(time.time() - int(timestamp)) > 300:
        return False
    signed_content = timestamp.encode("ascii") + b"." + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed_content, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)


def verify_webhook_path_token(candidate: str) -> bool:
    expected = _read_config().get("webhook_path_token", "").strip()
    return bool(expected) and hmac.compare_digest(expected, candidate)
