"""Persistencia simples das configuracoes do escritorio SOFI.IA PREVI."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "data" / "office_settings.json"


DEFAULT_OFFICE_SETTINGS: dict[str, Any] = {
    "responsavel_nome": "",
    "responsavel_email": "",
    "responsavel_whatsapp": "",
    "plano": "Essencial",
    "office_name": "",
    "oab": "",
    "tutorial_video_url": "",
    "fee_percentages": {
        "Aposentadoria Programada": 30,
        "BPC/LOAS": 30,
        "Pensao por Morte": 30,
        "Auxilio por Incapacidade": 30,
        "Aposentadoria Especial": 30,
        "Outros": 30,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_office_settings() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return deepcopy(DEFAULT_OFFICE_SETTINGS)

    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return deepcopy(DEFAULT_OFFICE_SETTINGS)

    return _deep_merge(DEFAULT_OFFICE_SETTINGS, data)


def save_office_settings(settings: dict[str, Any]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged = _deep_merge(DEFAULT_OFFICE_SETTINGS, settings)
    SETTINGS_PATH.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def resolve_fee_percentage(flow_name: str, settings: dict[str, Any]) -> int:
    category_map = {
        "Aposentadoria": "Aposentadoria Programada",
        "BPC/LOAS": "BPC/LOAS",
        "Pensao por Morte": "Pensao por Morte",
        "Auxilio-Doenca": "Auxilio por Incapacidade",
        "Aposentadoria por Invalidez": "Auxilio por Incapacidade",
        "Auxilio-Acidente": "Auxilio por Incapacidade",
        "Aposentadoria Especial": "Aposentadoria Especial",
    }
    category = category_map.get(flow_name, "Outros")
    percentages = settings.get("fee_percentages", {})
    try:
        return int(percentages.get(category, 30))
    except (TypeError, ValueError):
        return 30
