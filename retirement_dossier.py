"""Dossiê probatório conservador para hipóteses de aposentadoria.

O módulo organiza prova documental e lacunas de cada hipótese. Não calcula
direito adquirido, não homologa carência e não emite conclusão de elegibilidade.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping

from modules.cnis_analyzer import analyze_cnis_documents
from modules.rmi_engine import build_scenario_catalog


AUDIT_TYPE_RETIREMENT_DOSSIER = "DOSSIE_PROBATORIO_APOSENTADORIA"
HUMAN_DECISIONS = {"em_revisao", "prosseguir_analise", "solicitar_provas", "arquivar_hipotese"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _code(document: Mapping[str, Any]) -> str:
    return _text(document.get("document_code")).upper()


def _uploaded(document: Mapping[str, Any]) -> bool:
    try:
        return bool(json.loads(_text(document.get("uploaded_files_json")) or "[]"))
    except json.JSONDecodeError:
        return False


def _page_and_excerpt(raw_text: str) -> tuple[int | None, str]:
    if not raw_text:
        return None, "Documento anexado; ainda sem texto extraído para rastreabilidade."
    marker = re.search(r"\[P[aá]gina\s+(\d+)", raw_text, flags=re.IGNORECASE)
    page = int(marker.group(1)) if marker else None
    excerpt = re.sub(r"\s+", " ", raw_text).strip()[:240]
    return page, excerpt or "Texto extraído sem trecho útil para exibição."


def _evidence(document: Mapping[str, Any]) -> dict[str, Any]:
    page, excerpt = _page_and_excerpt(_text(document.get("raw_text")))
    report = {
        "documento_id": document.get("id"),
        "codigo": _code(document),
        "nome": _text(document.get("document_name")),
        "status": _text(document.get("status")) or "pendente",
        "status_extracao": _text(document.get("extraction_status")) or "nao_processado",
        "confianca_extracao": document.get("extraction_confidence"),
        "pagina": page,
        "trecho": excerpt,
    }


def _requirement(
    *,
    key: str,
    label: str,
    accepted_codes: set[str],
    documents: list[Mapping[str, Any]],
    note: str,
    critical: bool = True,
) -> dict[str, Any]:
    matched = [doc for doc in documents if _code(doc) in accepted_codes and _uploaded(doc)]
    usable = [doc for doc in matched if _text(doc.get("status")) not in {"ilegivel", "rejeitado"}]
    return {
        "chave": key,
        "requisito": label,
        "critico": critical,
        "status": "evidenciado" if usable else ("inutilizavel" if matched else "pendente"),
        "orientacao": note,
        "evidencias": [_evidence(doc) for doc in usable],
    }


def _profile_requirement(key: str, label: str, value: Any, note: str) -> dict[str, Any]:
    known = value not in (None, "", "nao_sei")
    return {
        "chave": key,
        "requisito": label,
        "critico": True,
        "status": "informado" if known else "pendente",
        "orientacao": note,
        "evidencias": ([{"documento_id": None, "codigo": "TRIAGEM", "nome": "Dado informado na triagem", "valor": value}] if known else []),
    }


def _hypothesis(code: str, title: str, requirements: list[dict[str, Any]], scope: str) -> dict[str, Any]:
    pending = [item for item in requirements if item["status"] != "evidenciado" and item["status"] != "informado"]
    critical_pending = [item for item in pending if item["critico"]]
    status = "base_incompleta" if critical_pending else "revisao_humana_obrigatoria"
    return {
        "codigo": code,
        "titulo": title,
        "escopo": scope,
        "status": status,
        "requisitos": requirements,
        "pendencias": [item["requisito"] for item in pending],
        "conclusao": (
            "A base documental ainda não permite análise técnica desta hipótese."
            if critical_pending
            else "A documentação mínima foi localizada; a análise e decisão continuam reservadas ao advogado."
        ),
    }


def build_retirement_dossier(
    *,
    documents: Iterable[Mapping[str, Any]],
    triage_profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a reviewable evidence map for retirement, never an entitlement decision."""
    docs = list(documents)
    cnis_analysis = analyze_cnis_documents(docs)
    profile = (triage_profile or {}).get("prequalification", {})
    if not isinstance(profile, Mapping):
        profile = {}

    identity = _requirement(
        key="identidade", label="Identidade e data de nascimento comprovadas",
        accepted_codes={"IDENTIDADE", "RG", "CNH", "CPF"}, documents=docs,
        note="Conferir o original e a coerência dos dados civis com o CNIS.",
    )
    cnis = _requirement(
        key="cnis", label="CNIS com vínculos, contribuições e indicadores",
        accepted_codes={"CNIS"}, documents=docs,
        note="A leitura é evidência preliminar; conferir competências, indicadores e carência no extrato original.",
    )
    ctps = _requirement(
        key="ctps", label="CTPS para conferência dos vínculos",
        accepted_codes={"CTPS"}, documents=docs,
        note="Comparar admissões, desligamentos e empregadores com o CNIS.",
    )
    affiliation = _profile_requirement(
        "filiacao", "Primeira filiação ao RGPS identificada", profile.get("affiliation"),
        "Confirmar a primeira filiação no CNIS antes de aplicar regra de transição.",
    )
    contribution = _profile_requirement(
        "tempo_informado", "Tempo de contribuição informado", profile.get("contribution_years"),
        "O tempo informado não substitui a contagem técnica, carência ou períodos concomitantes.",
    )
    age = _profile_requirement(
        "idade_informada", "Idade informada", profile.get("age"),
        "Confirmar a data de nascimento no documento civil e no CNIS.",
    )
    special = _requirement(
        key="atividade_especial", label="PPP, LTCAT ou prova de atividade especial",
        accepted_codes={"PPS_LTCATS", "PPP", "LTCAT"}, documents=docs,
        note="Avaliar agentes nocivos, períodos, responsável técnico e documentação complementar.",
    )
    public_or_rural = _requirement(
        key="tempo_complementar", label="CTC ou prova de tempo rural/público",
        accepted_codes={"CERTIDOES_TEMPO", "CTC", "PROVAS_ATIVIDADE_RURAL"}, documents=docs,
        note="Identificar a natureza do período e a necessidade de averbação ou justificação administrativa.",
    )
    pcd = _requirement(
        key="pcd", label="Laudos e provas da condição de pessoa com deficiência",
        accepted_codes={"LAUDOS_PCD", "LAUDO_MEDICO", "ATESTADO_MEDICO"}, documents=docs,
        note="A classificação, grau e marco temporal dependem de avaliação técnica e perícia competente.",
    )

    hypotheses = [
        _hypothesis("programada_idade", "Aposentadoria programada por idade", [identity, age, cnis, ctps, affiliation], "Hipótese básica; não abrange transições ou direito adquirido."),
        _hypothesis("transicoes_tempo", "Regras de transição / tempo de contribuição", [identity, cnis, ctps, affiliation, contribution], "Exige memória de cálculo e validação da regra aplicável."),
        _hypothesis("especial", "Aposentadoria especial ou conversão de tempo", [identity, cnis, ctps, special], "A prova de exposição e os períodos exigem revisão especializada."),
        _hypothesis("rural_hibrida_publica", "Tempo rural, híbrido ou público", [identity, cnis, public_or_rural], "A prova e a forma de aproveitamento do tempo dependem da origem de cada período."),
        _hypothesis("pessoa_com_deficiencia", "Aposentadoria da pessoa com deficiência", [identity, cnis, ctps, pcd], "Não infere deficiência ou grau a partir do OCR."),
    ]
    pending = sum(len(item["pendencias"]) for item in hypotheses)
    evidence_count = sum(
        len(requirement["evidencias"])
        for hypothesis in hypotheses for requirement in hypothesis["requisitos"]
        if requirement["status"] in {"evidenciado", "informado"}
    )
    return {
        "tipo": AUDIT_TYPE_RETIREMENT_DOSSIER,
        "status": "revisao_humana_obrigatoria",
        "resumo": {"hipoteses": len(hypotheses), "evidencias": evidence_count, "pendencias": pending},
        "conclusao": "O dossiê organiza provas e lacunas. Não reconhece direito, não calcula RMI e não substitui decisão profissional.",
        "analise_cnis": cnis_analysis,
        "hipoteses": hypotheses,
        "decisao_humana": {"status": "em_revisao", "responsavel": "", "nota": ""},
    }
    report["cenarios_preparatorios"] = build_scenario_catalog(dossier=report, triage_profile=triage_profile)
    return report


def apply_human_decision(report: dict[str, Any], *, status: str, responsible: str, note: str) -> dict[str, Any]:
    if status not in HUMAN_DECISIONS:
        raise ValueError("Decisão de revisão inválida.")
    if not _text(responsible):
        raise ValueError("Informe o responsável pela decisão humana.")
    if not _text(note):
        raise ValueError("Registre uma nota para a decisão humana.")
    report["decisao_humana"] = {"status": status, "responsavel": _text(responsible), "nota": _text(note)}
    return report
