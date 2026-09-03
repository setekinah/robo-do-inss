"""Local multi-user credential storage with salted password hashing."""
from __future__ import annotations

import base64, hashlib, hmac, json, os, re, secrets, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from runtime_paths import DATA_DIR

CREDENTIALS_PATH = DATA_DIR / "auth_credentials.json"
PBKDF2_ITERATIONS = 600_000
SESSION_TTL_SECONDS = 8 * 60 * 60
MAX_ACTIVE_SESSIONS = 256
_SESSIONS: dict[str, tuple[float, str]] = {}
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

def normalize_email(email: str) -> str: return email.strip().casefold()
def validate_email(email: str) -> str | None:
    return None if _EMAIL_PATTERN.fullmatch(normalize_email(email)) else "Informe um e-mail profissional válido."
def validate_password(password: str) -> str | None:
    if len(password) < 10: return "A senha deve ter pelo menos 10 caracteres."
    if not re.search(r"[A-Z]", password): return "Inclua pelo menos uma letra maiúscula na senha."
    if not re.search(r"[a-z]", password): return "Inclua pelo menos uma letra minúscula na senha."
    if not re.search(r"\d", password): return "Inclua pelo menos um número na senha."
    return None
def validate_whatsapp(value: str) -> str | None:
    return None if 10 <= len(re.sub(r"\D", "", value)) <= 13 else "Informe um WhatsApp com DDD válido."

def _load_users() -> list[dict[str, Any]]:
    if not CREDENTIALS_PATH.exists(): return []
    try: payload = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return []
    raw_users = payload.get("users") if isinstance(payload, dict) else None
    if raw_users is None and isinstance(payload, dict): raw_users = [payload]
    if not isinstance(raw_users, list): return []
    users = []
    for raw in raw_users:
        try:
            email = normalize_email(str(raw["email"])); salt = base64.b64decode(raw["salt"], validate=True)
            password_hash = base64.b64decode(raw["password_hash"], validate=True); iterations = int(raw["iterations"])
        except (ValueError, TypeError, KeyError): continue
        if email and salt and password_hash and iterations >= 100_000:
            users.append({"email": email, "salt": salt, "password_hash": password_hash, "iterations": iterations})
    return users

def _save_users(users: list[dict[str, Any]]) -> None:
    payload = {"version": 2, "updated_at": datetime.now(timezone.utc).isoformat(), "users": [
        {"email": u["email"], "salt": base64.b64encode(u["salt"]).decode("ascii"), "password_hash": base64.b64encode(u["password_hash"]).decode("ascii"), "iterations": u["iterations"]} for u in users]}
    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = Path(f"{CREDENTIALS_PATH}.tmp"); temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8"); temporary_path.replace(CREDENTIALS_PATH)
    try: os.chmod(CREDENTIALS_PATH, 0o600)
    except OSError: pass

def credentials_configured() -> bool: return bool(_load_users())
def user_count() -> int: return len(_load_users())
def save_credentials(email: str, password: str) -> None:
    if credentials_configured(): raise ValueError("Já existe uma conta configurada.")
    create_user(email, password)
def create_user(email: str, password: str) -> str:
    email = normalize_email(email); error = validate_email(email) or validate_password(password)
    if error: raise ValueError(error)
    users = _load_users()
    if any(user["email"] == email for user in users): raise ValueError("Já existe uma conta com este e-mail.")
    salt = secrets.token_bytes(16); password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    users.append({"email": email, "salt": salt, "password_hash": password_hash, "iterations": PBKDF2_ITERATIONS}); _save_users(users); return email
def authenticate(email: str, password: str) -> str | None:
    for user in _load_users():
        if normalize_email(email) == user["email"]:
            candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), user["salt"], user["iterations"])
            return user["email"] if hmac.compare_digest(candidate, user["password_hash"]) else None
    return None
def verify_credentials(email: str, password: str) -> bool: return authenticate(email, password) is not None
def _purge(now: float) -> None:
    for key, (expires, _) in list(_SESSIONS.items()):
        if expires <= now: _SESSIONS.pop(key, None)
def create_session(user_email: str = "") -> str:
    now = time.time(); _purge(now)
    if len(_SESSIONS) >= MAX_ACTIVE_SESSIONS: _SESSIONS.pop(min(_SESSIONS, key=lambda key: _SESSIONS[key][0]), None)
    token = secrets.token_urlsafe(32); _SESSIONS[hashlib.sha256(token.encode()).hexdigest()] = (now + SESSION_TTL_SECONDS, normalize_email(user_email)); return token
def get_session_user(token: str) -> str | None:
    _purge(time.time()); entry = _SESSIONS.get(hashlib.sha256((token or "").encode()).hexdigest()); return entry[1] if entry else None
def verify_session(token: str) -> bool: return get_session_user(token) is not None
def revoke_session(token: str) -> None: _SESSIONS.pop(hashlib.sha256((token or "").encode()).hexdigest(), None)
