"""Local credential storage with salted password hashing for SOFI.IA PREVI."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime_paths import DATA_DIR


CREDENTIALS_PATH = DATA_DIR / "auth_credentials.json"
PBKDF2_ITERATIONS = 600_000
SESSION_TTL_SECONDS = 8 * 60 * 60
MAX_ACTIVE_SESSIONS = 256
_SESSIONS: dict[str, float] = {}
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def validate_email(email: str) -> str | None:
    if not _EMAIL_PATTERN.fullmatch(normalize_email(email)):
        return "Informe um e-mail profissional válido."
    return None


def validate_password(password: str) -> str | None:
    if len(password) < 10:
        return "A senha deve ter pelo menos 10 caracteres."
    if not re.search(r"[A-Z]", password):
        return "Inclua pelo menos uma letra maiúscula na senha."
    if not re.search(r"[a-z]", password):
        return "Inclua pelo menos uma letra minúscula na senha."
    if not re.search(r"\d", password):
        return "Inclua pelo menos um número na senha."
    return None


def validate_whatsapp(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if not 10 <= len(digits) <= 13:
        return "Informe um WhatsApp com DDD válido."
    return None


def credentials_configured() -> bool:
    return _load_credentials() is not None


def save_credentials(email: str, password: str) -> None:
    normalized_email = normalize_email(email)
    email_error = validate_email(normalized_email)
    password_error = validate_password(password)
    if email_error or password_error:
        raise ValueError(email_error or password_error)

    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    payload = {
        "version": 1,
        "email": normalized_email,
        "salt": base64.b64encode(salt).decode("ascii"),
        "password_hash": base64.b64encode(password_hash).decode("ascii"),
        "iterations": PBKDF2_ITERATIONS,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = Path(f"{CREDENTIALS_PATH}.tmp")
    temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary_path.replace(CREDENTIALS_PATH)
    try:
        os.chmod(CREDENTIALS_PATH, 0o600)
    except OSError:
        # On Windows, the effective ACL may be controlled by the user profile.
        pass


def verify_credentials(email: str, password: str) -> bool:
    credentials = _load_credentials()
    if credentials is None or normalize_email(email) != credentials["email"]:
        return False

    candidate_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        credentials["salt"],
        credentials["iterations"],
    )
    return hmac.compare_digest(candidate_hash, credentials["password_hash"])


def create_session() -> str:
    """Cria uma sessão opaca; somente o hash fica em memória no servidor."""
    now = time.time()
    for session_key, expiry in list(_SESSIONS.items()):
        if expiry <= now:
            _SESSIONS.pop(session_key, None)
    if len(_SESSIONS) >= MAX_ACTIVE_SESSIONS:
        oldest_key = min(_SESSIONS, key=_SESSIONS.get)
        _SESSIONS.pop(oldest_key, None)
    token = secrets.token_urlsafe(32)
    _SESSIONS[hashlib.sha256(token.encode("utf-8")).hexdigest()] = now + SESSION_TTL_SECONDS
    return token


def verify_session(token: str) -> bool:
    now = time.time()
    key = hashlib.sha256((token or "").encode("utf-8")).hexdigest()
    expires_at = _SESSIONS.get(key, 0)
    for session_key, expiry in list(_SESSIONS.items()):
        if expiry <= now:
            _SESSIONS.pop(session_key, None)
    return expires_at > now


def revoke_session(token: str) -> None:
    _SESSIONS.pop(hashlib.sha256((token or "").encode("utf-8")).hexdigest(), None)


def _load_credentials() -> dict[str, Any] | None:
    if not CREDENTIALS_PATH.exists():
        return None
    try:
        payload = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
        email = normalize_email(str(payload["email"]))
        salt = base64.b64decode(payload["salt"], validate=True)
        password_hash = base64.b64decode(payload["password_hash"], validate=True)
        iterations = int(payload["iterations"])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
    if not email or not salt or not password_hash or iterations < 100_000:
        return None
    return {
        "email": email,
        "salt": salt,
        "password_hash": password_hash,
        "iterations": iterations,
    }
