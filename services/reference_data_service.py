"""Validação de conjuntos locais de índices e tabelas de referência."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlparse


REFERENCE_KINDS = {"indices", "tabelas"}


@dataclass(frozen=True)
class ReferenceDataset:
    kind: str
    version: str
    source_url: str
    effective_date: date
    data: dict[str, Any]


def validate_reference_dataset(dataset: ReferenceDataset) -> None:
    if dataset.kind not in REFERENCE_KINDS:
        raise ValueError("Tipo de referência inválido.")
    if not dataset.version.strip():
        raise ValueError("Informe a versão da referência.")
    parsed = urlparse(dataset.source_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("A fonte deve ser uma URL HTTPS válida.")
    if not dataset.data:
        raise ValueError("A referência não pode estar vazia.")
