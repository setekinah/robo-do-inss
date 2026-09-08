"""Contrato puro e compatível para os estados operacionais legados.

O banco ainda usa ``atendimentos`` e ``crm_stage`` durante a transição. Este
módulo não persiste nada: centraliza apenas o vocabulário aceito e a barreira
mínima de integridade que os serviços de aplicação devem aplicar.
"""

from __future__ import annotations


class DomainStateError(ValueError):
    """Um valor não pertence ao contrato de estado compatível."""


class InvalidStageTransitionError(DomainStateError):
    """A mudança solicitada não é permitida pela transição operacional atual."""


# Valores encontrados no Web App, no banco de compatibilidade e no Streamlit
# legado. A enumeração é deliberadamente fechada: novos estágios exigem uma
# decisão de domínio, não um texto arbitrário vindo do navegador.
CRM_STAGES = frozenset(
    {
        "novo_contato",
        "triagem",
        "qualificacao",
        "conflito",
        "proposta",
        "documentos",
        "caso_ativo",
        "concluido",
        "encerrado",
        "perdido",
        "relacionamento",
    }
)

# Resultados efetivamente emitidos pelos fluxos de triagem e pelo pré-filtro
# atual. Eles continuam sendo status legados de compatibilidade, não estados
# jurídicos canônicos.
LEGACY_ATTENDANCE_STATUSES = frozenset(
    {"aprovado", "revisao", "desqualificado", "pendente_documental"}
)

CONFLICT_STATUSES = frozenset({"pendente", "liberado", "conflito"})
PRIVACY_LEGAL_BASES = frozenset(
    {
        "consentimento",
        "procedimentos_preliminares",
        "execucao_contrato",
        "exercicio_regular_direitos",
        "obrigacao_legal",
        "protecao_vida",
        "tutela_saude",
    }
)
RELATIONSHIP_STATUSES = frozenset(
    {"nao_aplicavel", "aguardando_revisao", "reativado"}
)


# É uma barreira operacional compatível, não a state machine jurídica P2.
# Auto-transições permitem operações idempotentes. As transições de avanço
# usadas pelo Kanban atual continuam disponíveis; as terminais não são
# reabertas pelo endpoint genérico.
ALLOWED_STAGE_TRANSITIONS: dict[str, frozenset[str]] = {
    "novo_contato": frozenset({"novo_contato", "triagem", "relacionamento", "perdido"}),
    "triagem": frozenset({"triagem", "qualificacao", "relacionamento", "perdido"}),
    "qualificacao": frozenset({"qualificacao", "triagem", "conflito", "relacionamento", "perdido"}),
    "conflito": frozenset({"conflito", "qualificacao", "proposta", "relacionamento", "perdido"}),
    "proposta": frozenset({"proposta", "conflito", "documentos", "relacionamento", "perdido"}),
    "documentos": frozenset({"documentos", "proposta", "caso_ativo", "concluido", "relacionamento", "perdido"}),
    "caso_ativo": frozenset({"caso_ativo", "documentos", "concluido", "encerrado", "perdido"}),
    "concluido": frozenset({"concluido"}),
    "encerrado": frozenset({"encerrado"}),
    "perdido": frozenset({"perdido"}),
    "relacionamento": frozenset({"relacionamento", "triagem"}),
}


def _normalize(value: object) -> str:
    return str(value or "").strip().lower()


def validate_case_stage(stage: object) -> str:
    normalized = _normalize(stage)
    if normalized not in CRM_STAGES:
        raise DomainStateError("Etapa do CRM inválida.")
    return normalized


def normalize_legacy_status(status: object) -> str:
    normalized = _normalize(status)
    if normalized not in LEGACY_ATTENDANCE_STATUSES:
        raise DomainStateError("Status legado da triagem inválido.")
    return normalized


def validate_conflict_status(status: object) -> str:
    normalized = _normalize(status)
    if normalized not in CONFLICT_STATUSES:
        raise DomainStateError("Status de conflito inválido.")
    return normalized


def validate_privacy_legal_basis(legal_basis: object) -> str:
    normalized = _normalize(legal_basis)
    if normalized not in PRIVACY_LEGAL_BASES:
        raise DomainStateError("Base legal de privacidade inválida.")
    return normalized


def validate_relationship_status(status: object) -> str:
    normalized = _normalize(status)
    if normalized not in RELATIONSHIP_STATUSES:
        raise DomainStateError("Status de relacionamento inválido.")
    return normalized


def can_transition_stage(current_stage: object, destination_stage: object) -> bool:
    current = validate_case_stage(current_stage)
    destination = validate_case_stage(destination_stage)
    return destination in ALLOWED_STAGE_TRANSITIONS[current]


def require_stage_transition(current_stage: object, destination_stage: object) -> str:
    current = validate_case_stage(current_stage)
    destination = validate_case_stage(destination_stage)
    if destination not in ALLOWED_STAGE_TRANSITIONS[current]:
        raise InvalidStageTransitionError("Transição de etapa não permitida.")
    return destination


def derive_legacy_stage(status: object) -> str:
    """Deriva somente o estágio inicial de um novo atendimento legado.

    A entrada do navegador não escolhe o estágio. Resultados sem elegibilidade
    permanecem na base de relacionamento; os demais começam em triagem para
    preservar o fluxo atual até a implementação de P2.
    """

    normalized_status = normalize_legacy_status(status)
    return "relacionamento" if normalized_status == "desqualificado" else "triagem"


def derive_next_action_candidates(*, next_step: object, next_action: object) -> tuple[str, ...]:
    """Expõe candidatos atuais sem criar prazo ou alterar persistência."""

    return tuple(value for value in (str(next_action or "").strip(), str(next_step or "").strip()) if value)
