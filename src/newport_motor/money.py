"""Aritmética monetária em centavos inteiros — sem float."""

from __future__ import annotations

from newport_motor.types import MoneyCents, RateBasisPoints


def money(centavos: int) -> MoneyCents:
    return MoneyCents(int(centavos))


def round_half_up_centavos(valor: int) -> MoneyCents:
    """Arredondamento half-up quando valor está em sub-centavos (escala 1/10000)."""
    return MoneyCents(round_half_up_from_numerator(valor, 100))


def apply_rate_bps(valor_centavos: int, bps: RateBasisPoints) -> int:
    """Aplica taxa em basis points com arredondamento half-up por operação."""
    numerador = valor_centavos * (10_000 + int(bps))
    return round_half_up_from_numerator(numerador, 10_000)


def round_half_up_from_numerator(numerador: int, denominador: int) -> int:
    if numerador >= 0:
        return (numerador + denominador // 2) // denominador
    return (numerador - denominador // 2) // denominador


def add_money(*valores: MoneyCents) -> MoneyCents:
    return MoneyCents(sum(int(v) for v in valores))


def subtract_money(a: MoneyCents, b: MoneyCents) -> MoneyCents:
    return MoneyCents(int(a) - int(b))


def abs_diff(a: MoneyCents, b: MoneyCents) -> MoneyCents:
    return MoneyCents(abs(int(a) - int(b)))
