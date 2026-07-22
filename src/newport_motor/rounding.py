"""Registry de estratégias de arredondamento (não inclui regimes de copart)."""

from __future__ import annotations

from newport_motor.finance import normalizar_vidas_para_recorrente, total_recorrente_de_bases_exclui
from newport_motor.types import MoneyCents, PriceBasis, RateBasisPoints, RoundingStrategy, TipoFiscal


def apply_iof_strategy(
    valores_basis: list[tuple[int, PriceBasis]],
    tipo_fiscal: TipoFiscal,
    iof_bps: RateBasisPoints,
    strategy: RoundingStrategy,
) -> list[MoneyCents]:
    return normalizar_vidas_para_recorrente(valores_basis, tipo_fiscal, iof_bps, strategy)


def total_com_iof_strategy(
    bases_exclui: list[int],
    tipo_fiscal: TipoFiscal,
    iof_bps: RateBasisPoints,
    strategy: RoundingStrategy,
) -> MoneyCents:
    return total_recorrente_de_bases_exclui(bases_exclui, tipo_fiscal, iof_bps, strategy)
