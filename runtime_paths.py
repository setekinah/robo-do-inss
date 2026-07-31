"""Resolve paths for local operational data outside the source checkout."""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def resolve_data_dir() -> Path:
    """Return a writable user-data directory, falling back only when necessary."""
    preferred = Path(os.environ.get("LOCALAPPDATA", BASE_DIR)) / "Robo do INSS" / "data"
    fallback = BASE_DIR / "data"

    for candidate in (preferred, fallback):
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
