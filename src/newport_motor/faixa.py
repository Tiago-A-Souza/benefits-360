"""Cálculo de idade e faixa etária (DP-01, DP-08)."""

from __future__ import annotations

from datetime import date

# Faixas ANS padrão (10 faixas: 0–9)
_FAIXA_LIMITES = (18, 23, 28, 33, 38, 43, 48, 53, 58)


def idade_completa_em(nascimento: date, referencia: date) -> int:
    anos = referencia.year - nascimento.year
    if (referencia.month, referencia.day) < (nascimento.month, nascimento.day):
        anos -= 1
    return anos


def faixa_de_idade(idade: int) -> int:
    if idade < 0:
        raise ValueError("idade negativa")
    for idx, limite in enumerate(_FAIXA_LIMITES):
        if idade <= limite:
            return idx
    return 9


def faixa_em(nascimento: date, referencia: date) -> tuple[int, int]:
    idade = idade_completa_em(nascimento, referencia)
    return idade, faixa_de_idade(idade)
