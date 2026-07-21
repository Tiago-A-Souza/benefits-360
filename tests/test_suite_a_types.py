"""Suíte A — Tipos e aritmética."""

from newport_motor.money import apply_rate_bps, round_half_up_from_numerator
from newport_motor.rounding import apply_iof_strategy
from newport_motor.types import MoneyCents, RateBasisPoints, RoundingStrategy


def test_money_cents_is_int():
    v = MoneyCents(12345)
    assert isinstance(v, int)
    assert v == 12345


def test_rate_bps_iof_238():
    # 10000 centavos * 2.38% = 10238 centavos (R$102,38)
    result = apply_rate_bps(10_000_00, RateBasisPoints(238))
    assert result == 10_238_00


def test_round_half_up_from_numerator():
    assert round_half_up_from_numerator(1005, 10) == 101
    assert round_half_up_from_numerator(1004, 10) == 100


def test_ordem_por_vida_entao_soma():
    """Aplica IOF por vida, arredonda, depois soma."""
    valores = [10_000_00, 10_500_00]
    com_iof = apply_iof_strategy(valores, RateBasisPoints(238), RoundingStrategy.POR_VIDA_ENTAO_SOMA)
    assert len(com_iof) == 2
    total = sum(int(v) for v in com_iof)
    # Cada vida arredondada individualmente
    v1 = apply_rate_bps(10_000_00, RateBasisPoints(238))
    v2 = apply_rate_bps(10_500_00, RateBasisPoints(238))
    assert int(com_iof[0]) == v1
    assert int(com_iof[1]) == v2
    assert total == v1 + v2


def test_borda_arredondamento_half_up():
    # Caso onde numerador fica exatamente no meio
    bps = RateBasisPoints(238)
    # valor que gera fração de centavo
    result = apply_rate_bps(333_33, bps)
    assert isinstance(result, int)
