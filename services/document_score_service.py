"""Cálculo determinístico da maturidade documental de um caso."""

from __future__ import annotations

from typing import Any


def build_document_case_score(documents: list[Any]) -> dict[str, Any]:
    if not documents:
        return {"score": 0, "label": "Sem dossie", "critical_gaps": [], "processed": 0}

    status_weight = {"validado": 1.0, "em_validacao": 0.82, "recebido": 0.62, "pendente": 0.18, "ilegivel": 0.05, "inconsistente": 0.12, "dispensado": 1.0}
    extraction_weight = {"extraido": 1.0, "parcial": 0.72, "nao_processado": 0.0, "sem_texto": 0.18, "dependencia_ausente": 0.0, "erro": 0.0, None: 0.0}
    required_docs = [row for row in documents if int(row["required"]) == 1]
    if not required_docs:
        return {"score": 0, "label": "Sem obrigatorios", "critical_gaps": [], "processed": 0}

    total_points = 0.0
    critical_gaps: list[str] = []
    processed = 0
    for row in required_docs:
        status = row["status"]
        extraction = row["extraction_status"]
        processed += int(extraction in {"extraido", "parcial"})
        total_points += status_weight.get(status, 0.0) * 70
        total_points += extraction_weight.get(extraction, 0.0) * 30
        if status in {"pendente", "ilegivel", "inconsistente"}:
            critical_gaps.append(str(row["document_name"]))

    score = round(total_points / len(required_docs))
    label = "Pronto para analise juridica" if score >= 80 else "Dossie parcialmente consolidado" if score >= 55 else "Dossie critico"
    return {"score": int(score), "label": label, "critical_gaps": critical_gaps[:4], "processed": processed}
