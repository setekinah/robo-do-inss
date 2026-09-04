"""Leitura conservadora e rastreável de extratos CNIS enviados ao escritório.

Este módulo não acessa o Meu INSS, não calcula tempo de contribuição e não
reconhece direito a benefício. Ele somente estrutura sinais encontrados no
texto extraído de documentos locais para a conferência do profissional.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


ANALYZER_SCHEMA_VERSION = "1.0"
NORMATIVE_SOURCE = {
    "id": "pt990_anexo_v",
    "titulo": "Indicadores CNIS — Anexo V da Portaria DIRBEN/INSS nº 990",
    "url": "https://portalin.inss.gov.br/assets/anexos/pt990/AnexoV.pdf",
    "uso": "Referência para conferência humana de indicadores; validar versão vigente no catálogo oficial.",
}

_DATE = r"(0?[1-9]|[12]\d|3[01])/(0?[1-9]|1[0-2])/(19\d{2}|20\d{2})"
_PAGE = re.compile(r"\[P[aá]gina\s+(\d+)", re.IGNORECASE)
_PEXT = re.compile(r"(?<![A-Z0-9])PEXT(?![A-Z0-9])", re.IGNORECASE)
_SPECIAL = re.compile(r"\b(PPP|LTCAT|ATIVIDADE\s+ESPECIAL|AGENTE[S]?\s+NOCIVO[S]?|INSALUBRIDADE)\b", re.IGNORECASE)
_PERIOD = re.compile(rf"{_DATE}\s*(?:A|ATÉ|ATE|[-–])\s*{_DATE}", re.IGNORECASE)


class CNISInput(BaseModel):
    """Contrato mínimo entre extração documental e análise de CNIS."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    document_id: int | None = None
    document_name: str = "CNIS"
    raw_text: str = Field(max_length=2_000_000)

    @field_validator("raw_text")
    @classmethod
    def raw_text_must_exist(cls, value: str) -> str:
        if not value:
            raise ValueError("O CNIS não possui texto extraído para análise.")
        return value


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: int | None = None
    page: int | None = None
    excerpt: str = Field(min_length=1, max_length=280)


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    category: str
    status: str = "requer_revisao_humana"
    message: str
    guidance: str
    evidence: list[Evidence] = Field(default_factory=list)


class CNISAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = ANALYZER_SCHEMA_VERSION
    status: str
    source: dict[str, str]
    findings: list[Finding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    conclusion: str


def _page_at(text: str, position: int) -> int | None:
    pages = list(_PAGE.finditer(text, 0, position))
    return int(pages[-1].group(1)) if pages else None


def _excerpt(text: str, position: int, width: int = 240) -> str:
    start = max(0, position - 80)
    end = min(len(text), position + width)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def _evidence(text: str, position: int, document_id: int | None) -> Evidence:
    return Evidence(document_id=document_id, page=_page_at(text, position), excerpt=_excerpt(text, position))


def _parse_period_date(match: re.Match[str], offset: int) -> date | None:
    try:
        return date(int(match.group(offset + 2)), int(match.group(offset + 1)), int(match.group(offset)))
    except (ValueError, IndexError):
        return None


def _possible_long_periods(text: str, document_id: int | None) -> list[Finding]:
    findings: list[Finding] = []
    for match in _PERIOD.finditer(text):
        start = _parse_period_date(match, 1)
        end = _parse_period_date(match, 4)
        if not start or not end or end < start or (end - start).days < 365:
            continue
        findings.append(Finding(
            code="PERIODO_EXTENSO_A_CONFERIR", category="periodo",
            message="Período superior a 12 meses identificado no texto do CNIS.",
            guidance="Conferir competências, remunerações e eventuais interrupções no extrato original; o achado não confirma tempo ou carência.",
            evidence=[_evidence(text, match.start(), document_id)],
        ))
    return findings


def analyze_cnis_text(*, raw_text: str, document_id: int | None = None, document_name: str = "CNIS") -> dict[str, Any]:
    """Retorna apenas sinais revisáveis; falhas de extração degradam com segurança."""
    try:
        source = CNISInput(document_id=document_id, document_name=document_name, raw_text=raw_text)
    except ValidationError as exc:
        return CNISAnalysis(
            status="nao_analisado", source=NORMATIVE_SOURCE,
            warnings=[f"Texto inválido para análise: {error['msg']}" for error in exc.errors()],
            conclusion="Não foi possível analisar o CNIS. Reextraia o documento e confira o original.",
        ).model_dump()

    findings: list[Finding] = []
    for match in _PEXT.finditer(source.raw_text):
        findings.append(Finding(
            code="PEXT", category="indicador_cnis",
            message="Indicador PEXT localizado no texto extraído.",
            guidance="Associar o indicador à competência e conferir a providência aplicável no catálogo oficial antes de qualquer conclusão.",
            evidence=[_evidence(source.raw_text, match.start(), source.document_id)],
        ))
    for match in _SPECIAL.finditer(source.raw_text):
        findings.append(Finding(
            code="POSSIVEL_PERIODO_ESPECIAL", category="atividade_especial",
            message=f"Referência a “{match.group(0)}” localizada no documento.",
            guidance="Solicitar e revisar PPP/LTCAT e demais provas. A menção textual não comprova exposição, período especial ou conversão.",
            evidence=[_evidence(source.raw_text, match.start(), source.document_id)],
        ))
    findings.extend(_possible_long_periods(source.raw_text, source.document_id))

    unique: dict[str, Finding] = {}
    for finding in findings:
        unique.setdefault(finding.code, finding)
    selected = list(unique.values())
    analysis = CNISAnalysis(
        status="revisao_humana_obrigatoria" if selected else "sem_sinais_automaticos",
        source=NORMATIVE_SOURCE, findings=selected,
        warnings=[
            "Resultado obtido de texto extraído localmente; confira o CNIS original e a competência de cada indicador.",
            "O analisador não calcula tempo de contribuição, carência, RMI ou elegibilidade.",
        ],
        conclusion=("Foram encontrados sinais para conferência profissional." if selected else "Nenhum sinal automático foi localizado; isso não confirma ausência de pendências."),
    )
    return analysis.model_dump()


def analyze_cnis_documents(documents: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Analisa somente documentos CNIS, preservando seus identificadores."""
    analyses = [analyze_cnis_text(raw_text=str(document.get("raw_text") or ""), document_id=document.get("id"), document_name=str(document.get("document_name") or "CNIS")) for document in documents if str(document.get("document_code") or "").upper() == "CNIS"]
    if not analyses:
        return CNISAnalysis(status="documento_ausente", source=NORMATIVE_SOURCE, warnings=["Nenhum CNIS com texto extraído foi localizado no caso."], conclusion="Anexe o CNIS para iniciar a leitura técnica preliminar.").model_dump()
    findings = [finding for analysis in analyses for finding in analysis["findings"]]
    warnings = [warning for analysis in analyses for warning in analysis["warnings"]]
    return CNISAnalysis(
        status="revisao_humana_obrigatoria" if findings else "sem_sinais_automaticos",
        source=NORMATIVE_SOURCE, findings=[Finding.model_validate(item) for item in findings], warnings=warnings,
        conclusion=("A análise consolidada requer revisão humana." if findings else "Nenhum sinal automático foi localizado nos CNIS analisados; confira os originais."),
    ).model_dump()
