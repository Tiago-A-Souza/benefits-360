"""Matriz estimativa opção × plano vigente — reusa estimativa e resumo atuais."""

from __future__ import annotations

from newport_app.cotacao_pdf.estimativa import estimar_opcao_rascunho
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import (
    CelulaEstimativaSubgrupo,
    MatrizEstimativaResponse,
)
from newport_app.rascunho.selecao_grupo import opcoes_do_subgrupo
from newport_app.services.resumo_plano_atual import montar_resumo_plano_atual


def montar_matriz_estimativa(
    rascunho: RascunhoEstudo,
    *,
    restrita: bool = True,
) -> MatrizEstimativaResponse:
    """Uma célula por par que interessa: plano vigente × cotação escolhida para ele.

    Restrita é o padrão porque calcular o valor de um plano para um grupo que não
    vai recebê-lo produz justamente o número que a comparação por grupo existe
    para eliminar. Grupo sem seleção própria herda o catálogo, então nele a
    restrição não tira nada.

    `restrita=False` serve à tela de seleção da etapa 3, onde o operador ainda
    está decidindo e precisa ver o valor de cada plano em cada grupo.
    """
    resumo = montar_resumo_plano_atual(rascunho)
    por_id = {op.id: op for op in rascunho.opcoes_proposta}
    celulas: list[CelulaEstimativaSubgrupo] = []

    for plano in resumo.planos:
        if restrita:
            ids = opcoes_do_subgrupo(rascunho, plano.subgrupo_id)
        else:
            ids = [op.id for op in rascunho.opcoes_proposta]
        quantidades = {fx.faixa: fx.quantidade_vidas for fx in plano.faixas}
        referencia = plano.referencia_comparativo_centavos
        for opcao_id in ids:
            opcao = por_id.get(opcao_id)
            if opcao is None:
                continue
            estimado = estimar_opcao_rascunho(opcao, quantidades)
            diff = None
            if estimado is not None and referencia:
                diff = estimado - referencia
            celulas.append(
                CelulaEstimativaSubgrupo(
                    opcao_id=opcao.id,
                    subgrupo_id=plano.subgrupo_id,
                    estimado_centavos=estimado,
                    diff_centavos=diff,
                )
            )

    return MatrizEstimativaResponse(celulas=celulas)
