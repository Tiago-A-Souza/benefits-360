"""Colisão de chave de coluna — FASE 3, sobrevive à FASE 4.

A apresentação identifica coluna por `chave_de_coluna`. Hoje isso é `opcao_id`
(a primeira atribuição do cenário). Dois cenários que começam pelo mesmo plano
colidem, e `builder._propostas_por_id` perde uma coluna.

Este teste reproduz a colisão e exige o sinal. A asserção é bicondicional: se
a chave colapsa as colunas, o alerta existe; se a chave passa a ser única
(FASE 4: `cenario_id`), o alerta some. O teste fica verde nos dois lados.
"""

from __future__ import annotations

from newport_app.models.draft import AtribuicaoRascunho, CenarioRascunho
from newport_app.presentation.builder import _propostas_por_id
from newport_app.presentation.colisao_coluna import CODIGO_COLISAO_COLUNA
from tests.test_paridade_matriz_html import (
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
)


def test_colisao_de_chave_nao_e_silenciosa():
    """Dois cenários começando pelo mesmo plano: a matriz guarda os dois.

    Se a apresentação colapsar as colunas numa chave só, tem de haver alerta.
    Se não colapsar (FASE 4), o alerta não pode existir — senão ficaria mentindo.
    """
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    rascunho.cenarios = [
        CenarioRascunho(
            id="c-uniforme-prata",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a1a", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-prata"
                ),
                AtribuicaoRascunho(
                    id="a1b", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-prata"
                ),
            ],
        ),
        CenarioRascunho(
            id="c-misto-prata-ouro",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a2a", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-prata"
                ),
                AtribuicaoRascunho(
                    id="a2b", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-ouro"
                ),
            ],
        ),
    ]

    matriz, _ = _calcular_matriz(rascunho)
    calculadas = [p for p in matriz.propostas if p.calculo_realizado]
    assert len(calculadas) == 2
    assert {p.cenario_id for p in calculadas} == {
        "c-uniforme-prata",
        "c-misto-prata-ouro",
    }

    colapsadas = _propostas_por_id(matriz)
    sinais = [p for p in matriz.pendencias if p.codigo == CODIGO_COLISAO_COLUNA]

    if len(colapsadas) < len(calculadas):
        assert len(sinais) == 1
        alerta = sinais[0]
        assert alerta.tipo == "alerta"
        assert alerta.etapa == 5
        assert "documento" in alerta.descricao.lower()
        # Nomeia os dois; não escolhe um nem descarta o outro.
        assert "Proposta prata" in alerta.descricao
        assert "Proposta ouro" in alerta.descricao
        # Não é bloqueio: a matriz continua com as duas colunas.
        assert alerta.tipo != "bloqueio"
    else:
        assert sinais == []


def test_sem_colisao_nao_inventa_alerta():
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    rascunho.cenarios = [
        CenarioRascunho(
            id="c-prata",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a1a", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-prata"
                ),
                AtribuicaoRascunho(
                    id="a1b", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-prata"
                ),
            ],
        ),
        CenarioRascunho(
            id="c-ouro",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a2a", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-ouro"
                ),
                AtribuicaoRascunho(
                    id="a2b", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-ouro"
                ),
            ],
        ),
    ]
    matriz, _ = _calcular_matriz(rascunho)
    assert len(matriz.propostas) == 2
    assert {p.opcao_id for p in matriz.propostas} == {"op-prata", "op-ouro"}
    assert not any(p.codigo == CODIGO_COLISAO_COLUNA for p in matriz.pendencias)
    assert len(_propostas_por_id(matriz)) == 2
