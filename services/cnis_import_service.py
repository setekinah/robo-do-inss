"""Prévia local de extratos CNIS para conferência humana."""

from __future__ import annotations

from typing import Any

from document_intelligence import analyze_document_bundle


CNIS_FIELDS = ["cpf", "nit", "competencias", "vinculos", "salarios", "indicadores"]


def build_cnis_preview(file_paths: list[str]) -> dict[str, Any]:
    analysis = analyze_document_bundle(
        document_code="CNIS_IMPORTACAO",
        uploaded_files=file_paths,
        critical_fields=CNIS_FIELDS,
    )
    return {
        "extraction_status": analysis["extraction_status"],
        "confidence": float(analysis["extraction_confidence"]),
        "fields": analysis["extracted_data"],
        "technical_notes": analysis["technical_notes"],
        "text_excerpt": analysis["raw_text"][:5000],
    }
