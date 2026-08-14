"""Persistência auditável de prévias CNIS extraídas localmente."""

from __future__ import annotations

import json
from typing import Any

from database import get_connection


class CnisImportRepository:
    def create(self, attendance_id: int, file_path: str, preview: dict[str, Any]) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO importacoes_cnis
                (attendance_id, file_path, extraction_status, confidence, fields_json, technical_notes, text_excerpt)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (attendance_id, file_path, preview["extraction_status"], preview["confidence"],
                 json.dumps(preview["fields"], ensure_ascii=False), preview["technical_notes"], preview["text_excerpt"]),
            )
            return int(cursor.lastrowid)

    def list_for_attendance(self, attendance_id: int) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM importacoes_cnis WHERE attendance_id = ? ORDER BY id DESC", (attendance_id,)).fetchall()
        return [
            {"id": int(row["id"]), "created_at": str(row["created_at"]), "file_path": str(row["file_path"]),
             "extraction_status": str(row["extraction_status"]), "confidence": float(row["confidence"]),
             "fields": json.loads(row["fields_json"]), "technical_notes": str(row["technical_notes"]),
             "confirmed_at": row["confirmed_at"]}
            for row in rows
        ]

    def confirm(self, import_id: int) -> None:
        with get_connection() as conn:
            cursor = conn.execute("UPDATE importacoes_cnis SET confirmed_at = CURRENT_TIMESTAMP WHERE id = ?", (import_id,))
            if cursor.rowcount != 1:
                raise ValueError("Importação CNIS não encontrada.")
