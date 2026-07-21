"""Registry de estratégias de arredondamento (não inclui regimes de copart)."""

from __future__ import annotations

from collections.abc import Callable

from newport_motor.money import apply_rate_bps, round_half_up_from_numerator
from newport_motor.types import MoneyCents, RateBasisPoints, RoundingStrategy

ApplyIofFn = Callable[[list[int], RateBasisPoints], list[MoneyCents]]


def _por_vida_entao_soma(valores: list[int], iof_bps: RateBasisPoints) -> list[MoneyCents]:
    return [MoneyCents(apply_rate_bps(v, iof_bps)) for v in valores]


def _soma_entao_aplica(valores: list[int], iof_bps: RateBasisPoints) -> list[MoneyCents]:
    total = sum(valores)
    total_com_iof = apply_rate_bps(total, iof_bps)
    if not valores:
        return []
    if len(valores) == 1:
        return [MoneyCents(total_com_iof)]
    # Distribui proporcionalmente e ajusta resíduo no último
    partes: list[MoneyCents] = []
    acumulado = 0
    for i, v in enumerate(valores[:-1]):
        parte = round_half_up_from_numerator(total_com_iof * v, total)
        partes.append(MoneyCents(parte))
        acumulado += parte
    partes.append(MoneyCents(total_com_iof - acumulado))
    return partes


def _no_total(valores: list[int], iof_bps: RateBasisPoints) -> list[MoneyCents]:
    # Valores por vida sem IOF; IOF aplicado apenas no total externo
    return [MoneyCents(v) for v in valores]


ROUNDING_REGISTRY: dict[RoundingStrategy, ApplyIofFn] = {
    RoundingStrategy.POR_VIDA_ENTAO_SOMA: _por_vida_entao_soma,
    RoundingStrategy.SOMA_ENTAO_APLICA: _soma_entao_aplica,
    RoundingStrategy.NO_TOTAL: _no_total,
}


def apply_iof_strategy(
    valores_exclui_iof: list[int],
    iof_bps: RateBasisPoints,
    strategy: RoundingStrategy,
) -> list[MoneyCents]:
    fn = ROUNDING_REGISTRY[strategy]
    return fn(valores_exclui_iof, iof_bps)
