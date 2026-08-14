"""Regras parametrizadas para a estimativa de salário-maternidade."""

from __future__ import annotations

SALARIO_MINIMO_2026 = 1621.00
TETO_INSS_2026 = 8537.55


def clamp_benefit_value(value: float) -> float:
    return min(max(float(value), SALARIO_MINIMO_2026), TETO_INSS_2026)


def estimate_maternity_benefit(category: str, values: list[float] | None = None, mei_standard: bool = False) -> dict[str, float | str]:
    contributions = [float(value) for value in values or []]
    if category == "MEI" and mei_standard:
        monthly_value = SALARIO_MINIMO_2026
        note = "Para MEI padrao, a estimativa considera o salario minimo de 2026."
    else:
        if not contributions:
            raise ValueError("Informe ao menos uma remuneracao ou contribuicao.")
        monthly_value = clamp_benefit_value(sum(contributions) / len(contributions))
        notes = {
            "CLT": "Para CLT, a estimativa usa a remuneracao informada ou a media dos ultimos salarios.",
            "MEI": "Para MEI com complementacao, a estimativa segue a media das contribuicoes informadas.",
            "Autonoma / Facultativa": "Para autonoma ou facultativa, a estimativa usa a media das contribuicoes informadas, respeitando minimo e teto.",
            "Desempregada": "Para desempregada, a estimativa usa a media das contribuicoes disponiveis.",
        }
        note = notes.get(category, "Estimativa baseada nas contribuicoes informadas.")
    return {"monthly_value": monthly_value, "total_value": monthly_value * 4, "note": note}
