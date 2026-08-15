"""Benchmark local para decidir a integração do dArchiva com o PrevIA.

Não transmite arquivos. A meta é medir a linha de base atual e comparar, com
o mesmo conjunto anonimizado, o resultado do dArchiva antes de qualquer
integração com documentos de clientes.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import document_intelligence


def normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def score_document(document: dict[str, Any]) -> dict[str, Any]:
    file_path = Path(str(document["path"])).expanduser().resolve()
    critical_fields = [str(field) for field in document.get("critical_fields", [])]
    analysis = document_intelligence.analyze_document_bundle(
        document_code=str(document.get("document_code", "DOCUMENTO")),
        uploaded_files=[str(file_path)],
        critical_fields=critical_fields,
    )
    expected = {str(key): str(value) for key, value in document.get("expected", {}).items()}
    extracted = analysis.get("extracted_data", {})
    field_results = {
        field: {
            "expected": bool(value),
            "matched": normalize(extracted.get(field)) == normalize(value) if value else None,
            "extracted": bool(extracted.get(field)),
        }
        for field, value in expected.items()
    }
    return {
        "id": str(document.get("id", file_path.name)),
        "document_code": str(document.get("document_code", "DOCUMENTO")),
        "status": analysis.get("extraction_status"),
        "confidence": analysis.get("extraction_confidence"),
        "source_type": analysis.get("source_type"),
        "technical_notes": analysis.get("technical_notes"),
        "field_results": field_results,
    }


def run_baseline(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = [score_document(item) for item in manifest.get("documents", [])]
    checked = [field for result in results for field in result["field_results"].values() if field["expected"]]
    matched = sum(1 for field in checked if field["matched"])
    return {
        "pilot": "previadarchiva-local-baseline",
        "documents": results,
        "metrics": {
            "documents_total": len(results),
            "fields_checked": len(checked),
            "fields_matched": matched,
            "field_accuracy": round(matched / len(checked), 4) if checked else None,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa o benchmark documental local do PrevIA.")
    parser.add_argument("manifest", type=Path, help="JSON com documentos anonimizados e campos esperados.")
    parser.add_argument("--output", type=Path, default=Path("darchiva_pilot_report.json"))
    args = parser.parse_args()
    report = run_baseline(args.manifest)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
