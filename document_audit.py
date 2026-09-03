"""Auditoria documental rastreável para CNIS e CTPS.

Este módulo não decide direito a benefício. Ele só compara dados extraídos de
documentos e informa o que foi confirmado, divergiu ou não pôde ser localizado.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from typing import Any, Iterable, Mapping

import document_intelligence


AUDIT_TYPE_CNIS_CTPS = "CNIS_X_CTPS"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalise(value: Any) -> str:
    value = unicodedata.normalize("NFKD", _text(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _valid_cnpj(value: Any) -> str:
    return document_intelligence.first_valid_identifier(_text(value), "cnpj")


def _parse_date(value: Any) -> datetime | None:
    try:
        return datetime.strptime(_text(value), "%d/%m/%Y")
    except ValueError:
        return None


def _page_for_offset(raw_text: str, offset: int) -> int | None:
    markers = list(re.finditer(r"\[P[aá]gina\s+(\d+)", raw_text, flags=re.IGNORECASE))
    previous = [marker for marker in markers if marker.start() <= offset]
    return int(previous[-1].group(1)) if previous else None


def _evidence(raw_text: str, document_code: str, vinculo: Mapping[str, Any]) -> dict[str, Any]:
    """Return an excerpt and page marker, never inventing a location."""
    candidates = [_valid_cnpj(vinculo.get("cnpj")), _text(vinculo.get("empregador"))]
    offset = -1
    for candidate in candidates:
        if candidate:
            offset = raw_text.lower().find(candidate.lower())
            if offset >= 0:
                break
    if offset < 0:
        start_date = _text(vinculo.get("data_inicio"))
        offset = raw_text.find(start_date) if start_date else -1
    excerpt = ""
    page = None
    if offset >= 0:
        page = _page_for_offset(raw_text, offset)
        excerpt = re.sub(r"\s+", " ", raw_text[max(0, offset - 70): offset + 230]).strip()
    return {
        "documento": document_code,
        "pagina": page,
        "trecho": excerpt or "Trecho não localizado automaticamente no texto extraído.",
        "campos": {
            "cnpj": _valid_cnpj(vinculo.get("cnpj")) or None,
            "empregador": _text(vinculo.get("empregador")) or None,
            "data_inicio": _text(vinculo.get("data_inicio")) or None,
            "data_fim": _text(vinculo.get("data_fim")) or None,
        },
    }


def _same_employer(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_cnpj, right_cnpj = _valid_cnpj(left.get("cnpj")), _valid_cnpj(right.get("cnpj"))
    if left_cnpj and right_cnpj:
        return left_cnpj == right_cnpj
    left_name, right_name = _normalise(left.get("empregador")), _normalise(right.get("empregador"))
    # Sem CNPJ só aceitamos o nome praticamente idêntico. Não há fuzzy match
    # para evitar que homônimos sejam tratados como prova de vínculo.
    return len(left_name) >= 8 and left_name == right_name


def _difference_days(left: Any, right: Any) -> int | None:
    left_date, right_date = _parse_date(left), _parse_date(right)
    return abs((left_date - right_date).days) if left_date and right_date else None


def _compare_pair(cnis: Mapping[str, Any], ctps: Mapping[str, Any], cnis_text: str, ctps_text: str) -> dict[str, Any]:
    differing_fields: list[dict[str, Any]] = []
    for key, label in (("data_inicio", "Data de admissão"), ("data_fim", "Data de saída")):
        cnis_value, ctps_value = _text(cnis.get(key)), _text(ctps.get(key))
        if not cnis_value or not ctps_value:
            differing_fields.append({"campo": label, "cnis": cnis_value or None, "ctps": ctps_value or None, "diferenca_dias": None})
        elif cnis_value != ctps_value:
            differing_fields.append({"campo": label, "cnis": cnis_value, "ctps": ctps_value, "diferenca_dias": _difference_days(cnis_value, ctps_value)})
    status = "confirmado" if not differing_fields else "divergente"
    return {
        "status": status,
        "risco": "verde" if status == "confirmado" else "amarelo",
        "titulo": "Vínculo confirmado entre CNIS e CTPS" if status == "confirmado" else "Divergência entre CNIS e CTPS",
        "empregador": _text(cnis.get("empregador")) or _text(ctps.get("empregador")),
        "cnpj": _valid_cnpj(cnis.get("cnpj")) or _valid_cnpj(ctps.get("cnpj")) or None,
        "diferencas": differing_fields,
        "impacto_potencial": (
            "Período consistente nos dois documentos." if status == "confirmado"
            else "Pode afetar o tempo de contribuição; requer conferência técnica e prova documental."
        ),
        "providencia": (
            "Sem providência automática." if status == "confirmado"
            else "Conferir o original e avaliar acerto de vínculo/remuneração antes de qualquer cálculo conclusivo."
        ),
        "requer_revisao": status != "confirmado",
        "evidencias": [_evidence(cnis_text, "CNIS", cnis), _evidence(ctps_text, "CTPS", ctps)],
    }


def _unmatched(vinculo: Mapping[str, Any], raw_text: str, origin: str) -> dict[str, Any]:
    other = "CTPS" if origin == "CNIS" else "CNIS"
    return {
        "status": "nao_localizado",
        "risco": "amarelo",
        "titulo": f"Vínculo do {origin} não localizado no {other}",
        "empregador": _text(vinculo.get("empregador")),
        "cnpj": _valid_cnpj(vinculo.get("cnpj")) or None,
        "diferencas": [],
        "impacto_potencial": "A ausência de correspondência não prova erro, mas impede confirmação automática do período.",
        "providencia": f"Conferir o {other}, anexar páginas pertinentes e validar manualmente o vínculo.",
        "requer_revisao": True,
        "evidencias": [_evidence(raw_text, origin, vinculo)],
    }


def build_cnis_ctps_audit(*, cnis_raw_text: str, ctps_raw_text: str) -> dict[str, Any]:
    """Compare only extracted employment links and preserve documentary evidence."""
    cnis_links = document_intelligence.extract_cnis_vinculos(cnis_raw_text)
    ctps_links = document_intelligence.extract_ctps_vinculos(ctps_raw_text)
    findings: list[dict[str, Any]] = []
    matched_ctps: set[int] = set()
    for cnis in cnis_links:
        match_index = next((index for index, ctps in enumerate(ctps_links) if index not in matched_ctps and _same_employer(cnis, ctps)), None)
        if match_index is None:
            findings.append(_unmatched(cnis, cnis_raw_text, "CNIS"))
            continue
        matched_ctps.add(match_index)
        findings.append(_compare_pair(cnis, ctps_links[match_index], cnis_raw_text, ctps_raw_text))
    for index, ctps in enumerate(ctps_links):
        if index not in matched_ctps:
            findings.append(_unmatched(ctps, ctps_raw_text, "CTPS"))

    summary = {
        "vinculos_cnis": len(cnis_links),
        "vinculos_ctps": len(ctps_links),
        "confirmados": sum(item["status"] == "confirmado" for item in findings),
        "divergentes": sum(item["status"] == "divergente" for item in findings),
        "nao_localizados": sum(item["status"] == "nao_localizado" for item in findings),
    }
    insufficient = not cnis_links or not ctps_links
    review_count = sum(bool(item["requer_revisao"]) for item in findings)
    return {
        "tipo": AUDIT_TYPE_CNIS_CTPS,
        "status": "base_insuficiente" if insufficient else ("revisao_necessaria" if review_count else "confirmada"),
        "resumo": summary,
        "conclusao": (
            "Não há vínculos estruturados suficientes nos dois documentos para realizar o cruzamento."
            if insufficient else (
                "Foram encontradas divergências ou vínculos sem correspondência; revisão humana obrigatória."
                if review_count else "Os vínculos extraídos estão consistentes entre CNIS e CTPS."
            )
        ),
        "avisos": [
            "Auditoria documental: não calcula direito, carência homologada, RMI ou elegibilidade.",
            "Cada divergência deve ser conferida no documento original antes de qualquer providência.",
        ],
        "achados": findings,
    }


def build_cnis_ctps_audit_from_documents(documents: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    by_code: dict[str, Mapping[str, Any]] = {}
    for document in documents:
        code = _text(document.get("document_code")).upper()
        if code in {"CNIS", "CTPS"} and _text(document.get("raw_text")):
            by_code[code] = document
    report = build_cnis_ctps_audit(
        cnis_raw_text=_text(by_code.get("CNIS", {}).get("raw_text")),
        ctps_raw_text=_text(by_code.get("CTPS", {}).get("raw_text")),
    )
    report["documentos"] = [
        {
            "id": document.get("id"),
            "codigo": code,
            "confianca_extracao": document.get("extraction_confidence"),
            "status_extracao": document.get("extraction_status"),
        }
        for code, document in by_code.items()
    ]
    return report


def serialise_report(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, sort_keys=True)
