"""Persistencia local em SQLite para atendimentos e respostas."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from document_rules import build_document_checklist
from runtime_paths import DATA_DIR


DB_PATH = DATA_DIR / "triagem.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_database() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS atendimentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                lead_name TEXT NOT NULL,
                lead_phone TEXT,
                flow_id TEXT NOT NULL,
                flow_name TEXT NOT NULL,
                status TEXT NOT NULL,
                result_title TEXT NOT NULL,
                summary TEXT NOT NULL,
                next_step TEXT NOT NULL,
                notes TEXT,
                history_json TEXT NOT NULL,
                benefit_category TEXT,
                estimated_monthly_value REAL,
                estimated_total_value REAL
            )
            """
        )
        ensure_column(conn, "benefit_category", "TEXT")
        ensure_column(conn, "estimated_monthly_value", "REAL")
        ensure_column(conn, "estimated_total_value", "REAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS atendimento_documentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attendance_id INTEGER NOT NULL,
                flow_id TEXT NOT NULL,
                document_code TEXT NOT NULL,
                document_name TEXT NOT NULL,
                category TEXT NOT NULL,
                required INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'pendente',
                notes TEXT,
                critical_fields_json TEXT NOT NULL,
                uploaded_files_json TEXT,
                raw_text TEXT,
                extracted_data_json TEXT,
                source_type TEXT,
                extraction_status TEXT,
                extraction_confidence REAL,
                technical_notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(attendance_id, document_code)
            )
            """
        )
        ensure_document_column(conn, "raw_text", "TEXT")
        ensure_document_column(conn, "extracted_data_json", "TEXT")
        ensure_document_column(conn, "source_type", "TEXT")
        ensure_document_column(conn, "extraction_status", "TEXT")
        ensure_document_column(conn, "extraction_confidence", "REAL")
        ensure_document_column(conn, "technical_notes", "TEXT")
        backfill_document_checklists(conn)
        conn.commit()


def ensure_column(conn: sqlite3.Connection, column_name: str, column_type: str) -> None:
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(atendimentos)").fetchall()
    }
    if column_name not in columns:
        conn.execute(f"ALTER TABLE atendimentos ADD COLUMN {column_name} {column_type}")


def ensure_document_column(conn: sqlite3.Connection, column_name: str, column_type: str) -> None:
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(atendimento_documentos)").fetchall()
    }
    if column_name not in columns:
        conn.execute(
            f"ALTER TABLE atendimento_documentos ADD COLUMN {column_name} {column_type}"
        )


def save_attendance(
    *,
    lead_name: str,
    lead_phone: str,
    flow_id: str,
    flow_name: str,
    status: str,
    result_title: str,
    summary: str,
    next_step: str,
    notes: str,
    history: list[dict[str, Any]],
    benefit_category: str | None = None,
    estimated_monthly_value: float | None = None,
    estimated_total_value: float | None = None,
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO atendimentos (
                lead_name,
                lead_phone,
                flow_id,
                flow_name,
                status,
                result_title,
                summary,
                next_step,
                notes,
                history_json,
                benefit_category,
                estimated_monthly_value,
                estimated_total_value
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lead_name,
                lead_phone,
                flow_id,
                flow_name,
                status,
                result_title,
                summary,
                next_step,
                notes,
                json.dumps(history, ensure_ascii=True),
                benefit_category,
                estimated_monthly_value,
                estimated_total_value,
            ),
        )
        attendance_id = int(cursor.lastrowid)
        if status in {"aprovado", "revisao"}:
            seed_document_checklist(conn, attendance_id=attendance_id, flow_id=flow_id)
        conn.commit()
        return attendance_id


def list_recent_attendances(limit: int = 10) -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                created_at,
                lead_name,
                flow_name,
                status,
                result_title
            FROM atendimentos
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return rows


def search_attendances(
    *,
    lead_query: str = "",
    flow_name: str = "",
    status: str = "",
    limit: int = 50,
) -> list[sqlite3.Row]:
    conditions: list[str] = []
    params: list[Any] = []

    if lead_query:
        conditions.append("(lead_name LIKE ? OR lead_phone LIKE ?)")
        like = f"%{lead_query}%"
        params.extend([like, like])
    if flow_name and flow_name != "Todos":
        conditions.append("flow_name = ?")
        params.append(flow_name)
    if status and status != "Todos":
        conditions.append("status = ?")
        params.append(status)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                id,
                created_at,
                lead_name,
                lead_phone,
                flow_name,
                status,
                result_title,
                benefit_category,
                estimated_monthly_value,
                estimated_total_value
            FROM atendimentos
            {where_sql}
            ORDER BY id DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    return rows


def get_attendance_details(attendance_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                id,
                created_at,
                lead_name,
                lead_phone,
                flow_id,
                flow_name,
                status,
                result_title,
                summary,
                next_step,
                notes,
                history_json,
                benefit_category,
                estimated_monthly_value,
                estimated_total_value
            FROM atendimentos
            WHERE id = ?
            """,
            (attendance_id,),
        ).fetchone()
    return row


def load_history(history_json: str) -> list[dict[str, Any]]:
    if not history_json:
        return []
    return json.loads(history_json)


def get_dashboard_summary() -> dict[str, Any]:
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) AS total FROM atendimentos").fetchone()["total"]
        by_status = conn.execute(
            """
            SELECT status, COUNT(*) AS total
            FROM atendimentos
            GROUP BY status
            ORDER BY total DESC
            """
        ).fetchall()
        by_flow = conn.execute(
            """
            SELECT flow_name, COUNT(*) AS total
            FROM atendimentos
            GROUP BY flow_name
            ORDER BY total DESC, flow_name ASC
            """
        ).fetchall()
        recent_days = conn.execute(
            """
            SELECT DATE(created_at) AS day, COUNT(*) AS total
            FROM atendimentos
            GROUP BY DATE(created_at)
            ORDER BY day DESC
            LIMIT 7
            """
        ).fetchall()
        conversion_by_flow = conn.execute(
            """
            SELECT flow_name, status, COUNT(*) AS total
            FROM atendimentos
            GROUP BY flow_name, status
            ORDER BY flow_name ASC, status ASC
            """
        ).fetchall()
        document_status = conn.execute(
            """
            SELECT status, COUNT(*) AS total
            FROM atendimento_documentos
            GROUP BY status
            ORDER BY total DESC, status ASC
            """
        ).fetchall()
        document_backlog = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM atendimento_documentos
            WHERE required = 1 AND status != 'validado'
            """
        ).fetchone()["total"]

    return {
        "total": total,
        "by_status": by_status,
        "by_flow": by_flow,
        "recent_days": list(reversed(recent_days)),
        "conversion_by_flow": conversion_by_flow,
        "document_status": document_status,
        "document_backlog": document_backlog,
    }


def seed_document_checklist(
    conn: sqlite3.Connection,
    *,
    attendance_id: int,
    flow_id: str,
) -> None:
    checklist = build_document_checklist(flow_id)
    for item in checklist:
        conn.execute(
            """
            INSERT OR IGNORE INTO atendimento_documentos (
                attendance_id,
                flow_id,
                document_code,
                document_name,
                category,
                required,
                critical_fields_json,
                uploaded_files_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attendance_id,
                flow_id,
                item["code"],
                item["name"],
                item["category"],
                1 if item["required"] else 0,
                json.dumps(item.get("critical_fields", []), ensure_ascii=True),
                json.dumps([], ensure_ascii=True),
            ),
        )


def backfill_document_checklists(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT id, flow_id
        FROM atendimentos
        WHERE status IN ('aprovado', 'revisao')
        """
    ).fetchall()
    for row in rows:
        seed_document_checklist(
            conn,
            attendance_id=int(row["id"]),
            flow_id=str(row["flow_id"]),
        )


def list_document_pipeline_attendances(
    *,
    status_filter: str = "Todos",
    limit: int = 50,
) -> list[sqlite3.Row]:
    filters = ["a.status IN ('aprovado', 'revisao')"]
    params: list[Any] = []
    if status_filter and status_filter != "Todos":
        filters.append("a.status = ?")
        params.append(status_filter)

    where_sql = f"WHERE {' AND '.join(filters)}"

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                a.id,
                a.created_at,
                a.lead_name,
                a.flow_name,
                CASE
                    WHEN LOWER(TRIM(a.status)) IN ('revisao', 'em revisao') THEN 'revisao'
                    WHEN LOWER(TRIM(a.status)) = 'desqualificado' THEN 'desqualificado'
                    ELSE 'aprovado'
                END AS triage_bucket,
                COUNT(d.id) AS document_total,
                SUM(CASE WHEN d.required = 1 THEN 1 ELSE 0 END) AS required_total,
                SUM(CASE WHEN d.required = 1 AND d.status = 'validado' THEN 1 ELSE 0 END) AS validated_total,
                SUM(CASE WHEN d.status = 'ilegivel' THEN 1 ELSE 0 END) AS illegible_total,
                SUM(CASE WHEN d.status = 'inconsistente' THEN 1 ELSE 0 END) AS inconsistent_total
            FROM atendimentos a
            LEFT JOIN atendimento_documentos d ON d.attendance_id = a.id
            {where_sql}
            GROUP BY a.id, a.created_at, a.lead_name, a.flow_name, a.status
            ORDER BY a.id DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    return rows


def list_attendance_documents(attendance_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                attendance_id,
                flow_id,
                document_code,
                document_name,
                category,
                required,
                status,
                notes,
                critical_fields_json,
                uploaded_files_json,
                raw_text,
                extracted_data_json,
                source_type,
                extraction_status,
                extraction_confidence,
                technical_notes,
                created_at,
                updated_at
            FROM atendimento_documentos
            WHERE attendance_id = ?
            ORDER BY required DESC, category ASC, document_name ASC
            """,
            (attendance_id,),
        ).fetchall()
    return rows


def update_attendance_document(
    *,
    document_id: int,
    status: str,
    notes: str,
    uploaded_files: list[str] | None = None,
    raw_text: str | None = None,
    extracted_data: dict[str, Any] | None = None,
    source_type: str | None = None,
    extraction_status: str | None = None,
    extraction_confidence: float | None = None,
    technical_notes: str | None = None,
) -> None:
    with get_connection() as conn:
        current = conn.execute(
            """
            SELECT
                uploaded_files_json,
                raw_text,
                extracted_data_json,
                source_type,
                extraction_status,
                extraction_confidence,
                technical_notes
            FROM atendimento_documentos
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
        uploaded_files_json = (
            json.dumps(uploaded_files, ensure_ascii=True)
            if uploaded_files is not None
            else (current["uploaded_files_json"] if current else json.dumps([], ensure_ascii=True))
        )
        resolved_raw_text = raw_text if raw_text is not None else (current["raw_text"] if current else None)
        resolved_extracted_data_json = (
            json.dumps(extracted_data, ensure_ascii=True)
            if extracted_data is not None
            else (current["extracted_data_json"] if current else json.dumps({}, ensure_ascii=True))
        )
        resolved_source_type = source_type if source_type is not None else (current["source_type"] if current else None)
        resolved_extraction_status = (
            extraction_status
            if extraction_status is not None
            else (current["extraction_status"] if current else None)
        )
        resolved_extraction_confidence = (
            extraction_confidence
            if extraction_confidence is not None
            else (current["extraction_confidence"] if current else None)
        )
        resolved_technical_notes = (
            technical_notes if technical_notes is not None else (current["technical_notes"] if current else None)
        )
        conn.execute(
            """
            UPDATE atendimento_documentos
            SET
                status = ?,
                notes = ?,
                uploaded_files_json = ?,
                raw_text = ?,
                extracted_data_json = ?,
                source_type = ?,
                extraction_status = ?,
                extraction_confidence = ?,
                technical_notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status,
                notes,
                uploaded_files_json,
                resolved_raw_text,
                resolved_extracted_data_json,
                resolved_source_type,
                resolved_extraction_status,
                resolved_extraction_confidence,
                resolved_technical_notes,
                document_id,
            ),
        )
        conn.commit()


def get_document_pipeline_summary() -> dict[str, Any]:
    with get_connection() as conn:
        status_rows = conn.execute(
            """
            SELECT status, COUNT(*) AS total
            FROM atendimento_documentos
            GROUP BY status
            ORDER BY total DESC, status ASC
            """
        ).fetchall()
        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS total_documents,
                SUM(CASE WHEN required = 1 THEN 1 ELSE 0 END) AS required_documents,
                SUM(CASE WHEN status = 'validado' THEN 1 ELSE 0 END) AS validated_documents,
                SUM(CASE WHEN status = 'pendente' THEN 1 ELSE 0 END) AS pending_documents,
                SUM(CASE WHEN extraction_status IN ('extraido', 'parcial') THEN 1 ELSE 0 END) AS processed_documents
            FROM atendimento_documentos
            """
        ).fetchone()

    return {
        "status_rows": status_rows,
        "total_documents": int(totals["total_documents"] or 0),
        "required_documents": int(totals["required_documents"] or 0),
        "validated_documents": int(totals["validated_documents"] or 0),
        "pending_documents": int(totals["pending_documents"] or 0),
        "processed_documents": int(totals["processed_documents"] or 0),
    }
