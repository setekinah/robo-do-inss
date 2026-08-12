"""Resolve paths for local operational data outside the source checkout."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def resolve_data_dir() -> Path:
    """Return a writable user-data directory, falling back only when necessary."""
    configured = os.environ.get("ROBO_INSS_DATA_DIR")
    preferred = Path(os.environ.get("LOCALAPPDATA", BASE_DIR)) / "Robo do INSS" / "data"
    fallback = BASE_DIR / "data"
    candidates = (Path(configured).expanduser(),) if configured else (preferred, fallback)

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return candidate
        except OSError:
            continue

    return fallback


DATA_DIR = resolve_data_dir()


def write_private_text(path: Path, content: str) -> None:
    """Atomically persist a small local secret/configuration file.

    The application is local-first, so this is not a replacement for disk
    encryption.  It does, however, avoid partially-written credential and
    settings files and applies the most restrictive portable file mode.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.",
        suffix=".tmp", delete=False
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    try:
        try:
            os.chmod(temporary_path, 0o600)
        except OSError:
            pass
        temporary_path.replace(path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        temporary_path.unlink(missing_ok=True)
