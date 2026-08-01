"""Barramento interno e orquestração segura de eventos jurídicos."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from database import (
    add_crm_activity,
    add_integration_audit,
    complete_integration_event,
    create_crm_task,
    enqueue_integration_event,
    fail_integration_event,
    get_attendance_details,
    get_integration_event,
    list_pending_integration_events,
    mark_integration_event_processing,
    set_case_next_action_if_missing,
)


EVENT_RULES: dict[str, dict[str, Any]] = {
    "lead.qualified": {
        "label": "Lead qualificado",
        "title": "Realizar triagem inicial do lead qualificado",
        "priority": "media",
        "task_type": "triagem_inicial",
        "requires_review": False,
        "due_offset": 1,
    },
    "whatsapp.lead.qualified": {
        "label": "Lead qualificado pelo WhatsApp",
        "title": "Revisar triagem recebida pelo WhatsApp",
        "priority": "media",
        "task_type": "triagem_inicial",
        "requires_review": False,
        "due_offset": 1,
    },
    "process.movement.received": {
        "label": "Movimentação processual",
        "title": "Analisar nova movimentação processual",
        "priority": "alta",
        "task_type": "movimentacao_processual",
        "requires_review": True,
        "due_offset": 0,
    },
    "publication.received": {
        "label": "Publicação recebida",
        "title": "Revisar publicação e confirmar eventual prazo",
        "priority": "alta",
        "task_type": "publicacao",
        "requires_review": True,
        "due_offset": 0,
    },
    "inss.requirement.detected": {
        "label": "Exigência do INSS",
        "title": "Analisar exigência do INSS e confirmar providências",
        "priority": "critica",
        "task_type": "exigencia_inss",
        "requires_review": True,
        "due_offset": 0,
    },
}

PRIORITIES = {"baixa", "media", "alta", "critica"}


@dataclass(frozen=True)
class EventReceipt:
    event_id: int
    created: bool
    event_key: str


@dataclass(frozen=True)
class ProcessingResult:
    event_id: int
    status: str
    task_id: int | None = None
    error: str = ""


def build_event_key(
    *,
    source: str,
    event_type: str,
    attendance_id: int,
    external_reference: str,
    payload: dict[str, Any],
) -> str:
    reference = external_reference.strip()
    if reference:
        fingerprint = reference
    else:
        canonical_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()[:24]
    return f"{source.strip().lower()}:{event_type}:{attendance_id}:{fingerprint}"


def receive_event(
    *,
    event_type: str,
    source: str,
    attendance_id: int,
    payload: dict[str, Any] | None = None,
    external_reference: str = "",
    idempotency_key: str = "",
    priority: str | None = None,
    occurred_at: str | None = None,
) -> EventReceipt:
    if event_type not in EVENT_RULES:
        raise ValueError("Tipo de evento não suportado pelo orquestrador.")
    if not source.strip():
        raise ValueError("Informe a origem do evento.")
    if get_attendance_details(attendance_id) is None:
        raise ValueError("O atendimento vinculado ao evento não existe.")

    clean_payload = dict(payload or {})
    rule = EVENT_RULES[event_type]
    normalized_priority = (priority or str(rule["priority"])).strip().lower()
    if normalized_priority not in PRIORITIES:
        raise ValueError("Prioridade de evento inválida.")
    event_key = idempotency_key.strip() or build_event_key(
        source=source,
        event_type=event_type,
        attendance_id=attendance_id,
        external_reference=external_reference,
        payload=clean_payload,
    )
    event_id, created = enqueue_integration_event(
        event_key=event_key,
        event_type=event_type,
        source=source,
        attendance_id=attendance_id,
        external_reference=external_reference,
        payload=clean_payload,
        priority=normalized_priority,
        requires_review=bool(rule["requires_review"]),
        occurred_at=occurred_at,
    )
    return EventReceipt(event_id=event_id, created=created, event_key=event_key)


def process_event(event_id: int) -> ProcessingResult:
    event = get_integration_event(event_id)
    if event is None:
        return ProcessingResult(event_id=event_id, status="falhou", error="Evento não encontrado.")
    if str(event["status"]) == "concluido":
        return ProcessingResult(event_id=event_id, status="ignorado")
    if not mark_integration_event_processing(event_id):
        return ProcessingResult(event_id=event_id, status="ignorado")

    try:
        event_type = str(event["event_type"])
        rule = EVENT_RULES[event_type]
        payload = json.loads(str(event["payload_json"] or "{}"))
        attendance_id = int(event["attendance_id"])
        attendance = get_attendance_details(attendance_id)
        if attendance is None:
            raise ValueError("Atendimento vinculado não encontrado.")

        due_at = _resolve_operational_due_date(payload, int(rule["due_offset"]))
        assigned_to = str(payload.get("assigned_to") or attendance["assigned_to"] or "Equipe jurídica")
        title = str(payload.get("task_title") or rule["title"]).strip()
        description = _build_task_description(
            event_type=event_type,
            source=str(event["source"]),
            external_reference=str(event["external_reference"] or ""),
            payload=payload,
            requires_review=bool(rule["requires_review"]),
        )
        task_id = create_crm_task(
            attendance_id=attendance_id,
            title=title,
            description=description,
            due_at=due_at,
            assigned_to=assigned_to,
            priority=str(event["priority"]),
            source_event_id=event_id,
            requires_review=bool(rule["requires_review"]),
            task_type=str(rule["task_type"]),
        )
        set_case_next_action_if_missing(
            attendance_id=attendance_id,
            next_action=title,
            next_action_at=due_at,
        )
        add_crm_activity(
            attendance_id=attendance_id,
            activity_type="Automação",
            body=f"{rule['label']}: tarefa #{task_id} criada a partir de {event['source']}.",
        )
        add_integration_audit(
            event_id=event_id,
            action="tarefa_criada",
            details={
                "task_id": task_id,
                "attendance_id": attendance_id,
                "requires_review": bool(rule["requires_review"]),
                "operational_due_at": due_at,
            },
        )
        complete_integration_event(event_id)
        return ProcessingResult(event_id=event_id, status="concluido", task_id=task_id)
    except Exception as exc:  # noqa: BLE001 - a falha precisa ser persistida para reprocessamento
        error_message = str(exc) or exc.__class__.__name__
        fail_integration_event(event_id, error_message)
        add_integration_audit(
            event_id=event_id,
            action="processamento_falhou",
            details={"error": error_message},
        )
        return ProcessingResult(event_id=event_id, status="falhou", error=error_message)


def process_pending_events(limit: int = 20) -> list[ProcessingResult]:
    return [process_event(int(event["id"])) for event in list_pending_integration_events(limit)]


def receive_and_process_event(**event_data: Any) -> ProcessingResult:
    receipt = receive_event(**event_data)
    if not receipt.created:
        existing = get_integration_event(receipt.event_id)
        existing_status = str(existing["status"]) if existing is not None else "ignorado"
        return ProcessingResult(event_id=receipt.event_id, status=existing_status)
    return process_event(receipt.event_id)


def _resolve_operational_due_date(payload: dict[str, Any], offset: int) -> str:
    suggested = str(payload.get("suggested_due_at") or "").strip()
    if suggested:
        try:
            return date.fromisoformat(suggested[:10]).isoformat()
        except ValueError:
            pass
    return _add_business_days(date.today(), offset).isoformat()


def _add_business_days(start: date, days: int) -> date:
    current = start
    if days == 0:
        while current.weekday() >= 5:
            current += timedelta(days=1)
        return current
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _build_task_description(
    *,
    event_type: str,
    source: str,
    external_reference: str,
    payload: dict[str, Any],
    requires_review: bool,
) -> str:
    summary = str(payload.get("summary") or payload.get("content") or "Evento recebido sem resumo.").strip()
    parts = [f"Origem: {source}.", summary[:3000]]
    if external_reference:
        parts.append(f"Referência externa: {external_reference}.")
    if requires_review:
        parts.append(
            "A data indicada é uma prioridade operacional sugerida, não um prazo fatal. "
            "Confirme a publicação, o termo inicial, a contagem e o calendário aplicável antes de aprovar."
        )
    if event_type == "inss.requirement.detected":
        parts.append("Confirme o inteiro teor da exigência no canal oficial antes de responder.")
    return "\n\n".join(parts)
