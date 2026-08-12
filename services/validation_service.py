"""Validações de domínio reutilizáveis, independentes da interface."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_cpf(value: str) -> ValidationResult:
    cpf = "".join(character for character in value if character.isdigit())
    if len(cpf) != 11:
        return ValidationResult(("CPF deve conter 11 dígitos.",))
    if cpf == cpf[0] * 11:
        return ValidationResult(("CPF inválido.",))

    def digit(partial: str, weight_start: int) -> str:
        total = sum(int(number) * weight for number, weight in zip(partial, range(weight_start, 1, -1)))
        remainder = (total * 10) % 11
        return str(0 if remainder == 10 else remainder)

    if digit(cpf[:9], 10) != cpf[9] or digit(cpf[:10], 11) != cpf[10]:
        return ValidationResult(("CPF inválido.",))
    return ValidationResult()


def validate_number(value: object, label: str, minimum: float = 0, maximum: float | None = None) -> ValidationResult:
    if isinstance(value, bool):
        return ValidationResult((f"{label} deve ser numérico.",))
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ValidationResult((f"{label} deve ser numérico.",))
    if not isfinite(number):
        return ValidationResult((f"{label} deve ser finito.",))
    if number < minimum:
        return ValidationResult((f"{label} deve ser maior ou igual a {minimum:g}.",))
    if maximum is not None and number > maximum:
        return ValidationResult((f"{label} deve ser menor ou igual a {maximum:g}.",))
    return ValidationResult()


def validate_contribution_time(years: object, months: object, days: object) -> ValidationResult:
    errors = [
        *validate_number(years, "Anos", 0, 100).errors,
        *validate_number(months, "Meses", 0, 11).errors,
        *validate_number(days, "Dias", 0, 30).errors,
    ]
    return ValidationResult(tuple(errors))
