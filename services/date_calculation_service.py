"""Cálculos civis de intervalo, sem efeitos jurídicos implícitos."""

from __future__ import annotations

from datetime import date


def calculate_day_interval(start: date, end: date, inclusive: bool = False) -> int:
    if end < start:
        raise ValueError("A data final deve ser posterior ou igual à inicial.")
    return (end - start).days + int(inclusive)
