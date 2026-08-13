"""Persistência SQLite auditável para solicitações e resultados de cálculo."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from database import get_connection


@dataclass(frozen=True)
class CalculationRecord:
    id: int
    attendance_id: int
    calculation_type: str
    title: str
    inputs: dict[str, Any]
    result: dict[str, Any] | None
    ruleset_version: str
    status: str
    requires_human_review: bool
    created_at: str
    updated_at: str
    review_notes: str | None
    reviewed_at: str | None


class CalculationRepository:
    def create(
        self,
        *,
        attendance_id: int,
        calculation_type: str,
        title: str,
        inputs: dict[str, Any],
        ruleset_version: str,
        requires_human_review: bool = True,
    ) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO calculos_previdenciarios (
                    attendance_id, calculation_type, title, inputs_json,
                    ruleset_version, requires_human_review
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (attendance_id, calculation_type, title, json.dumps(inputs, ensure_ascii=False), ruleset_version, int(requires_human_review)),
            )
            return int(cursor.lastrowid)

    def save_result(self, calculation_id: int, result: dict[str, Any], status: str = "aguardando_revisao") -> None:
        if status not in {"rascunho", "aguardando_revisao", "revisado", "cancelado"}:
            raise ValueError("Status de cálculo inválido.")
        with get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE calculos_previdenciarios
                SET result_json = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(result, ensure_ascii=False), status, calculation_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Cálculo não encontrado.")

    def list_for_attendance(self, attendance_id: int) -> list[CalculationRecord]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM calculos_previdenciarios WHERE attendance_id = ? ORDER BY id DESC",
                (attendance_id,),
            ).fetchall()
        return [self._to_record(row) for row in rows]

    def mark_reviewed(self, calculation_id: int, review_notes: str) -> None:
        if not review_notes.strip():
            raise ValueError("Registre a observação da revisão antes de concluir.")
        with get_connection() as conn:
            cursor = conn.execute(
                """UPDATE calculos_previdenciarios
                SET status = 'revisado', review_notes = ?, reviewed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'aguardando_revisao'""",
                (review_notes.strip(), calculation_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Cálculo não está disponível para revisão.")

    @staticmethod
    def _to_record(row: Any) -> CalculationRecord:
        return CalculationRecord(
            id=int(row["id"]), attendance_id=int(row["attendance_id"]), calculation_type=str(row["calculation_type"]),
            title=str(row["title"]), inputs=json.loads(row["inputs_json"]),
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            ruleset_version=str(row["ruleset_version"]), status=str(row["status"]),
            requires_human_review=bool(row["requires_human_review"]), created_at=str(row["created_at"]), updated_at=str(row["updated_at"]),
            review_notes=str(row["review_notes"]) if row["review_notes"] else None,
            reviewed_at=str(row["reviewed_at"]) if row["reviewed_at"] else None,
        )
