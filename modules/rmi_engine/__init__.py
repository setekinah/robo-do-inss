"""Catálogo conservador de cenários para futura simulação previdenciária.

Esta primeira versão não calcula RMI, tempo, pontos ou direito adquirido. Ela
apenas informa ao advogado quais dados e provas precisam estar completos antes
que uma regra possa entrar em uma simulação jurídica validada.
"""

from __future__ import annotations

from typing import Any, Mapping


SCENARIOS = (
    ("programada_idade", "Aposentadoria programada por idade", ("idade", "cnis", "identidade")),
    ("transicao_pontos", "Regra de transição por pontos", ("filiacao", "tempo", "cnis", "ctps")),
    ("transicao_idade_progressiva", "Regra de transição por idade progressiva", ("filiacao", "idade", "tempo", "cnis", "ctps")),
    ("transicao_pedagio_50", "Regra de transição com pedágio de 50%", ("filiacao", "tempo", "cnis", "ctps")),
    ("transicao_pedagio_100", "Regra de transição com pedágio de 100%", ("filiacao", "idade", "tempo", "cnis", "ctps")),
)


def _known(profile: Mapping[str, Any], key: str) -> bool:
    field = {"idade": "age", "tempo": "contribution_years", "filiacao": "affiliation"}.get(key)
    return bool(field and profile.get(field) not in (None, "", "nao_sei"))


def build_scenario_catalog(*, dossier: Mapping[str, Any], triage_profile: Mapping[str, Any] | None = None) -> dict[str, Any]:
    profile = ((triage_profile or {}).get("prequalification") or {})
    if not isinstance(profile, Mapping):
        profile = {}
    hypotheses = {item.get("codigo"): item for item in dossier.get("hipoteses") or [] if isinstance(item, Mapping)}
    items = []
    for code, title, requirements in SCENARIOS:
        hypothesis = hypotheses.get("programada_idade" if code == "programada_idade" else "transicoes_tempo") or {}
        missing = []
        for requirement in requirements:
            if requirement in {"idade", "tempo", "filiacao"}:
                if not _known(profile, requirement):
                    missing.append(requirement)
            elif requirement in {"cnis", "ctps", "identidade"}:
                matched = next((item for item in hypothesis.get("requisitos") or [] if item.get("chave") == requirement), {})
                if matched.get("status") != "evidenciado":
                    missing.append(requirement)
        items.append({
            "codigo": code,
            "titulo": title,
            "status": "base_incompleta" if missing else "pronto_para_revisao_tecnica",
            "dados_ou_provas_pendentes": missing,
            "orientacao": "Não calcula RMI nem reconhece direito. Requer validação da regra vigente, memória de cálculo e aprovação profissional.",
        })
    return {
        "versao": "0.1",
        "status": "revisao_humana_obrigatoria",
        "conclusao": "Catálogo de cenários para preparação da simulação; não é um cálculo de melhor benefício.",
        "cenarios": items,
    }
