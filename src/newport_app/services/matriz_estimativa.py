"""Matriz estimativa opção × plano vigente — reusa estimativa e resumo atuais."""

from __future__ import annotations

from newport_app.cotacao_pdf.estimativa import estimar_opcao_rascunho
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import (
    CelulaEstimativaSubgrupo,
    MatrizEstimativaResponse,
)
from newport_app.services.resumo_plano_atual import montar_resumo_plano_atual


def montar_matriz_estimativa(rascunho: RascunhoEstudo) -> MatrizEstimativaResponse:
    """Uma célula por opção do rascunho × plano vigente do resumo."""
    resumo = montar_resumo_plano_atual(rascunho)
    celulas: list[CelulaEstimativaSubgrupo] = []
    for opcao in rascunho.opcoes_proposta:
        for plano in resumo.planos:
            quantidades = {fx.faixa: fx.quantidade_vidas for fx in plano.faixas}
            estimado = estimar_opcao_rascunho(opcao, quantidades)
            referencia = plano.referencia_comparativo_centavos
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
