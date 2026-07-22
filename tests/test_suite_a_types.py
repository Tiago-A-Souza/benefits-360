"""Suíte A — Tipos e aritmética."""

from newport_motor.money import apply_rate_bps, round_half_up_from_numerator
from newport_motor.rounding import apply_iof_strategy
from newport_motor.types import MoneyCents, PriceBasis, RateBasisPoints, RoundingStrategy, TipoFiscal


def test_money_cents_is_int():
    v = MoneyCents(12345)
    assert isinstance(v, int)
    assert v == 12345


def test_rate_bps_iof_238():
    result = apply_rate_bps(10_000_00, RateBasisPoints(238))
    assert result == 10_238_00


def test_round_half_up_positivo():
    assert round_half_up_from_numerator(1005, 10) == 101
    assert round_half_up_from_numerator(1004, 10) == 100
    assert round_half_up_from_numerator(5, 10) == 1
    assert round_half_up_from_numerator(4, 10) == 0


def test_round_half_up_negativo():
    assert round_half_up_from_numerator(-1005, 10) == -101
    assert round_half_up_from_numerator(-1004, 10) == -100
    assert round_half_up_from_numerator(-5, 10) == -1
    assert round_half_up_from_numerator(-4, 10) == 0


def test_ordem_por_vida_entao_soma():
    valores = [(10_000_00, PriceBasis.EXCLUI_IOF), (10_500_00, PriceBasis.EXCLUI_IOF)]
    com_iof = apply_iof_strategy(
        valores, TipoFiscal.SEGURADORA, RateBasisPoints(238), RoundingStrategy.POR_VIDA_ENTAO_SOMA
    )
    v1 = apply_rate_bps(10_000_00, RateBasisPoints(238))
    v2 = apply_rate_bps(10_500_00, RateBasisPoints(238))
    assert int(com_iof[0]) == v1
    assert int(com_iof[1]) == v2


def test_inclui_iof_nao_reaplica():
    valores = [(10_238_00, PriceBasis.INCLUI_IOF)]
    com_iof = apply_iof_strategy(
        valores, TipoFiscal.SEGURADORA, RateBasisPoints(238), RoundingStrategy.POR_VIDA_ENTAO_SOMA
    )
    assert int(com_iof[0]) == 10_238_00


def test_no_total_codigo_reservado_nao_homologado_piloto():
    """Código reservado em finance.py; motor bloqueia no_total com B-07 no piloto."""
    from newport_motor.finance import total_recorrente_de_bases_exclui
    from newport_motor.money import apply_rate_bps

    bases = [10_000_00, 10_500_00]
    per_vida = apply_iof_strategy(
        [(b, PriceBasis.EXCLUI_IOF) for b in bases],
        TipoFiscal.SEGURADORA,
        RateBasisPoints(238),
        RoundingStrategy.NO_TOTAL,
    )
    assert int(per_vida[0]) == 10_000_00
    total = total_recorrente_de_bases_exclui(
        bases, TipoFiscal.SEGURADORA, RateBasisPoints(238), RoundingStrategy.NO_TOTAL
    )
    assert int(total) == apply_rate_bps(20_500_00, RateBasisPoints(238))
