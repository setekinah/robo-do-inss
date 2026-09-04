"""Geração local de rascunhos PDF para conferência do advogado.

Os arquivos são produzidos somente em memória e não são protocolo, petição,
assinatura ou formulário oficial preenchido. A etapa de mapeamento de modelos
oficiais será acrescentada apenas após a validação jurídica de cada modelo.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any, Iterable, Mapping

import pymupdf
from pypdf import PdfReader


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _lines(dossier: Mapping[str, Any]) -> Iterable[str]:
    cnis = dossier.get("analise_cnis") or {}
    yield "RASCUNHO PARA CONFERÊNCIA PROFISSIONAL - NÃO PROTOCOLAR"
    yield ""
    yield "Este documento organiza informações já presentes no dossiê. A revisão, a estratégia e a assinatura são responsabilidade do advogado."
    yield ""
    yield "LEITURA PRELIMINAR DO CNIS"
    yield _clean(cnis.get("conclusion")) or "CNIS ainda não analisado."
    for finding in cnis.get("findings") or []:
        evidence = (finding.get("evidence") or [{}])[0]
        page = f" (página {evidence['page']})" if evidence.get("page") else ""
        yield f"- {finding.get('code', 'Sinal')}: {_clean(finding.get('message'))}{page}"
        yield f"  Providência: {_clean(finding.get('guidance'))}"
    yield ""
    yield "HIPÓTESES E PENDÊNCIAS"
    for hypothesis in dossier.get("hipoteses") or []:
        yield f"- {_clean(hypothesis.get('titulo'))}: {_clean(hypothesis.get('status'))}"
        for pending in hypothesis.get("pendencias") or []:
            yield f"  - Pendente: {_clean(pending)}"
    yield ""
    decision = dossier.get("decisao_humana") or {}
    yield "REGISTRO DE REVISÃO HUMANA"
    yield f"Status: {_clean(decision.get('status')) or 'em_revisao'}"
    yield f"Responsável: {_clean(decision.get('responsavel')) or 'não informado'}"
    yield f"Nota: {_clean(decision.get('nota')) or 'não informada'}"
    yield ""
    yield "Limites: não calcula tempo de contribuição, carência, RMI ou elegibilidade; não substitui o CNIS original nem a análise técnica."


def build_review_draft_pdf(*, attendance: Mapping[str, Any], dossier: Mapping[str, Any]) -> bytes:
    """Create a printable, memory-only PDF and validate its structure with pypdf."""
    title = f"Kit previdenciário - {_clean(attendance.get('lead_name')) or 'caso'}"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((48, 48), title, fontsize=16, fontname="hebo")
    y = 78
    for line in _lines(dossier):
        if y > 780:
            page = document.new_page()
            y = 52
        is_heading = line.isupper() and len(line) > 3
        page.insert_text((48, y), line, fontsize=10 if is_heading else 9, fontname="hebo" if is_heading else "helv")
        y += 16 if line else 10
    document.set_metadata({"title": title, "subject": "Rascunho para revisão profissional", "author": "PrevIA"})
    output = document.tobytes(garbage=4, deflate=True)
    document.close()

    # pypdf valida que o conteúdo entregue é um PDF legível antes da resposta.
    reader = PdfReader(BytesIO(output))
    if not reader.pages:
        raise ValueError("O PDF gerado não possui páginas.")
    return output
