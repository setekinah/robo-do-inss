"""Camada de conhecimento versionavel para CNIS e procedimentos do Portal IN.

Nenhuma regra deste modulo concede beneficio ou protocola requerimentos. Ele
apenas identifica evidencias, vincula fontes oficiais e produz tarefas para
revisao juridica.
"""

from __future__ import annotations

import re
from typing import Any


OFFICIAL_SOURCES = [
    ("pt990_anexo_v", "Indicadores CNIS", "https://portalin.inss.gov.br/assets/anexos/pt990/AnexoV.pdf", "indicadores"),
    ("pt990_ajustes", "Ajustes EC 103", "https://portalin.inss.gov.br/assets/anexos/pt990/AnexoIII.pdf", "ajustes"),
    ("in128_rac", "RAC — atualização CNIS", "https://portalin.inss.gov.br/assets/anexos/in/AnexoI.docx", "requerimentos"),
    ("pt991_transicoes", "Regras de transição", "https://portalin.inss.gov.br/anexos", "simulacao"),
    ("in128_provas", "PPP, CTC e atividade especial", "https://portalin.inss.gov.br/anexos", "provas"),
    ("pt992_dependentes", "Pensão e auxílio-reclusão", "https://portalin.inss.gov.br/anexos", "dependentes"),
    ("pt1208_social", "Avaliação social / BPC", "https://portalin.inss.gov.br/anexos", "bpc"),
]


def normalize_code(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").upper())


def build_indicator_matches(raw_text: str, definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Localiza siglas do catálogo ativo; duplicidades ficam explicitamente ambíguas."""
    by_code: dict[str, list[dict[str, Any]]] = {}
    for definition in definitions:
        code = normalize_code(str(definition.get("code") or ""))
        if code:
            by_code.setdefault(code, []).append(definition)
    matches: list[dict[str, Any]] = []
    for code, candidates in by_code.items():
        expression = re.escape(code).replace(r"\-", r"\s*-\s*")
        if not re.search(rf"(?<![A-Z0-9]){expression}(?![A-Z0-9])", raw_text, re.IGNORECASE):
            continue
        first = candidates[0]
        ambiguous = len(candidates) > 1
        matches.append({
            "code": code,
            "type": first.get("indicator_type", "Indicador"),
            "group": first.get("indicator_group", "CNIS"),
            "description": (
                f"Sigla com {len(candidates)} descrições oficiais; associe à competência antes de concluir o impacto."
                if ambiguous else first.get("official_description", "")),
            "guidance": first.get("general_guidance", "Revisar documento e providência aplicável."),
            "status": "ambigua_requer_contexto" if ambiguous else "identificada_requer_revisao",
            "risk": risk_from_type(str(first.get("indicator_type") or "")),
        })
    return matches


def risk_from_type(indicator_type: str) -> str:
    normalized = indicator_type.casefold()
    if "pend" in normalized:
        return "vermelho"
    if "alert" in normalized:
        return "amarelo"
    return "verde"


def action_plan(matches: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Plano de ação conservador; a escolha de RAC depende da revisão humana."""
    plans: list[dict[str, str]] = []
    for match in matches:
        code = str(match["code"])
        text = str(match.get("description") or "")
        lowered = f"{code} {text}".casefold()
        if any(token in lowered for token in ("vinc", "admiss", "rescis", "remunera")):
            rac, documents = "RAC 2.2", "CTPS, holerites, FGTS e documentos contemporâneos"
        elif any(token in lowered for token in ("contrib", "recolh", "gps", "salário mínimo", "ec103")):
            rac, documents = "RAC 2.6 / ajuste EC 103", "GPS/DARF, comprovantes de pagamento e CNIS por competência"
        elif "filia" in lowered or "atividade" in lowered:
            rac, documents = "RAC 2.5", "provas de atividade, contratos e declarações pertinentes"
        else:
            rac, documents = "Revisão técnica", "CNIS completo e documento probatório correspondente"
        plans.append({"indicator": code, "risk": str(match["risk"]), "action": rac, "documents": documents, "status": "aguarda_revisao_juridica"})
    return plans
