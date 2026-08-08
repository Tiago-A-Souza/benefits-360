"""Contagem de parentesco na importação SISCOR."""

from __future__ import annotations

import pytest

from newport_app.models.draft import ParentescoRascunho
from newport_app.models.siscor_import import LinhaSiscorCandidata
from newport_app.siscor_importer.parentesco_contagem import contar_parentesco


def _linha(**kwargs) -> LinhaSiscorCandidata:
    base = {
        "id": "l1",
        "numero_linha": 1,
        "parentesco_texto": None,
        "parentesco": None,
    }
    base.update(kwargs)
    return LinhaSiscorCandidata(**base)


def test_mix_titular_dependentes_fecha_total():
    linhas = []
    for i in range(27):
        linhas.append(
            _linha(
                id=f"t{i}",
                numero_linha=i + 1,
                parentesco_texto="TITULAR",
                parentesco=ParentescoRascunho.TITULAR,
            )
        )
    for i, (txt, par) in enumerate(
        [
            ("CÔNJUGE", ParentescoRascunho.CONJUGE),
            ("FILHO(A)", ParentescoRascunho.FILHO),
            ("COMPANHEIRO", ParentescoRascunho.COMPANHEIRO),
        ]
    ):
        qtd = [8, 5, 1][i]
        for j in range(qtd):
            linhas.append(
                _linha(
                    id=f"d{i}-{j}",
                    numero_linha=len(linhas) + 1,
                    parentesco_texto=txt,
                    parentesco=par,
                )
            )

    contagem = contar_parentesco(linhas)
    assert contagem.titulares == 27
    assert contagem.dependentes == 14
    assert contagem.sem_parentesco == 0
    assert contagem.total == 41


def test_somente_titulares():
    linhas = [
        _linha(
            id=f"t{i}",
            numero_linha=i + 1,
            parentesco_texto="TITULAR",
            parentesco=ParentescoRascunho.TITULAR,
        )
        for i in range(12)
    ]
    contagem = contar_parentesco(linhas)
    assert contagem.titulares == 12
    assert contagem.dependentes == 0
    assert contagem.total == 12


def test_parentesco_nao_mapeado():
    linhas = [
        _linha(
            id="t1",
            numero_linha=1,
            parentesco_texto="TITULAR",
            parentesco=ParentescoRascunho.TITULAR,
        ),
        _linha(
            id="x1",
            numero_linha=2,
            parentesco_texto="ENTEADO",
            parentesco=None,
        ),
    ]
    contagem = contar_parentesco(linhas)
    assert contagem.titulares == 1
    assert contagem.dependentes == 0
    assert contagem.sem_parentesco == 1
    assert contagem.total == 2


@pytest.mark.parametrize(
    "linhas_spec",
    [
        [("TITULAR", ParentescoRascunho.TITULAR)] * 5,
        [
            ("TITULAR", ParentescoRascunho.TITULAR),
            ("CÔNJUGE", ParentescoRascunho.CONJUGE),
            ("FILHO(A)", ParentescoRascunho.FILHO),
            ("COMPANHEIRO", ParentescoRascunho.COMPANHEIRO),
            ("DESCONHECIDO", None),
        ],
    ],
)
def test_propriedade_soma_contadores_igual_total(linhas_spec):
    linhas = [
        _linha(
            id=f"l{i}",
            numero_linha=i + 1,
            parentesco_texto=txt,
            parentesco=par,
        )
        for i, (txt, par) in enumerate(linhas_spec)
    ]
    contagem = contar_parentesco(linhas)
    assert contagem.total == len(linhas)
