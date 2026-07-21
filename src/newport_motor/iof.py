"""Aplicação de IOF conforme tipo fiscal e price_basis (DP-02)."""

from __future__ import annotations

from newport_motor.money import apply_rate_bps
from newport_motor.rounding import apply_iof_strategy
from newport_motor.types import (
    MoneyCents,
    PriceBasis,
    RateBasisPoints,
    RoundingStrategy,
    TipoFiscal,
)


def tipo_fiscal_aplica_iof(tipo_fiscal: TipoFiscal) -> bool:
    return tipo_fiscal == TipoFiscal.SEGURADORA


def valor_para_base_exclui_iof(
    valor_centavos: int,
    price_basis: PriceBasis,
    aplica_iof: bool,
    iof_bps: RateBasisPoints,
) -> int:
    """Normaliza valor para base exclui_iof quando possível."""
    if not aplica_iof:
        return valor_centavos
    if price_basis == PriceBasis.EXCLUI_IOF:
        return valor_centavos
    if price_basis == PriceBasis.INCLUI_IOF:
        # Remove IOF embutido: valor / (1 + iof)
        numerador = valor_centavos * 10_000
        return (numerador + (10_000 + int(iof_bps)) // 2) // (10_000 + int(iof_bps))
    return valor_centavos


def valor_com_iof(
    valor_exclui_iof: int,
    aplica_iof: bool,
    iof_bps: RateBasisPoints,
) -> MoneyCents:
    if not aplica_iof:
        return MoneyCents(valor_exclui_iof)
    return MoneyCents(apply_rate_bps(valor_exclui_iof, iof_bps))


def valores_vidas_com_iof(
    valores_exclui_iof: list[int],
    aplica_iof: bool,
    iof_bps: RateBasisPoints,
    strategy: RoundingStrategy,
) -> list[MoneyCents]:
    if not aplica_iof:
        return [MoneyCents(v) for v in valores_exclui_iof]
    return apply_iof_strategy(valores_exclui_iof, iof_bps, strategy)
