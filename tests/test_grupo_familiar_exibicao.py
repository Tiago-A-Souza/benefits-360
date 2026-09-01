"""Exibição da visão por grupo familiar — rótulos anônimos e acomodação."""

from __future__ import annotations

from newport_app.presentation.formatacao import normalizar_acomodacao_exibicao
from newport_app.presentation.grupos_familiares import (
    rotulo_grupo,
    rotulo_parentesco_exibicao,
    rotulo_vida_agregada,
)
from newport_app.presentation.grupos_familiares import GrupoFamiliarMontado
from newport_app.models.responses import DetalheVidaComparativo


def test_rotulo_vida_agregada_inclui_vinculo():
    assert rotulo_vida_agregada("29 a 33", "conjuge") == "Beneficiário · 29 a 33 · cônjuge"
    assert rotulo_vida_agregada("0 a 18", "titular") == "Beneficiário · 0 a 18 · titular"
    assert rotulo_vida_agregada("19 a 23", "filho") == "Beneficiário · 19 a 23 · filho(a)"


def test_rotulo_grupo_numerado_sem_nomes():
    g = GrupoFamiliarMontado(
        grupo_id="g1",
        titular=None,
        membros=[
            DetalheVidaComparativo(vida_id="v1", nome="A"),
            DetalheVidaComparativo(vida_id="v2", nome="B"),
        ],
    )
    assert rotulo_grupo(g, nomes_ocultos=True, numero=3) == "Grupo 3"


def test_normalizar_acomodacao_exibicao():
    assert normalizar_acomodacao_exibicao("apartamento") == "Apartamento"
    assert normalizar_acomodacao_exibicao("APARTAMENTO") == "Apartamento"
    assert normalizar_acomodacao_exibicao("Apartamento") == "Apartamento"
    assert normalizar_acomodacao_exibicao(None) is None


def test_rotulo_parentesco_exibicao():
    assert rotulo_parentesco_exibicao("conjuge") == "cônjuge"
    assert rotulo_parentesco_exibicao("filho") == "filho(a)"
