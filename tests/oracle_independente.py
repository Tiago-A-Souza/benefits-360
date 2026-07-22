"""
Oráculo de referência INDEPENDENTE do motor — só para authoring/validação de fixtures.
Não importar newport_motor.finance nem newport_motor.engine.
"""

from __future__ import annotations

IOF_BPS = 238


def round_half_up(num: int, den: int) -> int:
    if num >= 0:
        return (num + den // 2) // den
    return -((-num + den // 2) // den)


def apply_iof_exclui(valor_exclui: int) -> int:
    return round_half_up(valor_exclui * (10_000 + IOF_BPS), 10_000)


def valor_tabela(faixa: int, base: int = 100_000, incremento: int = 10_000) -> int:
    return base + faixa * incremento


def faixa_idade(idade: int) -> int:
    limites = (18, 23, 28, 33, 38, 43, 48, 53, 58)
    for idx, lim in enumerate(limites):
        if idade <= lim:
            return idx
    return 9


def recorrente(valor: int, basis: str, tipo_fiscal: str) -> int:
    if tipo_fiscal == "operadora":
        return valor
    if basis == "inclui_iof":
        return valor
    return apply_iof_exclui(valor)
