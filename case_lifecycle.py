"""Serviços de aplicação mínimos para o ciclo operacional legado.

Mantém ``atendimentos`` como persistência temporária, mas impede que
controllers HTTP definam estados e fatos operacionais diretamente em SQL.
"""

from __future__ import annotations

from typing import Any

import database
from domain_state import (
    DomainStateError,
    derive_legacy_stage,
    InvalidStageTransitionError,
    require_stage_transition,
    validate_conflict_status,
    validate_privacy_legal_basis,
)


class AttendanceNotFoundError(LookupError):
    """O atendimento solicitado não existe."""


def _attendance_or_raise(conn: Any, attendance_id: int) -> Any:
    attendance = conn.execute(
        """
        SELECT id, status, crm_stage, relationship_status
        FROM atendimentos
        WHERE id = ?
        """,
        (attendance_id,),
    ).fetchone()
    if attendance is None:
        raise AttendanceNotFoundError("Atendimento não encontrado.")
    return attendance


def transition_case_stage(*, attendance_id: int, destination_stage: object) -> dict[str, object]:
    """Valida e persiste uma transição operacional compatível."""

    with database.get_connection() as conn:
        attendance = _attendance_or_raise(conn, attendance_id)
        current_stage = str(attendance["crm_stage"] or "triagem")
        destination = require_stage_transition(current_stage, destination_stage)
        conn.execute(
            "UPDATE atendimentos SET crm_stage = ?, crm_stage_updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (destination, attendance_id),
        )
        if destination != current_stage:
            conn.execute(
                "INSERT INTO crm_atividades (attendance_id, activity_type, body) VALUES (?, ?, ?)",
                (attendance_id, "estagio_alterado", f"Estágio do CRM alterado para: {destination.upper()}"),
            )
    return {"id": attendance_id, "stage": destination, "previous_stage": current_stage}


def reactivate_lead(*, attendance_id: int) -> dict[str, object]:
    """Reabre explicitamente um lead de relacionamento para nova triagem."""

    with database.get_connection() as conn:
        attendance = _attendance_or_raise(conn, attendance_id)
        is_relationship_lead = (
            str(attendance["crm_stage"] or "").strip().lower() == "relacionamento"
            and str(attendance["relationship_status"] or "").strip().lower() == "aguardando_revisao"
            and str(attendance["status"] or "").strip().lower() == "desqualificado"
        )
        if not is_relationship_lead:
            raise InvalidStageTransitionError(
                "Reativação disponível apenas para lead desqualificado em acompanhamento de relacionamento."
            )
        conn.execute(
            """
            UPDATE atendimentos
            SET status = 'revisao', crm_stage = ?, relationship_status = 'reativado',
                relationship_next_review_at = NULL,
                next_action = 'Refazer triagem guiada com dados atualizados',
                crm_stage_updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (derive_legacy_stage("revisao"), attendance_id),
        )
        conn.execute(
            "INSERT INTO crm_atividades (attendance_id, activity_type, body) VALUES (?, ?, ?)",
            (attendance_id, "lead_reativado", "Lead reativado para nova triagem."),
        )
    return {"id": attendance_id, "status": "revisao", "stage": "triagem"}


def record_conflict_check(
    *, attendance_id: int, status: object, notes: object, parties: object
) -> dict[str, object]:
    """Registra conflito somente quando a checagem foi explicitamente informada."""

    normalized_status = validate_conflict_status(status)
    clean_notes = str(notes or "").strip()
    clean_parties = str(parties or "").strip()
    if not clean_notes:
        raise DomainStateError("Informe as observações da checagem de conflito.")
    if normalized_status == "liberado" and not clean_parties:
        raise DomainStateError("Informe as partes verificadas antes de liberar o conflito.")
    with database.get_connection() as conn:
        _attendance_or_raise(conn, attendance_id)
        conn.execute(
            """
            UPDATE atendimentos
            SET conflict_status = ?, conflict_notes = ?, conflict_checked_parties = ?
            WHERE id = ?
            """,
            (normalized_status, clean_notes, clean_parties, attendance_id),
        )
        conn.execute(
            "INSERT INTO crm_atividades (attendance_id, activity_type, body) VALUES (?, ?, ?)",
            (attendance_id, "conflito_atualizado", "Checagem de conflito atualizada."),
        )
    return {"id": attendance_id, "conflict_status": normalized_status}


def record_privacy_acknowledgement(
    *, attendance_id: int, legal_basis: object, acknowledged: object
) -> dict[str, object]:
    """Registra base legal e ciência apenas quando ambas são explicitamente declaradas."""

    normalized_basis = validate_privacy_legal_basis(legal_basis)
    if acknowledged is not True:
        raise DomainStateError("Confirme explicitamente a ciência do aviso de privacidade.")
    with database.get_connection() as conn:
        _attendance_or_raise(conn, attendance_id)
        conn.execute(
            """
            UPDATE atendimentos
            SET privacy_notice_acknowledged = 1,
                privacy_legal_basis = ?,
                privacy_acknowledged_at = COALESCE(privacy_acknowledged_at, CURRENT_TIMESTAMP)
            WHERE id = ?
            """,
            (normalized_basis, attendance_id),
        )
    return {"id": attendance_id, "privacy_legal_basis": normalized_basis}


def record_activity(*, attendance_id: int, activity_type: object, body: object) -> None:
    clean_body = str(body or "").strip()
    if not clean_body:
        raise DomainStateError("Informe o conteúdo da atividade.")
    clean_type = str(activity_type or "nota").strip().lower() or "nota"
    with database.get_connection() as conn:
        _attendance_or_raise(conn, attendance_id)
        conn.execute(
            "INSERT INTO crm_atividades (attendance_id, activity_type, body) VALUES (?, ?, ?)",
            (attendance_id, clean_type, clean_body),
        )


def create_manual_task(*, attendance_id: int, title: object, due_at: object, priority: object) -> None:
    clean_title = str(title or "").strip()
    if not clean_title:
        raise DomainStateError("Informe o título da tarefa.")
    normalized_priority = str(priority or "media").strip().lower() or "media"
    if normalized_priority not in {"baixa", "media", "alta", "critica"}:
        raise DomainStateError("Prioridade de tarefa inválida.")
    with database.get_connection() as conn:
        _attendance_or_raise(conn, attendance_id)
        conn.execute(
            "INSERT INTO crm_tarefas (attendance_id, title, due_at, priority, status) VALUES (?, ?, ?, ?, 'aberta')",
            (attendance_id, clean_title, str(due_at or "").strip(), normalized_priority),
        )
