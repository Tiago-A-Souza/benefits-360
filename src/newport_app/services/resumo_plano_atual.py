"""Resumo financeiro do plano atual derivado do SISCOR/vidas."""

from __future__ import annotations

from collections import defaultdict

from newport_app.agregacao_faixa import agregar_valores_faixa
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import (
    ResumoFaixaPlanoAtual,
    ResumoPlanoAtualItem,
    ResumoPlanoAtualResponse,
)
from newport_motor.faixa import faixa_em
from newport_motor.money import apply_rate_bps

_OBS_BASE = "Valores observados por fatura/vida — não substituem tabela oficial."


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


def _formatar_percentual_bps(bps: int | None) -> str | None:
    if bps is None:
        return None
    inteiro = bps // 100
    dec = abs(bps % 100)
    sinal = "-" if bps < 0 else ""
    return f"{sinal}{inteiro},{dec:02d}%"


def _montar_observacao(
    *,
    qtd_benef: int,
    vidas_com_valor: int,
    tem_faixas: bool,
) -> str | None:
    partes: list[str] = []
    sem_valor = qtd_benef - vidas_com_valor
    if sem_valor > 0:
        partes.append(f"{sem_valor} de {qtd_benef} beneficiários sem valor informado.")
    elif qtd_benef > 0 and vidas_com_valor == 0:
        partes.append("Nenhum beneficiário com valor informado.")
    if tem_faixas and vidas_com_valor > 0:
        partes.append(_OBS_BASE)
    if not partes:
        return None
    return " ".join(partes)


def _centavos_vida(vida) -> int | None:
    if vida.valor_fatura and vida.valor_fatura.centavos is not None:
        return vida.valor_fatura.centavos
    if vida.valor_conferencia and vida.valor_conferencia.centavos is not None:
        return vida.valor_conferencia.centavos
    return None


def montar_resumo_plano_atual(rascunho: RascunhoEstudo) -> ResumoPlanoAtualResponse:
    data_ref = rascunho.escolhas.data_referencia_idade
    baseline = rascunho.escolhas.baseline_escolhido.valor
    planos: list[ResumoPlanoAtualItem] = []
    total_vigente_geral = 0
    total_reajustado_geral = 0
    tem_reajuste_global = False

    for sg in rascunho.subgrupos_atuais:
        por_faixa: dict[int, list[int]] = defaultdict(list)
        vidas_por_faixa: dict[int, int] = defaultdict(int)
        qtd_benef = 0
        vidas_com_valor = 0
        centavos_vidas: list[int] = []
        for vida in rascunho.vidas_incluidas():
            if vida.subgrupo_atual_id != sg.id:
                continue
            qtd_benef += 1
            if data_ref is None:
                continue
            _, faixa = faixa_em(vida.nascimento, data_ref)
            vidas_por_faixa[faixa] += 1
            cent = _centavos_vida(vida)
            if cent is not None:
                por_faixa[faixa].append(cent)
                centavos_vidas.append(cent)
                vidas_com_valor += 1

        faixas_resumo: list[ResumoFaixaPlanoAtual] = []
        subtotal = 0
        for faixa in range(10):
            qtd = vidas_por_faixa.get(faixa, 0)
            if qtd == 0:
                continue
            valores = por_faixa.get(faixa, [])
            valor_obs, total_faixa, alerta = agregar_valores_faixa(valores)
            if total_faixa is not None:
                subtotal += total_faixa
            if len(valores) < qtd:
                falta = qtd - len(valores)
                aviso_faixa = (
                    f"{falta} de {qtd} vidas nesta faixa sem valor informado."
                )
                alerta = f"{alerta} {aviso_faixa}".strip() if alerta else aviso_faixa
            faixas_resumo.append(
                ResumoFaixaPlanoAtual(
                    faixa=faixa,
                    quantidade_vidas=qtd,
                    valor_observado_reais=_formatar_reais(valor_obs),
                    alerta_inconsistencia=alerta,
                )
            )

        vigente = subtotal if vidas_com_valor > 0 else None
        reajustado = None
        if vigente is not None and sg.reajuste_bps is not None:
            tem_reajuste_global = True
            reajustado = sum(
                apply_rate_bps(cent, sg.reajuste_bps) for cent in centavos_vidas
            )

        if baseline == "reajustado" and reajustado is not None:
            referencia_centavos = reajustado
            referencia_rotulo = "reajustada"
        else:
            referencia_centavos = vigente
            referencia_rotulo = "vigente"

        if vigente is not None:
            total_vigente_geral += vigente
        if reajustado is not None:
            total_reajustado_geral += reajustado

        planos.append(
            ResumoPlanoAtualItem(
                subgrupo_id=sg.id,
                operadora=sg.operadora,
                plano_nome=sg.plano_nome,
                quantidade_beneficiarios=qtd_benef,
                valor_mensal_vigente_centavos=vigente,
                valor_mensal_vigente_reais=_formatar_reais(vigente),
                reajuste_bps=sg.reajuste_bps,
                reajuste_percentual_exibicao=_formatar_percentual_bps(sg.reajuste_bps),
                valor_mensal_reajustado_centavos=reajustado,
                valor_mensal_reajustado_reais=_formatar_reais(reajustado),
                referencia_comparativo=referencia_rotulo,
                referencia_comparativo_centavos=referencia_centavos,
                referencia_comparativo_reais=_formatar_reais(referencia_centavos),
                faixas=faixas_resumo,
                subtotal_calculado_reais=_formatar_reais(vigente),
                observacao=_montar_observacao(
                    qtd_benef=qtd_benef,
                    vidas_com_valor=vidas_com_valor,
                    tem_faixas=bool(faixas_resumo),
                ),
            )
        )

    total_vigente = total_vigente_geral if total_vigente_geral else None
    total_reajustado = (
        total_reajustado_geral if tem_reajuste_global and total_reajustado_geral else None
    )

    return ResumoPlanoAtualResponse(
        planos=planos,
        total_vigente_centavos=total_vigente,
        total_vigente_reais=_formatar_reais(total_vigente),
        total_reajustado_centavos=total_reajustado,
        total_reajustado_reais=_formatar_reais(total_reajustado),
        total_calculado_reais=_formatar_reais(total_vigente),
        requer_data_referencia=data_ref is None,
    )
