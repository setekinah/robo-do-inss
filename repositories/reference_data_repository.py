"""Repositório SQLite para conjuntos de referência versionados."""

from __future__ import annotations

import json
from typing import Any

from database import get_connection
from services.reference_data_service import ReferenceDataset, validate_reference_dataset


class ReferenceDataRepository:
    def save(self, dataset: ReferenceDataset) -> int:
        validate_reference_dataset(dataset)
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO referencias_calculo
                (kind, version, source_url, effective_date, data_json)
                VALUES (?, ?, ?, ?, ?)""",
                (dataset.kind, dataset.version, dataset.source_url, dataset.effective_date.isoformat(), json.dumps(dataset.data, ensure_ascii=False)),
            )
            return int(cursor.lastrowid)

    def latest(self, kind: str) -> ReferenceDataset | None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM referencias_calculo WHERE kind = ? ORDER BY id DESC LIMIT 1", (kind,)).fetchone()
        if row is None:
            return None
        from datetime import date
        return ReferenceDataset(str(row["kind"]), str(row["version"]), str(row["source_url"]), date.fromisoformat(str(row["effective_date"])), json.loads(row["data_json"]))
