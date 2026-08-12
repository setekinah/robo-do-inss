"""Persistencia local em SQLite para atendimentos e respostas."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from document_rules import build_document_checklist
from runtime_paths import DATA_DIR


DB_PATH = DATA_DIR / "triagem.db"


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Open a transactional SQLite connection and always release the file handle."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


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
        ensure_column(conn, "crm_stage", "TEXT NOT NULL DEFAULT 'triagem'")
        ensure_column(conn, "conflict_status", "TEXT NOT NULL DEFAULT 'pendente'")
        ensure_column(conn, "assigned_to", "TEXT")
        ensure_column(conn, "next_action", "TEXT")
        ensure_column(conn, "next_action_at", "TEXT")
        ensure_column(conn, "lost_reason", "TEXT")
        ensure_column(conn, "lead_email", "TEXT")
        ensure_column(conn, "lead_source", "TEXT")
        ensure_column(conn, "conflict_checked_parties", "TEXT")
        ensure_column(conn, "conflict_notes", "TEXT")
        ensure_column(conn, "contracted_at", "TEXT")
        ensure_column(conn, "crm_stage_updated_at", "TEXT")
        ensure_column(conn, "privacy_notice_acknowledged", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "privacy_legal_basis", "TEXT")
        ensure_column(conn, "privacy_acknowledged_at", "TEXT")
        ensure_column(conn, "triage_profile_json", "TEXT NOT NULL DEFAULT '{}'")
        conn.execute(
            """
            UPDATE atendimentos
            SET crm_stage = CASE
                WHEN status = 'desqualificado' THEN 'perdido'
                WHEN status IN ('aprovado', 'revisao') THEN 'documentos'
                ELSE 'triagem'
            END
            WHERE crm_stage IS NULL OR crm_stage = ''
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_tarefas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attendance_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                due_at TEXT,
                assigned_to TEXT,
                status TEXT NOT NULL DEFAULT 'aberta',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                FOREIGN KEY(attendance_id) REFERENCES atendimentos(id)
            )
            """
        )
        ensure_task_column(conn, "description", "TEXT")
        ensure_task_column(conn, "priority", "TEXT NOT NULL DEFAULT 'media'")
        ensure_task_column(conn, "source_event_id", "INTEGER")
        ensure_task_column(conn, "requires_review", "INTEGER NOT NULL DEFAULT 0")
        ensure_task_column(conn, "review_status", "TEXT NOT NULL DEFAULT 'nao_aplicavel'")
        ensure_task_column(conn, "task_type", "TEXT NOT NULL DEFAULT 'manual'")
        ensure_task_column(conn, "updated_at", "TEXT")
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_crm_tarefas_source_event
            ON crm_tarefas(source_event_id)
            WHERE source_event_id IS NOT NULL
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_atividades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attendance_id INTEGER NOT NULL,
                activity_type TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(attendance_id) REFERENCES atendimentos(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS integration_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_key TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                attendance_id INTEGER,
                external_reference TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                priority TEXT NOT NULL DEFAULT 'media',
                status TEXT NOT NULL DEFAULT 'pendente',
                requires_review INTEGER NOT NULL DEFAULT 0,
                occurred_at TEXT,
                received_at TEXT DEFAULT CURRENT_TIMESTAMP,
                processing_started_at TEXT,
                processed_at TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                FOREIGN KEY(attendance_id) REFERENCES atendimentos(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS integration_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(event_id) REFERENCES integration_events(id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_integration_events_status ON integration_events(status, id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_integration_audit_event ON integration_audit_log(event_id, id)"
        )
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS calculos_previdenciarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attendance_id INTEGER NOT NULL,
                calculation_type TEXT NOT NULL,
                title TEXT NOT NULL,
                inputs_json TEXT NOT NULL,
                result_json TEXT,
                ruleset_version TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'rascunho',
                requires_human_review INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(attendance_id) REFERENCES atendimentos(id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_calculos_previdenciarios_attendance
            ON calculos_previdenciarios(attendance_id, id DESC)
            """
        )
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


def ensure_task_column(conn: sqlite3.Connection, column_name: str, column_type: str) -> None:
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(crm_tarefas)").fetchall()
    }
    if column_name not in columns:
        conn.execute(f"ALTER TABLE crm_tarefas ADD COLUMN {column_name} {column_type}")


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
    lead_email: str = "",
    lead_source: str = "",
    benefit_category: str | None = None,
    estimated_monthly_value: float | None = None,
    estimated_total_value: float | None = None,
    privacy_notice_acknowledged: bool = False,
    privacy_legal_basis: str = "",
    triage_profile: dict[str, Any] | None = None,
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
                estimated_total_value,
                crm_stage,
                conflict_status
                ,lead_email,
                lead_source,
                privacy_notice_acknowledged,
                privacy_legal_basis,
                triage_profile_json,
                privacy_acknowledged_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP ELSE NULL END)
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
                "triagem",
                "pendente",
                lead_email.strip(),
                lead_source.strip(),
                1 if privacy_notice_acknowledged else 0,
                privacy_legal_basis.strip(),
                json.dumps(triage_profile or {}, ensure_ascii=False, sort_keys=True),
                1 if privacy_notice_acknowledged else 0,
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
                ,crm_stage,
                conflict_status,
                assigned_to,
                next_action,
                next_action_at,
                lost_reason,
                lead_email,
                lead_source,
                conflict_checked_parties,
                conflict_notes,
                contracted_at,
                privacy_notice_acknowledged,
                privacy_legal_basis,
                privacy_acknowledged_at,
                triage_profile_json
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
                ,crm_stage,
                conflict_status,
                assigned_to,
                next_action,
                next_action_at,
                lost_reason,
                lead_email,
                lead_source,
                conflict_checked_parties,
                conflict_notes,
                contracted_at,
                privacy_notice_acknowledged,
                privacy_legal_basis,
                privacy_acknowledged_at,
                triage_profile_json
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


def update_crm_case(
    *,
    attendance_id: int,
    crm_stage: str,
    conflict_status: str,
    assigned_to: str,
    next_action: str,
    next_action_at: str | None,
    lost_reason: str = "",
    conflict_checked_parties: str = "",
    conflict_notes: str = "",
    privacy_notice_acknowledged: bool = False,
    privacy_legal_basis: str = "",
) -> None:
    with get_connection() as conn:
        current = conn.execute(
            "SELECT crm_stage FROM atendimentos WHERE id = ?", (attendance_id,)
        ).fetchone()
        stage_changed = current is not None and current["crm_stage"] != crm_stage
        if stage_changed and (not next_action.strip() or not next_action_at):
            raise ValueError("Defina a próxima ação e a data antes de mudar a etapa do caso.")
        if conflict_status == "liberado" and not conflict_checked_parties.strip():
            raise ValueError("Informe as partes verificadas antes de liberar o conflito.")
        if privacy_notice_acknowledged and not privacy_legal_basis.strip():
            raise ValueError("Informe a base legal antes de registrar a ciência de privacidade.")
        conn.execute(
            """
            UPDATE atendimentos
            SET
                crm_stage = ?,
                conflict_status = ?,
                assigned_to = ?,
                next_action = ?,
                next_action_at = ?,
                lost_reason = ?
                ,conflict_checked_parties = ?
                ,conflict_notes = ?
                ,privacy_notice_acknowledged = ?
                ,privacy_legal_basis = ?
                ,privacy_acknowledged_at = CASE
                    WHEN ? = 1 AND privacy_notice_acknowledged = 0 THEN CURRENT_TIMESTAMP
                    WHEN ? = 0 THEN NULL
                    ELSE privacy_acknowledged_at
                END
                ,crm_stage_updated_at = CASE WHEN crm_stage != ? THEN CURRENT_TIMESTAMP ELSE crm_stage_updated_at END
                ,contracted_at = CASE WHEN ? = 'caso_ativo' AND contracted_at IS NULL THEN CURRENT_TIMESTAMP ELSE contracted_at END
            WHERE id = ?
            """,
            (
                crm_stage,
                conflict_status,
                assigned_to.strip(),
                next_action.strip(),
                next_action_at,
                lost_reason.strip(),
                conflict_checked_parties.strip(),
                conflict_notes.strip(),
                1 if privacy_notice_acknowledged else 0,
                privacy_legal_basis.strip(),
                1 if privacy_notice_acknowledged else 0,
                1 if privacy_notice_acknowledged else 0,
                crm_stage,
                crm_stage,
                attendance_id,
            ),
        )
        conn.commit()


def add_crm_activity(*, attendance_id: int, activity_type: str, body: str) -> None:
    clean_body = body.strip()
    if not clean_body:
        return
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO crm_atividades (attendance_id, activity_type, body)
            VALUES (?, ?, ?)
            """,
            (attendance_id, activity_type, clean_body),
        )
        conn.commit()


def set_case_next_action_if_missing(
    *, attendance_id: int, next_action: str, next_action_at: str | None
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE atendimentos
            SET next_action = ?, next_action_at = ?
            WHERE id = ?
              AND (next_action IS NULL OR TRIM(next_action) = '' OR next_action_at IS NULL)
            """,
            (next_action.strip(), next_action_at, attendance_id),
        )
        conn.commit()


def list_crm_activities(attendance_id: int, limit: int = 30) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, attendance_id, activity_type, body, created_at
            FROM crm_atividades
            WHERE attendance_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (attendance_id, limit),
        ).fetchall()


def create_crm_task(
    *,
    attendance_id: int,
    title: str,
    due_at: str | None,
    assigned_to: str,
    description: str = "",
    priority: str = "media",
    source_event_id: int | None = None,
    requires_review: bool = False,
    task_type: str = "manual",
) -> int:
    clean_title = title.strip()
    if not clean_title:
        raise ValueError("A tarefa precisa de um título.")
    if not description.strip():
        raise ValueError("A tarefa precisa de uma descrição.")
    if not due_at:
        raise ValueError("A tarefa precisa de um prazo operacional.")
    if not assigned_to.strip():
        raise ValueError("A tarefa precisa de um responsável.")
    normalized_priority = priority.strip().lower()
    if normalized_priority not in {"baixa", "media", "alta", "critica"}:
        raise ValueError("Prioridade de tarefa inválida.")
    with get_connection() as conn:
        if source_event_id is not None:
            existing = conn.execute(
                "SELECT id FROM crm_tarefas WHERE source_event_id = ?",
                (source_event_id,),
            ).fetchone()
            if existing is not None:
                return int(existing["id"])
        cursor = conn.execute(
            """
            INSERT INTO crm_tarefas (
                attendance_id,
                title,
                due_at,
                assigned_to,
                description,
                priority,
                source_event_id,
                requires_review,
                review_status,
                task_type,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                attendance_id,
                clean_title,
                due_at,
                assigned_to.strip(),
                description.strip(),
                normalized_priority,
                source_event_id,
                1 if requires_review else 0,
                "pendente" if requires_review else "nao_aplicavel",
                task_type.strip() or "manual",
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_crm_tasks(attendance_id: int, include_done: bool = False) -> list[sqlite3.Row]:
    where = "attendance_id = ?" if include_done else "attendance_id = ? AND status = 'aberta'"
    with get_connection() as conn:
        return conn.execute(
            f"""
            SELECT
                id,
                attendance_id,
                title,
                due_at,
                assigned_to,
                status,
                created_at,
                completed_at,
                description,
                priority,
                source_event_id,
                requires_review,
                review_status,
                task_type,
                updated_at
            FROM crm_tarefas
            WHERE {where}
            ORDER BY CASE WHEN due_at IS NULL THEN 1 ELSE 0 END, due_at ASC, id DESC
            """,
            (attendance_id,),
        ).fetchall()


def complete_crm_task(task_id: int) -> None:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE crm_tarefas
            SET status = 'concluida', completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND (requires_review = 0 OR review_status = 'aprovada')
            """,
            (task_id,),
        )
        if cursor.rowcount == 0:
            raise ValueError("A tarefa precisa ser revisada antes da conclusão.")
        conn.commit()


def review_crm_task(*, task_id: int, approved: bool, due_at: str | None = None) -> None:
    with get_connection() as conn:
        task = conn.execute(
            "SELECT id, requires_review, review_status, source_event_id FROM crm_tarefas WHERE id = ?",
            (task_id,),
        ).fetchone()
        if task is None:
            raise ValueError("Tarefa não encontrada.")
        if not int(task["requires_review"]):
            raise ValueError("Esta tarefa não exige revisão humana.")
        if str(task["review_status"]) != "pendente":
            raise ValueError("Esta tarefa já foi revisada.")
        conn.execute(
            """
            UPDATE crm_tarefas
            SET review_status = ?,
                status = CASE WHEN ? = 1 THEN status ELSE 'cancelada' END,
                due_at = CASE WHEN ? = 1 THEN COALESCE(?, due_at) ELSE due_at END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                "aprovada" if approved else "rejeitada",
                1 if approved else 0,
                1 if approved else 0,
                due_at,
                task_id,
            ),
        )
        if task["source_event_id"] is not None:
            conn.execute(
                """
                INSERT INTO integration_audit_log (event_id, action, details_json)
                VALUES (?, ?, ?)
                """,
                (
                    int(task["source_event_id"]),
                    "tarefa_aprovada" if approved else "tarefa_rejeitada",
                    json.dumps(
                        {"task_id": task_id, "due_at": due_at},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                ),
            )
        conn.commit()


def get_crm_summary() -> dict[str, int]:
    with get_connection() as conn:
        open_tasks = conn.execute(
            "SELECT COUNT(*) AS total FROM crm_tarefas WHERE status = 'aberta'"
        ).fetchone()["total"]
        overdue_tasks = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM crm_tarefas
            WHERE status = 'aberta' AND due_at IS NOT NULL AND DATE(due_at) < DATE('now')
            """
        ).fetchone()["total"]
        pending_conflicts = conn.execute(
            "SELECT COUNT(*) AS total FROM atendimentos WHERE conflict_status = 'pendente'"
        ).fetchone()["total"]
        due_today = conn.execute(
            "SELECT COUNT(*) AS total FROM crm_tarefas WHERE status = 'aberta' AND DATE(due_at) = DATE('now')"
        ).fetchone()["total"]
        stalled_leads = conn.execute(
            """SELECT COUNT(*) AS total FROM atendimentos
               WHERE crm_stage NOT IN ('encerrado', 'perdido')
                 AND (next_action IS NULL OR TRIM(next_action) = '' OR next_action_at IS NULL)"""
        ).fetchone()["total"]
    return {
        "open_tasks": int(open_tasks or 0),
        "overdue_tasks": int(overdue_tasks or 0),
        "pending_conflicts": int(pending_conflicts or 0),
        "due_today": int(due_today or 0),
        "stalled_leads": int(stalled_leads or 0),
    }


def get_crm_performance() -> dict[str, Any]:
    with get_connection() as conn:
        by_source = conn.execute(
            """
            SELECT COALESCE(NULLIF(lead_source, ''), 'Não informado') AS source,
                   COUNT(*) AS total,
                   SUM(CASE WHEN contracted_at IS NOT NULL THEN 1 ELSE 0 END) AS contracted
            FROM atendimentos
            GROUP BY COALESCE(NULLIF(lead_source, ''), 'Não informado')
            ORDER BY total DESC, source ASC
            """
        ).fetchall()
        average_days = conn.execute(
            """
            SELECT AVG(JULIANDAY(contracted_at) - JULIANDAY(created_at)) AS days
            FROM atendimentos WHERE contracted_at IS NOT NULL
            """
        ).fetchone()["days"]
    return {"by_source": by_source, "average_days_to_contract": float(average_days or 0)}


def enqueue_integration_event(
    *,
    event_key: str,
    event_type: str,
    source: str,
    attendance_id: int | None,
    external_reference: str,
    payload: dict[str, Any],
    priority: str,
    requires_review: bool,
    occurred_at: str | None = None,
) -> tuple[int, bool]:
    clean_key = event_key.strip()
    if not clean_key:
        raise ValueError("O evento precisa de uma chave de idempotência.")
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO integration_events (
                event_key,
                event_type,
                source,
                attendance_id,
                external_reference,
                payload_json,
                priority,
                requires_review,
                occurred_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clean_key,
                event_type.strip(),
                source.strip(),
                attendance_id,
                external_reference.strip(),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                priority.strip().lower(),
                1 if requires_review else 0,
                occurred_at,
            ),
        )
        if cursor.rowcount == 0:
            existing = conn.execute(
                "SELECT id FROM integration_events WHERE event_key = ?",
                (clean_key,),
            ).fetchone()
            if existing is None:
                raise RuntimeError("Não foi possível recuperar o evento idempotente.")
            return int(existing["id"]), False
        event_id = int(cursor.lastrowid)
        conn.execute(
            """
            INSERT INTO integration_audit_log (event_id, action, details_json)
            VALUES (?, 'evento_recebido', ?)
            """,
            (
                event_id,
                json.dumps(
                    {"event_type": event_type, "source": source},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            ),
        )
        conn.commit()
        return event_id, True


def get_integration_event(event_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM integration_events WHERE id = ?
            """,
            (event_id,),
        ).fetchone()


def list_pending_integration_events(limit: int = 20) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM integration_events
            WHERE status = 'pendente'
            ORDER BY
                CASE priority
                    WHEN 'critica' THEN 0
                    WHEN 'alta' THEN 1
                    WHEN 'media' THEN 2
                    ELSE 3
                END,
                id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def list_integration_events(limit: int = 30) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                e.*,
                a.lead_name,
                t.id AS task_id,
                t.title AS task_title,
                t.review_status AS task_review_status
            FROM integration_events e
            LEFT JOIN atendimentos a ON a.id = e.attendance_id
            LEFT JOIN crm_tarefas t ON t.source_event_id = e.id
            ORDER BY e.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def mark_integration_event_processing(event_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE integration_events
            SET status = 'processando',
                processing_started_at = CURRENT_TIMESTAMP,
                attempts = attempts + 1,
                last_error = NULL
            WHERE id = ? AND status = 'pendente'
            """,
            (event_id,),
        )
        conn.commit()
        return cursor.rowcount == 1


def complete_integration_event(event_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE integration_events
            SET status = 'concluido', processed_at = CURRENT_TIMESTAMP, last_error = NULL
            WHERE id = ?
            """,
            (event_id,),
        )
        conn.commit()


def fail_integration_event(event_id: int, error_message: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE integration_events
            SET status = 'falhou', processed_at = CURRENT_TIMESTAMP, last_error = ?
            WHERE id = ?
            """,
            (error_message.strip()[:1000], event_id),
        )
        conn.commit()


def retry_integration_event(event_id: int) -> None:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE integration_events
            SET status = 'pendente', last_error = NULL, processing_started_at = NULL, processed_at = NULL
            WHERE id = ? AND status = 'falhou'
            """,
            (event_id,),
        )
        if cursor.rowcount == 0:
            raise ValueError("Somente eventos com falha podem ser reenfileirados.")
        conn.commit()


def add_integration_audit(*, event_id: int, action: str, details: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO integration_audit_log (event_id, action, details_json)
            VALUES (?, ?, ?)
            """,
            (
                event_id,
                action.strip(),
                json.dumps(details, ensure_ascii=False, sort_keys=True),
            ),
        )
        conn.commit()


def list_integration_audit(event_id: int, limit: int = 50) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, event_id, action, details_json, created_at
            FROM integration_audit_log
            WHERE event_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (event_id, limit),
        ).fetchall()


def get_integration_summary() -> dict[str, int]:
    with get_connection() as conn:
        status_rows = conn.execute(
            """
            SELECT status, COUNT(*) AS total
            FROM integration_events
            GROUP BY status
            """
        ).fetchall()
        status_totals = {str(row["status"]): int(row["total"] or 0) for row in status_rows}
        pending_review = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM crm_tarefas
            WHERE status = 'aberta' AND requires_review = 1 AND review_status = 'pendente'
            """
        ).fetchone()["total"]
        automated_tasks = conn.execute(
            "SELECT COUNT(*) AS total FROM crm_tarefas WHERE source_event_id IS NOT NULL"
        ).fetchone()["total"]
    return {
        "pending": status_totals.get("pendente", 0),
        "processing": status_totals.get("processando", 0),
        "completed": status_totals.get("concluido", 0),
        "failed": status_totals.get("falhou", 0),
        "pending_review": int(pending_review or 0),
        "automated_tasks": int(automated_tasks or 0),
    }
