"""Resumo financeiro do plano atual derivado do SISCOR/vidas."""

from __future__ import annotations

from collections import defaultdict

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import (
    ResumoFaixaPlanoAtual,
    ResumoPlanoAtualItem,
    ResumoPlanoAtualResponse,
)
from newport_motor.faixa import faixa_em


def _formatar_reais(centavos: int | None) -> str | None:
    if centavos is None:
        return None
    neg = centavos < 0
    v = abs(centavos)
    reais = v // 100
    cents = v % 100
    sinal = "-" if neg else ""
    inteiro = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{cents:02d}"


def montar_resumo_plano_atual(rascunho: RascunhoEstudo) -> ResumoPlanoAtualResponse:
    data_ref = rascunho.escolhas.data_referencia_idade
    planos: list[ResumoPlanoAtualItem] = []
    total_geral = 0

    for sg in rascunho.subgrupos_atuais:
        por_faixa: dict[int, list[int]] = defaultdict(list)
        vidas_por_faixa: dict[int, int] = defaultdict(int)
        for vida in rascunho.vidas_incluidas():
            if vida.subgrupo_atual_id != sg.id:
                continue
            if data_ref is None:
                continue
            _, faixa = faixa_em(vida.nascimento, data_ref)
            vidas_por_faixa[faixa] += 1
            cent = None
            if vida.valor_fatura and vida.valor_fatura.centavos is not None:
                cent = vida.valor_fatura.centavos
            elif vida.valor_conferencia and vida.valor_conferencia.centavos is not None:
                cent = vida.valor_conferencia.centavos
            if cent is not None:
                por_faixa[faixa].append(cent)

        faixas_resumo: list[ResumoFaixaPlanoAtual] = []
        subtotal = 0
        for faixa in range(10):
            qtd = vidas_por_faixa.get(faixa, 0)
            if qtd == 0:
                continue
            valores = por_faixa.get(faixa, [])
            valor_obs = None
            alerta = None
            if valores:
                unicos = set(valores)
                if len(unicos) == 1:
                    valor_obs = valores[0]
                    subtotal += valor_obs * qtd
                else:
                    alerta = "Valores diferentes na mesma faixa — revise antes de usar como referência."
            faixas_resumo.append(
                ResumoFaixaPlanoAtual(
                    faixa=faixa,
                    quantidade_vidas=qtd,
                    valor_observado_reais=_formatar_reais(valor_obs),
                    alerta_inconsistencia=alerta,
                )
            )

        total_geral += subtotal
        planos.append(
            ResumoPlanoAtualItem(
                subgrupo_id=sg.id,
                operadora=sg.operadora,
                plano_nome=sg.plano_nome,
                faixas=faixas_resumo,
                subtotal_calculado_reais=_formatar_reais(subtotal if subtotal else None),
                observacao=(
                    "Valores observados por fatura/vida — não substituem tabela oficial."
                    if faixas_resumo
                    else None
                ),
            )
        )

    return ResumoPlanoAtualResponse(
        planos=planos,
        total_calculado_reais=_formatar_reais(total_geral if total_geral else None),
        requer_data_referencia=data_ref is None,
    )
