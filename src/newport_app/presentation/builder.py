"""Constrói PresentationViewModel a partir do comparativo congelado no snapshot."""

from __future__ import annotations

from datetime import datetime

from newport_app.cotacao_pdf.faixas import ROTULOS_FAIXA
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.presentation import (
    BeneficiarioApresentacao,
    BeneficiarioPropostaColuna,
    FaixaApresentacao,
    PaginaFaixasApresentacao,
    PlanoAtualApresentacao,
    PresentationViewModel,
    PropostaApresentacao,
    PropostaFaixaColuna,
    SecaoRegimeApresentacao,
    TotaisGeraisApresentacao,
    TotaisSecaoApresentacao,
)
from newport_app.models.responses import (
    ComparativoResponse,
    DetalheVidaComparativo,
    FaixaPlanoComparativo,
    PlanoAtualComparativo,
    ResultadoPropostaComparativo,
)
from newport_app.models.snapshot import SnapshotCalculo
from newport_app.presentation.formatacao import formatar_data_br
from newport_app.presentation.reajuste import (
    rotulo_reajuste_consolidado_dos_planos,
    rotulo_reajuste_exibicao,
)
from newport_app.presentation.rotulos import copart_descricao, qualificar_rotulos_propostas, rotulo_regime
from newport_app.snapshot.comparativo import ler_comparativo_congelado

MAX_PROPOSTAS_POR_PAGINA = 3
_ORDEM_REGIMES = ("sem", "parcial", "percentual")


def _percentual_tipico(rascunho: RascunhoEstudo, tipo: str) -> int | None:
    if tipo != "percentual":
        return None
    pcts = sorted(
        {
            r.percentual
            for r in rascunho.regimes_copart
            if r.tipo == "percentual" and r.percentual is not None
        }
    )
    if len(pcts) == 1:
        return pcts[0]
    return None


def _rotulo_regime(tipo: str, percentual: int | None = None) -> str:
    return rotulo_regime(tipo, percentual)


def _copart_descricao(rascunho: RascunhoEstudo, regime_id: str | None) -> str | None:
    return copart_descricao(rascunho, regime_id)


def _parentesco_eh_titular(parentesco: object) -> bool:
    valor = getattr(parentesco, "value", parentesco)
    return bool(valor and str(valor).lower() == "titular")


def _paginar_propostas(propostas_ids: list[str]) -> list[PaginaFaixasApresentacao]:
    paginas: list[PaginaFaixasApresentacao] = []
    for i in range(0, len(propostas_ids), MAX_PROPOSTAS_POR_PAGINA):
        paginas.append(
            PaginaFaixasApresentacao(
                indice=len(paginas),
                propostas_ids=propostas_ids[i : i + MAX_PROPOSTAS_POR_PAGINA],
            )
        )
    return paginas or [PaginaFaixasApresentacao(indice=0, propostas_ids=[])]


def _propostas_por_id(
    comparativo: ComparativoResponse,
) -> dict[str, ResultadoPropostaComparativo]:
    return {p.opcao_id: p for p in comparativo.propostas if p.calculo_realizado}


def _coletar_regimes(
    rascunho: RascunhoEstudo,
    propostas: list[ResultadoPropostaComparativo],
) -> list[tuple[str, str]]:
    encontrados: set[str] = {p.regime_tipo for p in propostas if p.regime_tipo}
    ordered = [
        (tipo, _rotulo_regime(tipo, _percentual_tipico(rascunho, tipo)))
        for tipo in _ORDEM_REGIMES
        if tipo in encontrados
    ]
    for tipo in encontrados:
        if tipo not in _ORDEM_REGIMES:
            ordered.append((tipo, _rotulo_regime(tipo)))
    if not ordered:
        ordered = [("sem", _rotulo_regime("sem"))]
    return ordered


def _vidas_unicas(
    propostas: list[ResultadoPropostaComparativo],
) -> dict[str, DetalheVidaComparativo]:
    vistos: dict[str, DetalheVidaComparativo] = {}
    for prop in propostas:
        for sec in prop.secoes:
            for vida in sec.vidas:
                if vida.vida_id not in vistos:
                    vistos[vida.vida_id] = vida
    return vistos


def _vidas_da_faixa(
    vidas: dict[str, DetalheVidaComparativo],
    faixa: int,
    subgrupo_id: str | None,
) -> list[DetalheVidaComparativo]:
    saida: list[DetalheVidaComparativo] = []
    for vida in vidas.values():
        if vida.faixa != faixa:
            continue
        if subgrupo_id and subgrupo_id != "vidas-incluidas" and vida.subgrupo_id != subgrupo_id:
            continue
        saida.append(vida)
    return saida


def _contar_parentesco(vidas_faixa: list[DetalheVidaComparativo]) -> tuple[int, int]:
    tit = sum(1 for v in vidas_faixa if _parentesco_eh_titular(v.parentesco))
    dep = len(vidas_faixa) - tit
    return tit, dep


def _mapear_faixa(
    fx: FaixaPlanoComparativo,
    propostas_ids: list[str],
    vidas: dict[str, DetalheVidaComparativo],
    subgrupo_id: str | None,
) -> FaixaApresentacao:
    vidas_fx = _vidas_da_faixa(vidas, fx.faixa, subgrupo_id)
    tit, dep = _contar_parentesco(vidas_fx)
    cols: list[PropostaFaixaColuna] = []
    for op_id in propostas_ids:
        col = next((c for c in fx.propostas if c.opcao_id == op_id), None)
        if col is None:
            cols.append(PropostaFaixaColuna(opcao_id=op_id, quantidade=0))
            continue
        cols.append(
            PropostaFaixaColuna(
                opcao_id=op_id,
                valor_unitario_centavos=col.unitario_centavos,
                quantidade=col.quantidade,
                subtotal_centavos=col.subtotal_centavos,
            )
        )
    return FaixaApresentacao(
        faixa=fx.faixa,
        rotulo=fx.rotulo,
        qtd_titulares=tit,
        qtd_dependentes=dep,
        qtd_total=fx.quantidade,
        atual_vigente_unitario_centavos=fx.vigente_unitario_centavos,
        atual_vigente_total_centavos=fx.vigente_total_centavos,
        atual_reajustado_unitario_centavos=fx.reajustado_unitario_centavos,
        atual_reajustado_total_centavos=fx.reajustado_total_centavos,
        observacao_valor=fx.observacao_valor,
        propostas=cols,
    )


def _mapear_plano(
    plano: PlanoAtualComparativo,
    rascunho: RascunhoEstudo,
    propostas_ids: list[str],
    vidas: dict[str, DetalheVidaComparativo],
) -> PlanoAtualApresentacao:
    sg = next((s for s in rascunho.subgrupos_atuais if s.id == plano.subgrupo_id), None)
    faixas = [
        _mapear_faixa(fx, propostas_ids, vidas, plano.subgrupo_id) for fx in plano.faixas
    ]
    return PlanoAtualApresentacao(
        subgrupo_id=plano.subgrupo_id,
        operadora=plano.operadora,
        plano_nome=plano.plano_nome,
        acomodacao=plano.acomodacao or (getattr(sg, "acomodacao", None) if sg else None),
        modalidade=None,
        copart_descricao=_copart_descricao(rascunho, sg.regime_copart_id if sg else None),
        faixas=faixas,
        subtotal_vigente_centavos=plano.vigente_centavos,
        subtotal_reajustado_centavos=plano.reajustado_centavos,
        reajuste_percentual_exibicao=rotulo_reajuste_exibicao(
            vigente_centavos=plano.vigente_centavos,
            reajustado_centavos=plano.reajustado_centavos,
            reajuste_bps_informado=sg.reajuste_bps if sg else None,
        ),
    )


def _montar_proposta_meta(
    rascunho: RascunhoEstudo,
    prop: ResultadoPropostaComparativo,
    regime_tipo: str,
    *,
    seguro_novo: bool,
) -> PropostaApresentacao:
    del seguro_novo  # diffs vêm do numerico em ambos os formatos
    op = next((o for o in rascunho.opcoes_proposta if o.id == prop.opcao_id), None)
    regime = None
    if op is not None:
        regime = next((r for r in rascunho.regimes_copart if r.id == op.regime_copart_id), None)
    pct_secao = regime.percentual if regime and regime.tipo == regime_tipo else None
    if pct_secao is None and regime_tipo == "percentual":
        pct_secao = _percentual_tipico(rascunho, regime_tipo)
    numerico = prop.numerico
    return PropostaApresentacao(
        opcao_id=prop.opcao_id,
        operadora=prop.operadora or (op.operadora if op else ""),
        plano_nome=prop.plano_nome,
        regime_rotulo=_rotulo_regime(regime_tipo, pct_secao),
        regime_tipo=regime_tipo,
        acomodacao=prop.acomodacao or (op.acomodacao if op else None),
        modalidade=op.modalidade.value if op and op.modalidade else None,
        copart_descricao=_copart_descricao(rascunho, op.regime_copart_id if op else None),
        validade=prop.validade_oficial or (formatar_data_br(op.validade_oficial) if op else None),
        premio_centavos=op.premio_saude.centavos if op and op.premio_saude else None,
        iof_centavos=op.iof.centavos if op and op.iof else None,
        total_recorrente_centavos=(
            op.total_recorrente.centavos if op and op.total_recorrente else None
        ),
        total_mensal_centavos=numerico.proposta_mensal_centavos if numerico else None,
        # Em seguro novo o numerico já traz diff vs a proposta mais barata.
        diff_mensal_centavos=numerico.diff_mes_centavos if numerico else None,
        diff_anual_centavos=numerico.diff_ano_centavos if numerico else None,
        diff_bps=numerico.diff_bps if numerico else None,
    )


def _total_atual_congelado(
    comparativo: ComparativoResponse,
    rascunho: RascunhoEstudo,
    *,
    seguro_novo: bool,
) -> int | None:
    if seguro_novo:
        return None
    baseline = "reajustado"
    escolhido = rascunho.escolhas.baseline_escolhido
    if escolhido and escolhido.valor == "vigente":
        baseline = "vigente"
    vals: list[int] = []
    for plano in comparativo.planos_atuais:
        centavos = plano.vigente_centavos if baseline == "vigente" else plano.reajustado_centavos
        if centavos is not None:
            vals.append(centavos)
    return sum(vals) if vals else None


def construir_view_model(
    snap: SnapshotCalculo,
    *,
    modo: str,
    propostas_selecionadas: list[str],
    ressalvas: list[str] | None = None,
    titulo: str | None = None,
    exibir_todas_faixas: bool = False,
    beneficiarios_agregados: bool = False,
    aprovado_em: datetime | None = None,
) -> PresentationViewModel:
    """Monta o ViewModel a partir do comparativo congelado.

    ``exibir_todas_faixas`` é ignorado: o payload congelado só traz faixas
    preenchidas, o mesmo recorte da matriz. O parâmetro permanece para não
    quebrar clientes antigos (default False).

    ``beneficiarios_agregados``: omite nomes reais (rótulo por faixa) — uso no
    documento cliente com três visões.

    ``aprovado_em``: data da revisão Newport (B-01). Sem aprovação viva a
    geração de HTML é recusada no serviço; testes unitários podem omitir.
    """
    del exibir_todas_faixas
    comparativo = ler_comparativo_congelado(snap.payload)
    rascunho = RascunhoEstudo.model_validate(snap.payload["rascunho"])
    por_id = _propostas_por_id(comparativo)
    propostas_ids = [op_id for op_id in propostas_selecionadas if op_id in por_id]
    propostas_sel = [por_id[op_id] for op_id in propostas_ids]
    vidas = _vidas_unicas(propostas_sel)
    seguro_novo = comparativo.formato == "novo" or rascunho.formato == "novo"
    data_revisao = formatar_data_br(aprovado_em) if aprovado_em is not None else ""
    vidas_calculadas = comparativo.beneficiarios_calculados or None
    qtd_planos = len(comparativo.planos_atuais) if not seguro_novo else None
    if qtd_planos == 0:
        qtd_planos = None
    regimes_ordem = _coletar_regimes(rascunho, propostas_sel)
    total_atual = _total_atual_congelado(comparativo, rascunho, seguro_novo=seguro_novo)

    secoes_vm: list[SecaoRegimeApresentacao] = []
    for regime_tipo, rotulo in regimes_ordem:
        propostas_regime = [p for p in propostas_sel if p.regime_tipo == regime_tipo]
        ids_regime = [p.opcao_id for p in propostas_regime]
        if not ids_regime:
            continue
        planos_vm: list[PlanoAtualApresentacao] = []
        if seguro_novo:
            faixas = [
                _mapear_faixa(fx, ids_regime, vidas, "vidas-incluidas")
                for fx in comparativo.faixas_estudo
            ]
            planos_vm.append(
                PlanoAtualApresentacao(
                    subgrupo_id="vidas-incluidas",
                    operadora="",
                    plano_nome="Beneficiários",
                    faixas=faixas,
                )
            )
        else:
            for plano in comparativo.planos_atuais:
                planos_vm.append(_mapear_plano(plano, rascunho, ids_regime, vidas))

        propostas_vm = [
            _montar_proposta_meta(rascunho, p, regime_tipo, seguro_novo=seguro_novo)
            for p in propostas_regime
        ]
        totais_sec = TotaisSecaoApresentacao(
            atual_centavos=None if seguro_novo else total_atual,
        )
        for p in propostas_regime:
            numerico = p.numerico
            totais_sec.propostas[p.opcao_id] = (
                numerico.proposta_mensal_centavos if numerico else None
            )
            if numerico:
                totais_sec.diff_mensal[p.opcao_id] = numerico.diff_mes_centavos
                totais_sec.diff_anual[p.opcao_id] = numerico.diff_ano_centavos

        secoes_vm.append(
            SecaoRegimeApresentacao(
                regime_rotulo=rotulo,
                regime_tipo=regime_tipo,
                propostas=propostas_vm,
                planos_atuais=planos_vm,
                totais=totais_sec,
                paginas_faixas=_paginar_propostas(ids_regime),
            )
        )

    beneficiarios: list[BeneficiarioApresentacao] = []
    if modo == "beneficiario":
        subgrupos_map = {s.id: s for s in rascunho.subgrupos_atuais}
        ordenadas = sorted(
            vidas.values(),
            key=lambda v: (
                v.plano_atual or "",
                v.nome or v.vida_id,
            ),
        )
        for dados in ordenadas:
            cols: list[BeneficiarioPropostaColuna] = []
            for op_id in propostas_ids:
                vd = None
                for sec in por_id[op_id].secoes:
                    vd = next((x for x in sec.vidas if x.vida_id == dados.vida_id), None)
                    if vd is not None:
                        break
                cols.append(
                    BeneficiarioPropostaColuna(
                        opcao_id=op_id,
                        valor_centavos=vd.proposta_centavos if vd else None,
                        diff_centavos=vd.diff_mes_centavos if vd else None,
                    )
                )
            sg = subgrupos_map.get(dados.subgrupo_id or "")
            faixa = dados.faixa
            faixa_rotulo = (
                dados.faixa_rotulo
                or (
                    ROTULOS_FAIXA[faixa]
                    if faixa is not None and 0 <= faixa < 10
                    else None
                )
            )
            if beneficiarios_agregados:
                rotulo_vida = f"Beneficiário · {faixa_rotulo or 'faixa não informada'}"
            else:
                rotulo_vida = dados.nome
            beneficiarios.append(
                BeneficiarioApresentacao(
                    vida_id=dados.vida_id,
                    nome=rotulo_vida,
                    idade=dados.idade,
                    faixa=faixa,
                    faixa_rotulo=faixa_rotulo,
                    parentesco=dados.parentesco,
                    plano_atual=dados.plano_atual or (sg.plano_nome if sg else None),
                    subgrupo_id=dados.subgrupo_id,
                    atual_vigente_centavos=dados.vigente_centavos,
                    atual_reajustado_centavos=dados.reajustado_centavos,
                    propostas=cols,
                )
            )

    totais_gerais = TotaisGeraisApresentacao(
        atual_centavos=total_atual,
        baseline_rotulo=(
            None
            if seguro_novo
            else (
                "Contrato reajustado"
                if rascunho.escolhas.baseline_escolhido.valor == "reajustado"
                else "Contrato vigente"
            )
        ),
    )
    for op_id in propostas_ids:
        numerico = por_id[op_id].numerico
        totais_gerais.propostas[op_id] = (
            numerico.proposta_mensal_centavos if numerico else None
        )
        if numerico:
            totais_gerais.diff_mensal[op_id] = numerico.diff_mes_centavos
            totais_gerais.diff_anual[op_id] = numerico.diff_ano_centavos

    todas_propostas = [p for secao in secoes_vm for p in secao.propostas]
    qualificar_rotulos_propostas(rascunho, todas_propostas)

    # Indicadores do resumo — após totais e rótulos; o renderer só itera.
    from newport_app.presentation.indicadores_resumo import montar_indicadores_resumo

    vm_parcial = PresentationViewModel(
        titulo=titulo or rascunho.titulo,
        data_apresentacao=data_revisao or "",
        estudo_id=snap.estudo_id,
        modo=modo,
        formato=rascunho.formato,
        propostas_selecionadas=propostas_ids,
        totais_gerais=totais_gerais,
        secoes_regime=secoes_vm,
    )
    for secao in secoes_vm:
        ids_secao = [p.opcao_id for p in secao.propostas]
        secao.indicadores_resumo = montar_indicadores_resumo(
            vm_parcial, secao, ids_secao
        )

    from newport_app.rascunho.acomodacao import coletar_divergencias_acomodacao

    nome_cliente = None
    if rascunho.empresa_cliente and (rascunho.empresa_cliente.nome or "").strip():
        nome_cliente = rascunho.empresa_cliente.nome.strip()

    return PresentationViewModel(
        titulo=titulo or rascunho.titulo,
        subtitulo=nome_cliente,
        data_apresentacao=data_revisao or "",
        estudo_id=snap.estudo_id,
        modo=modo,
        formato=rascunho.formato,
        propostas_selecionadas=propostas_ids,
        ressalvas=ressalvas or [],
        avisos_acomodacao=coletar_divergencias_acomodacao(rascunho),
        vidas_calculadas=vidas_calculadas,
        qtd_planos_vigentes=qtd_planos,
        totais_gerais=totais_gerais,
        secoes_regime=secoes_vm,
        beneficiarios=beneficiarios,
        reajuste_consolidado_percentual_exibicao=(
            None
            if seguro_novo
            else rotulo_reajuste_consolidado_dos_planos(comparativo.planos_atuais, rascunho)
        ),
    )
