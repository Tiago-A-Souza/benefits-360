"""Colisão de chave de coluna — dois cenários que começam pelo mesmo plano.

Desde a FASE 3 a coluna da matriz é um cenário, mas a camada de apresentação
ainda identifica coluna por `opcao_id`, e o `opcao_id` de uma coluna é a opção
da **primeira atribuição** do cenário (`opcao_referencia_cenario`). Quando dois
cenários começam pelo mesmo plano, as duas colunas saem com a mesma chave, e o
`{p.opcao_id: p for p in ...}` de `builder.py` mantém uma e perde a outra.

A matriz aguenta — as colunas são uma lista. Quem perde é o documento.

A correção definitiva é `coluna_id` = cenário, prevista para a FASE 4, que já
reescreve esses mesmos pontos para pôr o resumo executivo por cenário. Até lá o
caso é **detectado e sinalizado**: uma coluna não pode desaparecer em silêncio.

Alerta, não bloqueio: a matriz continua correta e três estudos já gravados
cairiam em bloqueio novo, o que esta fase não permite. O operador precisa saber
que o documento sairá com uma coluna a menos — não ser impedido de trabalhar.
"""

from __future__ import annotations

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import PendenciaItem, ResultadoPropostaComparativo

CODIGO_COLISAO_COLUNA = "APP-COL-001"


def chave_de_coluna(prop: ResultadoPropostaComparativo) -> str:
    """Identificador que a apresentação usa para achar a coluna.

    Hoje é `opcao_id` — a opção de referência do cenário, a primeira atribuição.
    Na FASE 4 passa a ser `cenario_id`. Quem colapsa as colunas
    (`builder._propostas_por_id`) e quem detecta a colisão leem daqui, para o
    sinal desaparecer no mesmo commit que a causa.
    """
    return prop.opcao_id


def colisoes_de_chave_de_coluna(
    propostas: list[ResultadoPropostaComparativo],
) -> dict[str, list[str]]:
    """chave de coluna repetida → ids dos cenários que a compartilham, em ordem."""
    por_chave: dict[str, list[str]] = {}
    for prop in propostas:
        if not prop.calculo_realizado:
            continue
        por_chave.setdefault(chave_de_coluna(prop), []).append(prop.cenario_id)
    return {chave: cens for chave, cens in por_chave.items() if len(cens) > 1}


def pendencias_colisao_de_coluna(
    rascunho: RascunhoEstudo,
    propostas: list[ResultadoPropostaComparativo],
) -> list[PendenciaItem]:
    colisoes = colisoes_de_chave_de_coluna(propostas)
    if not colisoes:
        return []

    rotulos = {p.cenario_id: p.plano_nome for p in propostas}
    nomes_opcao = {op.id: (op.plano_nome or op.id) for op in rascunho.opcoes_proposta}

    partes: list[str] = []
    for chave, cenarios in colisoes.items():
        nomes = [f"«{rotulos.get(c, c)}»" for c in cenarios]
        envolvidos = (
            " e ".join(nomes)
            if len(nomes) == 2
            else ", ".join(nomes[:-1]) + " e " + nomes[-1]
        )
        partes.append(
            f"Os cenários {envolvidos} começam pelo mesmo plano "
            f"«{nomes_opcao.get(chave, chave)}»"
        )

    quantidade = sum(len(c) for c in colisoes.values())
    return [
        PendenciaItem(
            tipo="alerta",
            titulo=(
                "Cenários que compartilham o primeiro plano"
                if len(colisoes) == 1
                else f"{len(colisoes)} planos iniciais repetidos entre cenários"
            ),
            descricao=(
                " · ".join(partes)
                + ". A comparação na tela está completa, mas o documento gerado "
                "mostrará apenas uma dessas colunas."
            ),
            acao_sugerida=(
                "Para ter as duas colunas no documento, reordene as atribuições de "
                "um dos cenários para que comecem por planos diferentes, ou gere um "
                "documento por cenário."
            ),
            codigo=CODIGO_COLISAO_COLUNA,
            etapa=5,
            quantidade=quantidade,
        )
    ]
