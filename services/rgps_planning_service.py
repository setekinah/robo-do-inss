"""Triagem determinística das regras RGPS selecionadas para 2026.

Escopo: regra geral, regra de pontos e idade mínima progressiva. Não calcula
RMI, não verifica CNIS e não substitui a análise jurídica individual.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


RULESET_VERSION = "RGPS-EC103-2026.1"
REFORM_EFFECTIVE_DATE = date(2019, 11, 13)
Sex = Literal["F", "M"]


@dataclass(frozen=True)
class RgpsPlanningInput:
    birth_date: date
    sex: Sex
    contribution_months: int
    carencia_months: int
    affiliation_date: date


@dataclass(frozen=True)
class RuleScreening:
    code: str
    title: str
    eligible: bool
    pending_requirements: tuple[str, ...]


@dataclass(frozen=True)
class RgpsPlanningResult:
    ruleset_version: str
    reference_date: date
    age_months: int
    contribution_months: int
    screenings: tuple[RuleScreening, ...]
    notices: tuple[str, ...]


def age_in_months(birth_date: date, reference_date: date) -> int:
    if birth_date > reference_date:
        raise ValueError("Data de nascimento não pode ser futura.")
    months = (reference_date.year - birth_date.year) * 12 + reference_date.month - birth_date.month
    return months - int(reference_date.day < birth_date.day)


def _missing(label: str, actual: int, required: int, suffix: str) -> str | None:
    if actual >= required:
        return None
    remaining = required - actual
    return f"{label}: faltam {remaining} {suffix}."


def screen_rgps_planning(data: RgpsPlanningInput, reference_date: date | None = None) -> RgpsPlanningResult:
    """Aplica critérios objetivos de acesso vigentes em 2026.

    A saída é deliberadamente uma triagem: documentos, períodos especiais,
    vínculos públicos, qualidade de segurado e direito adquirido requerem
    conferência humana e CNIS.
    """
    if data.sex not in {"F", "M"}:
        raise ValueError("Sexo deve ser 'F' ou 'M'.")
    if data.contribution_months < 0 or data.carencia_months < 0:
        raise ValueError("Tempo de contribuição e carência não podem ser negativos.")
    today = reference_date or date.today()
    if today.year != 2026:
        raise ValueError("Este motor é versionado exclusivamente para a competência de 2026.")

    age_months = age_in_months(data.birth_date, today)
    female = data.sex == "F"
    before_reform = data.affiliation_date < REFORM_EFFECTIVE_DATE
    general_age = 62 * 12 if female else 65 * 12
    general_contribution = 15 * 12 if female or before_reform else 20 * 12
    transition_contribution = 30 * 12 if female else 35 * 12
    points_required = 93 * 12 if female else 103 * 12
    progressive_age = 59 * 12 + 6 if female else 64 * 12 + 6
    carencia_required = 180

    general_pending = tuple(filter(None, (
        _missing("Idade mínima", age_months, general_age, "meses"),
        _missing("Tempo de contribuição", data.contribution_months, general_contribution, "meses"),
        _missing("Carência", data.carencia_months, carencia_required, "contribuições"),
    )))
    screenings = [RuleScreening("regra_geral", "Aposentadoria programada", not general_pending, general_pending)]

    if before_reform:
        points_pending = tuple(filter(None, (
            _missing("Tempo de contribuição", data.contribution_months, transition_contribution, "meses"),
            _missing("Pontuação idade + contribuição", age_months + data.contribution_months, points_required, "meses-equivalentes"),
            _missing("Carência", data.carencia_months, carencia_required, "contribuições"),
        )))
        progressive_pending = tuple(filter(None, (
            _missing("Idade mínima progressiva", age_months, progressive_age, "meses"),
            _missing("Tempo de contribuição", data.contribution_months, transition_contribution, "meses"),
            _missing("Carência", data.carencia_months, carencia_required, "contribuições"),
        )))
        screenings.extend((
            RuleScreening("transicao_pontos", "Transição por pontos", not points_pending, points_pending),
            RuleScreening("transicao_idade_progressiva", "Transição por idade progressiva", not progressive_pending, progressive_pending),
        ))

    notices = [
        "Triagem de requisitos objetivos; a concessão depende da conferência do CNIS e da análise jurídica.",
        "Este motor não analisa direito adquirido, pedágios, atividade especial, rural, professor, pessoa com deficiência, CTC ou RPPS.",
    ]
    if not before_reform:
        notices.append("Regras de transição não foram avaliadas porque a filiação informada é posterior à EC 103/2019.")
    return RgpsPlanningResult(RULESET_VERSION, today, age_months, data.contribution_months, tuple(screenings), tuple(notices))


def serialize_planning_result(result: RgpsPlanningResult) -> dict[str, object]:
    """Converte o resultado para o formato JSON armazenado no repositório."""
    return {
        "ruleset_version": result.ruleset_version,
        "reference_date": result.reference_date.isoformat(),
        "age_months": result.age_months,
        "contribution_months": result.contribution_months,
        "screenings": [
            {
                "code": screening.code,
                "title": screening.title,
                "eligible": screening.eligible,
                "pending_requirements": list(screening.pending_requirements),
            }
            for screening in result.screenings
        ],
        "notices": list(result.notices),
    }
