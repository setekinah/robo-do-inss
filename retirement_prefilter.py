"""Pré-filtro conservador para a jornada de aposentadoria.

Ele não reconhece direito a benefício: somente determina a próxima etapa segura
antes de iniciar a árvore de perguntas. Regras de transição, atividade especial,
PCD, rural e direito adquirido continuam exigindo CNIS e revisão técnica.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def evaluate_retirement_prefilter(payload: dict[str, Any]) -> dict[str, Any]:
    sex = payload.get("sex")
    age = payload.get("age")
    contribution_years = payload.get("contribution_years")
    has_cnis = payload.get("has_cnis")
    affiliation = payload.get("affiliation")
    cnis_evidence = payload.get("cnis_evidence") if isinstance(payload.get("cnis_evidence"), dict) else None

    if sex not in {"masculino", "feminino"}:
        raise ValueError("Informe o sexo para o pré-filtro.")
    if has_cnis not in {"sim", "nao"}:
        raise ValueError("Informe se o cliente possui CNIS.")
    if affiliation not in {"antes_ec103", "apos_ec103", "nao_sei"}:
        raise ValueError("Informe quando ocorreu a primeira filiação ao RGPS.")
    if not isinstance(age, (int, float)) or not 14 <= age <= 100:
        raise ValueError("Informe uma idade válida.")
    if not isinstance(contribution_years, (int, float)) or not 0 <= contribution_years <= 70:
        raise ValueError("Informe um tempo de contribuição válido.")

    evidence: dict[str, Any] = {"used": False, "source": "Dados informados manualmente", "alerts": 0}
    if cnis_evidence:
        document_code = str(cnis_evidence.get("document_code") or "").upper()
        metrics = cnis_evidence.get("metricas") if isinstance(cnis_evidence.get("metricas"), dict) else {}
        insured = cnis_evidence.get("segurado") if isinstance(cnis_evidence.get("segurado"), dict) else {}
        if document_code != "CNIS":
            raise ValueError("O arquivo enviado não foi identificado como CNIS. Revise ou envie o extrato previdenciário.")
        days = metrics.get("tempo_contribuicao_dias")
        if isinstance(days, (int, float)) and days > 0:
            contribution_years = round(float(days) / 365, 1)
            evidence["used"] = True
            evidence["source"] = "Tempo extraído do CNIS"
        birth_date = str(insured.get("data_nascimento") or "")
        try:
            born = datetime.strptime(birth_date, "%d/%m/%Y").date()
            today = date.today()
            age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
            evidence["used"] = True
            evidence["birth_date"] = birth_date
            evidence["source"] = "Dados extraídos do CNIS"
        except ValueError:
            pass
        matches = cnis_evidence.get("indicator_matches")
        if isinstance(matches, list):
            evidence["alerts"] = len(matches)
        evidence["file_name"] = str(cnis_evidence.get("file_name") or "CNIS enviado")
        evidence["extraction_confidence"] = cnis_evidence.get("extraction_confidence")

    # Regra programada de referência. Para homem filiado antes da EC 103/2019,
    # o mínimo de 15 anos pode se aplicar; transições nunca são concluídas aqui.
    required_age = 62 if sex == "feminino" else 65
    if sex == "feminino":
        required_contribution = 15
    elif affiliation == "antes_ec103":
        required_contribution = 15
    elif affiliation == "apos_ec103":
        required_contribution = 20
    else:
        required_contribution = None

    base = {
        "success": True,
        "prequalification": {
            "sex": sex,
            "age": age,
            "contribution_years": contribution_years,
            "has_cnis": has_cnis,
            "affiliation": affiliation,
        },
        "evidence": evidence,
        "disclaimer": (
            "Pré-filtro informativo. Não reconhece direito a benefício e não "
            "substitui a conferência do CNIS, das regras de transição e a revisão técnica."
        ),
    }

    if has_cnis == "nao" or affiliation == "nao_sei":
        reason = "O CNIS precisa confirmar a filiação, carência, vínculos e indicadores antes da simulação."
        if affiliation == "nao_sei" and has_cnis == "sim":
            reason = "O CNIS precisa confirmar a data da primeira filiação antes da simulação."
        return base | {
            "route": "documentos",
            "status": "revisao_documental",
            "title": "Não avance para a simulação sem validar o CNIS",
            "summary": reason,
            "next_action": "Abrir Documentos & OCR",
            "requirements": {"idade_minima_referencia": required_age, "tempo_minimo_referencia": required_contribution},
        }

    missing_age = max(0, required_age - age)
    missing_contribution = max(0, required_contribution - contribution_years)
    requirements = {
        "idade_minima_referencia": required_age,
        "tempo_minimo_referencia": required_contribution,
        "faltam_anos_idade": round(missing_age, 1),
        "faltam_anos_contribuicao": round(missing_contribution, 1),
    }

    if missing_age or missing_contribution:
        return base | {
            "route": "planejamento",
            "status": "planejamento_recomendado",
            "title": "Dados iniciais indicam planejamento, não elegibilidade automática",
            "summary": "Os dados informados não atingem a referência da aposentadoria programada. Regras de transição e períodos especiais só podem ser avaliados após revisão técnica do CNIS.",
            "next_action": "Salvar para acompanhamento previdenciário",
            "requirements": requirements,
        }

    return base | {
        "route": "triagem",
        "status": "triagem_tecnica",
        "title": "Pré-filtro mínimo atendido: seguir para triagem técnica",
        "summary": "Há dados mínimos para investigar regras de transição, períodos especiais e indicadores do CNIS. Isto não é concessão nem garantia de aposentadoria.",
        "next_action": "Iniciar triagem técnica de aposentadoria",
        "requirements": requirements,
    }
