"""Catálogo e validação de solicitações de cálculos previdenciários.

Este módulo intencionalmente não contém fórmulas jurídicas. Cada motor só deve
ser registrado após revisão técnica, fonte normativa e testes de regressão.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.validation_service import ValidationResult, validate_number


@dataclass(frozen=True)
class CalculationModule:
    code: str
    title: str
    requires_human_review: bool = True


CALCULATION_MODULES = (
    CalculationModule("planejamento_rgps", "Planejamento previdenciário RGPS"),
    CalculationModule("bpc_loas", "Análise documental BPC/LOAS"),
    CalculationModule("revisao_beneficio", "Revisão de benefício"),
    CalculationModule("atrasados", "Apuração de parcelas em atraso"),
    CalculationModule("restabelecimento", "Restabelecimento de benefício"),
    CalculationModule("rpps_uniao", "Análise RPPS União"),
    CalculationModule("rpps_est_mun", "Análise RPPS estadual ou municipal"),
    CalculationModule("contribuicao_atraso", "Contribuições em atraso"),
)
_MODULES_BY_CODE = {module.code: module for module in CALCULATION_MODULES}


def get_calculation_module(code: str) -> CalculationModule:
    try:
        return _MODULES_BY_CODE[code]
    except KeyError as error:
        raise ValueError("Módulo de cálculo não reconhecido.") from error


def validate_calculation_request(code: str, inputs: dict[str, Any]) -> ValidationResult:
    """Valida somente integridade de entrada; não atesta elegibilidade jurídica."""
    get_calculation_module(code)
    if not isinstance(inputs, dict):
        return ValidationResult(("Os dados do cálculo devem ser um objeto.",))
    errors: list[str] = []
    for name, value in inputs.items():
        if not isinstance(name, str) or not name.strip():
            errors.append("Todo campo do cálculo precisa ter um nome válido.")
        if isinstance(value, float):
            errors.extend(validate_number(value, name).errors)
        elif isinstance(value, (str, int, bool, type(None), list, dict)):
            continue
        else:
            errors.append(f"{name} possui um tipo de dado não suportado.")
    return ValidationResult(tuple(errors))
