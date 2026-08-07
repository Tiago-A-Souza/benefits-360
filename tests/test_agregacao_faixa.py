"""Testes do invariante de agregação por faixa etária."""

from __future__ import annotations

import random

import pytest

from newport_app.agregacao_faixa import agregar_valores_faixa


def test_faixa_homogenea_tres_vidas():
    unit, total, alerta = agregar_valores_faixa([10000, 10000, 10000])
    assert unit == 10000
    assert total == 30000
    assert alerta is None


def test_faixa_heterogenea_soma_todos():
    unit, total, alerta = agregar_valores_faixa([10000, 10000, 12000])
    assert unit is None
    assert total == 32000
    assert alerta is not None


def test_lista_vazia():
    unit, total, alerta = agregar_valores_faixa([])
    assert unit is None
    assert total is None
    assert alerta is None


@pytest.mark.parametrize(
    "valores",
    [
        [50_000],
        [10_000, 20_000, 30_000],
        [100, 100, 200, 300],
        [40978, 47945, 40978],
    ],
)
def test_total_igual_soma_direta(valores: list[int]):
    _, total, _ = agregar_valores_faixa(valores)
    assert total == sum(valores)


@pytest.mark.parametrize("seed", [1, 7, 42, 99])
def test_propriedade_soma_aleatoria(seed: int):
    rng = random.Random(seed)
    for _ in range(20):
        n = rng.randint(1, 30)
        valores = [rng.randint(1_000, 500_000) for _ in range(n)]
        _, total, _ = agregar_valores_faixa(valores)
        assert total == sum(valores)
