"""Geração de minuta de honorários sem dependência da sessão visual."""

from __future__ import annotations

from datetime import date
from typing import Any

from office_settings import resolve_fee_percentage


def build_fee_contract_preview(flow_name: str, lead_name: str, office_settings: dict[str, Any], today: date | None = None) -> str:
    client_name = lead_name or "CLIENTE"
    draft_date = (today or date.today()).strftime("%d/%m/%Y")
    fee_percentage = resolve_fee_percentage(flow_name, office_settings)
    return f"""
CONTRATO PARTICULAR DE HONORARIOS ADVOCATICIOS

Data da minuta: {draft_date}

CONTRATANTE:
{client_name}

OBJETO:
Prestacao de servicos advocaticios para analise, requerimento administrativo e/ou medidas correlatas
relacionadas ao beneficio previdenciario de {flow_name}.

HONORARIOS:
Fica ajustado, a titulo de honorarios advocaticios contratuais, o percentual de {fee_percentage}% ({fee_percentage} por cento)
sobre o valor economico obtido com o beneficio, incluindo valores atrasados, parcelas retroativas,
RPV, precatorio ou quantias liberadas em favor do contratante, observada a estrategia juridica adotada.

PAGAMENTO:
Os honorarios serao pagos no momento da liberacao dos valores, autorizando o contratante a deducao
do percentual contratado ou o pagamento imediato apos o recebimento do beneficio.

CIENCIA:
Esta minuta e um modelo inicial exibido pelo sistema e deve ser revisada e validada pelo escritorio
antes da assinatura definitiva.
"""
