"""Constrói PresentationViewModel a partir de snapshot aprovado — ETAPA 2.8.2."""

from __future__ import annotations

from datetime import datetime, timezone

from newport_app.agregacao_faixa import agregar_valores_faixa
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
from newport_app.models.snapshot import SnapshotCalculo
from newport_app.presentation.formatacao import formatar_data_br
from newport_app.presentation.rotulos import copart_descricao, qualificar_rotulos_propostas, rotulo_regime
from newport_app.presentation.motor_por_proposta import (
    CalculoProposta,
    VidaCalculoProposta,
    calcular_atual_do_snapshot,
    calcular_propostas_do_snapshot,
)

MAX_PROPOSTAS_POR_PAGINA = 3
_ORDEM_REGIMES = ("sem", "parcial", "percentual", "customizada")


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


def _coletar_regimes_apresentacao(
    rascunho: RascunhoEstudo,
    calculo_atual: CalculoProposta,
    calculos: dict[str, CalculoProposta],
    propostas_ids: list[str],
) -> list[tuple[str, str]]:
    encontrados: set[str] = set()
    for sec in calculo_atual.secoes:
        encontrados.add(sec.regime_tipo)
    for op_id in propostas_ids:
        calc = calculos.get(op_id)
        if calc is None:
            continue
        for sec in calc.secoes:
            encontrados.add(sec.regime_tipo)
    return [
        (tipo, _rotulo_regime(tipo, _percentual_tipico(rascunho, tipo)))
        for tipo in _ORDEM_REGIMES
        if tipo in encontrados
    ]


def _faixa_com_conteudo(fx: FaixaApresentacao) -> bool:
    if fx.qtd_total > 0:
        return True
    if fx.atual_vigente_total_centavos or fx.atual_reajustado_total_centavos:
        return True
    return any(
        (col.quantidade or 0) > 0 or col.valor_unitario_centavos is not None
        for col in fx.propostas
    )


def _propostas_do_regime(
    propostas_ids: list[str],
    calculos: dict[str, CalculoProposta],
    regime_tipo: str,
) -> list[str]:
    return [
        op_id
        for op_id in propostas_ids
        if any(s.regime_tipo == regime_tipo for s in calculos[op_id].secoes)
    ]


def _parentesco_eh_titular(vida: object) -> bool:
    parentesco = getattr(vida, "parentesco", None)
    return bool(parentesco and getattr(parentesco, "value", parentesco) == "titular")


def _dados_vida_proposta(
    vida_id: str,
    calculos_proposta: dict[str, CalculoProposta],
    propostas_ids: list[str],
    regime_tipo: str,
) -> VidaCalculoProposta | None:
    for op_id in propostas_ids:
        calc = calculos_proposta.get(op_id)
        if calc is None:
            continue
        for sec in calc.secoes:
            if sec.regime_tipo != regime_tipo:
                continue
            if vida_id in sec.vidas:
                return sec.vidas[vida_id]
    return None


def _finalizar_faixas(
    faixas: dict[int, FaixaApresentacao],
    vigentes_por_faixa: dict[int, list[int]],
    reajustados_por_faixa: dict[int, list[int]],
    proposta_vals: dict[int, dict[str, list[int]]],
    propostas_ids: list[str],
    *,
    exibir_todas_faixas: bool,
    incluir_atual: bool,
) -> list[FaixaApresentacao]:
    for fx in range(10):
        ag = faixas[fx]
        if incluir_atual:
            unit_v, tot_v, obs_v = agregar_valores_faixa(vigentes_por_faixa[fx])
            unit_r, tot_r, obs_r = agregar_valores_faixa(reajustados_por_faixa[fx])
            ag.atual_vigente_unitario_centavos = unit_v
            ag.atual_vigente_total_centavos = tot_v
            ag.atual_reajustado_unitario_centavos = unit_r
            ag.atual_reajustado_total_centavos = tot_r
            ag.observacao_valor = obs_v or obs_r
        for op_id in propostas_ids:
            unit_p, sub_p, _ = agregar_valores_faixa(proposta_vals[fx][op_id])
            ag.propostas.append(
                PropostaFaixaColuna(
                    opcao_id=op_id,
                    valor_unitario_centavos=unit_p,
                    quantidade=len(proposta_vals[fx][op_id]),
                    subtotal_centavos=sub_p,
                )
            )
    lista = [faixas[i] for i in range(10)]
    if exibir_todas_faixas:
        return lista
    filtradas = [fx for fx in lista if _faixa_com_conteudo(fx)]
    return filtradas or lista


def _montar_faixas_plano(
    subgrupo_id: str,
    vidas_rascunho: dict[str, object],
    atual_por_vida: dict[str, VidaCalculoProposta],
    calculos_proposta: dict[str, CalculoProposta],
    propostas_ids: list[str],
    regime_tipo: str,
    *,
    exibir_todas_faixas: bool = False,
) -> list[FaixaApresentacao]:
    faixas: dict[int, FaixaApresentacao] = {
        i: FaixaApresentacao(faixa=i, rotulo=ROTULOS_FAIXA[i]) for i in range(10)
    }
    vigentes_por_faixa: dict[int, list[int]] = {i: [] for i in range(10)}
    reajustados_por_faixa: dict[int, list[int]] = {i: [] for i in range(10)}
    proposta_vals: dict[int, dict[str, list[int]]] = {
        i: {op: [] for op in propostas_ids} for i in range(10)
    }

    for vida_id, dados in atual_por_vida.items():
        if dados.subgrupo_id != subgrupo_id:
            continue
        fx = dados.faixa
        if fx is None or fx < 0 or fx > 9:
            continue
        vida = vidas_rascunho.get(vida_id)
        ag = faixas[fx]
        ag.qtd_total += 1
        if vida is not None and _parentesco_eh_titular(vida):
            ag.qtd_titulares += 1
        else:
            ag.qtd_dependentes += 1
        if dados.vigente_centavos is not None:
            vigentes_por_faixa[fx].append(dados.vigente_centavos)
        if dados.reajustado_centavos is not None:
            reajustados_por_faixa[fx].append(dados.reajustado_centavos)
        for op_id in propostas_ids:
            calc = calculos_proposta.get(op_id)
            if calc is None:
                continue
            for sec in calc.secoes:
                if sec.regime_tipo != regime_tipo:
                    continue
                vd = sec.vidas.get(vida_id)
                if vd and vd.proposta_centavos is not None:
                    proposta_vals[fx][op_id].append(vd.proposta_centavos)

    return _finalizar_faixas(
        faixas,
        vigentes_por_faixa,
        reajustados_por_faixa,
        proposta_vals,
        propostas_ids,
        exibir_todas_faixas=exibir_todas_faixas,
        incluir_atual=True,
    )


def _montar_faixas_seguro_novo(
    vidas_rascunho: dict[str, object],
    calculos_proposta: dict[str, CalculoProposta],
    propostas_ids: list[str],
    regime_tipo: str,
    *,
    exibir_todas_faixas: bool = False,
) -> list[FaixaApresentacao]:
    """Agrupa vidas incluídas por faixa etária — sem plano vigente."""
    faixas: dict[int, FaixaApresentacao] = {
        i: FaixaApresentacao(faixa=i, rotulo=ROTULOS_FAIXA[i]) for i in range(10)
    }
    vigentes_por_faixa: dict[int, list[int]] = {i: [] for i in range(10)}
    reajustados_por_faixa: dict[int, list[int]] = {i: [] for i in range(10)}
    proposta_vals: dict[int, dict[str, list[int]]] = {
        i: {op: [] for op in propostas_ids} for i in range(10)
    }

    for vida_id, vida in vidas_rascunho.items():
        dados = _dados_vida_proposta(vida_id, calculos_proposta, propostas_ids, regime_tipo)
        if dados is None or dados.faixa is None or dados.faixa < 0 or dados.faixa > 9:
            continue
        fx = dados.faixa
        ag = faixas[fx]
        ag.qtd_total += 1
        if _parentesco_eh_titular(vida):
            ag.qtd_titulares += 1
        else:
            ag.qtd_dependentes += 1
        for op_id in propostas_ids:
            calc = calculos_proposta.get(op_id)
            if calc is None:
                continue
            for sec in calc.secoes:
                if sec.regime_tipo != regime_tipo:
                    continue
                vd = sec.vidas.get(vida_id)
                if vd and vd.proposta_centavos is not None:
                    proposta_vals[fx][op_id].append(vd.proposta_centavos)

    return _finalizar_faixas(
        faixas,
        vigentes_por_faixa,
        reajustados_por_faixa,
        proposta_vals,
        propostas_ids,
        exibir_todas_faixas=exibir_todas_faixas,
        incluir_atual=False,
    )


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


def _montar_proposta_meta(
    rascunho: RascunhoEstudo,
    op_id: str,
    calc: CalculoProposta,
    regime_tipo: str,
) -> PropostaApresentacao | None:
    op = next((o for o in rascunho.opcoes_proposta if o.id == op_id), None)
    if op is None:
        return None
    secao = next((s for s in calc.secoes if s.regime_tipo == regime_tipo), None)
    regime = next((r for r in rascunho.regimes_copart if r.id == op.regime_copart_id), None)
    pct_secao = regime.percentual if regime and regime.tipo == regime_tipo else None
    if pct_secao is None and regime_tipo == "percentual":
        pct_secao = _percentual_tipico(rascunho, regime_tipo)
    return PropostaApresentacao(
        opcao_id=op.id,
        operadora=op.operadora,
        plano_nome=op.plano_nome,
        regime_rotulo=_rotulo_regime(regime_tipo, pct_secao),
        regime_tipo=regime_tipo,
        acomodacao=op.acomodacao,
        modalidade=op.modalidade.value if op.modalidade else None,
        copart_descricao=_copart_descricao(rascunho, op.regime_copart_id),
        validade=formatar_data_br(op.validade_oficial),
        premio_centavos=op.premio_saude.centavos if op.premio_saude else None,
        iof_centavos=op.iof.centavos if op.iof else None,
        total_recorrente_centavos=(
            op.total_recorrente.centavos if op.total_recorrente else None
        ),
        total_mensal_centavos=secao.total_proposta_centavos if secao else None,
        diff_mensal_centavos=secao.diff_mes_centavos if secao else None,
        diff_anual_centavos=secao.diff_ano_centavos if secao else None,
    )


def construir_view_model(
    snap: SnapshotCalculo,
    *,
    modo: str,
    propostas_selecionadas: list[str],
    ressalvas: list[str] | None = None,
    titulo: str | None = None,
    exibir_todas_faixas: bool = False,
) -> PresentationViewModel:
    rascunho = RascunhoEstudo.model_validate(snap.payload["rascunho"])
    calculo_atual = calcular_atual_do_snapshot(snap)
    calculos = calcular_propostas_do_snapshot(snap, propostas_selecionadas)

    vidas_map = {v.id: v for v in rascunho.vidas if v.incluida}
    subgrupos_map = {s.id: s for s in rascunho.subgrupos_atuais}

    atual_por_vida: dict[str, VidaCalculoProposta] = {}
    for sec in calculo_atual.secoes:
        atual_por_vida.update(sec.vidas)

    regimes_ordem = _coletar_regimes_apresentacao(
        rascunho, calculo_atual, calculos, propostas_selecionadas
    )

    seguro_novo = rascunho.formato == "novo"

    secoes_vm: list[SecaoRegimeApresentacao] = []
    for regime_tipo, rotulo in regimes_ordem:
        propostas_regime = _propostas_do_regime(
            propostas_selecionadas, calculos, regime_tipo
        )
        planos_vm: list[PlanoAtualApresentacao] = []
        if seguro_novo:
            faixas = _montar_faixas_seguro_novo(
                vidas_map,
                calculos,
                propostas_regime,
                regime_tipo,
                exibir_todas_faixas=exibir_todas_faixas,
            )
            planos_vm.append(
                PlanoAtualApresentacao(
                    subgrupo_id="vidas-incluidas",
                    operadora="",
                    plano_nome="Beneficiários",
                    faixas=faixas,
                )
            )
        else:
            for sg in rascunho.subgrupos_atuais:
                faixas = _montar_faixas_plano(
                    sg.id,
                    vidas_map,
                    atual_por_vida,
                    calculos,
                    propostas_regime,
                    regime_tipo,
                    exibir_todas_faixas=exibir_todas_faixas,
                )
                vigentes = [
                    d.vigente_centavos
                    for d in atual_por_vida.values()
                    if d.subgrupo_id == sg.id and d.vigente_centavos is not None
                ]
                reajustados = [
                    d.reajustado_centavos
                    for d in atual_por_vida.values()
                    if d.subgrupo_id == sg.id and d.reajustado_centavos is not None
                ]
                planos_vm.append(
                    PlanoAtualApresentacao(
                        subgrupo_id=sg.id,
                        operadora=sg.operadora,
                        plano_nome=sg.plano_nome,
                        acomodacao=getattr(sg, "acomodacao", None),
                        modalidade=None,
                        copart_descricao=_copart_descricao(rascunho, sg.regime_copart_id),
                        faixas=faixas,
                        subtotal_vigente_centavos=sum(vigentes) if vigentes else None,
                        subtotal_reajustado_centavos=sum(reajustados) if reajustados else None,
                    )
                )

        propostas_vm = [
            p
            for op_id in propostas_regime
            if (p := _montar_proposta_meta(rascunho, op_id, calculos[op_id], regime_tipo))
        ]
        if seguro_novo:
            for prop in propostas_vm:
                prop.diff_mensal_centavos = None
                prop.diff_anual_centavos = None

        totais_sec = TotaisSecaoApresentacao(
            atual_centavos=None if seguro_novo else calculo_atual.total_atual_centavos,
        )
        for op_id in propostas_regime:
            sec_calc = next(
                (s for s in calculos[op_id].secoes if s.regime_tipo == regime_tipo),
                None,
            )
            totais_sec.propostas[op_id] = (
                sec_calc.total_proposta_centavos if sec_calc else None
            )
            if not seguro_novo:
                totais_sec.diff_mensal[op_id] = (
                    sec_calc.diff_mes_centavos if sec_calc else None
                )
                totais_sec.diff_anual[op_id] = (
                    sec_calc.diff_ano_centavos if sec_calc else None
                )

        secoes_vm.append(
            SecaoRegimeApresentacao(
                regime_rotulo=rotulo,
                regime_tipo=regime_tipo,
                propostas=propostas_vm,
                planos_atuais=planos_vm,
                totais=totais_sec,
                paginas_faixas=_paginar_propostas(propostas_regime),
            )
        )

    beneficiarios: list[BeneficiarioApresentacao] = []
    if modo == "beneficiario":
        vistos: set[str] = set()
        for vida_id, dados in sorted(
            atual_por_vida.items(),
            key=lambda x: (x[1].regime_tipo, vidas_map.get(x[0]).nome if x[0] in vidas_map else x[0]),
        ):
            if vida_id in vistos:
                continue
            vistos.add(vida_id)
            vida = vidas_map.get(vida_id)
            if vida is None:
                continue
            cols: list[BeneficiarioPropostaColuna] = []
            for op_id in propostas_selecionadas:
                vd = None
                for sec in calculos[op_id].secoes:
                    if vida_id in sec.vidas:
                        vd = sec.vidas[vida_id]
                        break
                cols.append(
                    BeneficiarioPropostaColuna(
                        opcao_id=op_id,
                        valor_centavos=vd.proposta_centavos if vd else None,
                        diff_centavos=vd.diff_mes_centavos if vd else None,
                    )
                )
            sg = subgrupos_map.get(dados.subgrupo_id)
            beneficiarios.append(
                BeneficiarioApresentacao(
                    vida_id=vida_id,
                    nome=vida.nome,
                    idade=dados.idade,
                    faixa=dados.faixa,
                    faixa_rotulo=(
                        ROTULOS_FAIXA[dados.faixa]
                        if dados.faixa is not None and 0 <= dados.faixa < 10
                        else None
                    ),
                    parentesco=vida.parentesco.value if vida.parentesco else None,
                    plano_atual=sg.plano_nome if sg else None,
                    subgrupo_id=dados.subgrupo_id,
                    atual_vigente_centavos=dados.vigente_centavos,
                    atual_reajustado_centavos=dados.reajustado_centavos,
                    propostas=cols,
                )
            )

    totais_gerais = TotaisGeraisApresentacao(
        atual_centavos=None if seguro_novo else calculo_atual.total_atual_centavos,
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
    for op_id in propostas_selecionadas:
        calc = calculos[op_id]
        totais_gerais.propostas[op_id] = calc.total_proposta_centavos
        if not seguro_novo:
            totais_gerais.diff_mensal[op_id] = calc.diff_mes_centavos
            totais_gerais.diff_anual[op_id] = calc.diff_ano_centavos

    todas_propostas = [p for secao in secoes_vm for p in secao.propostas]
    qualificar_rotulos_propostas(rascunho, todas_propostas)

    from newport_app.rascunho.acomodacao import coletar_divergencias_acomodacao

    return PresentationViewModel(
        titulo=titulo or rascunho.titulo,
        subtitulo=rascunho.empresa_cliente.nome if rascunho.empresa_cliente else None,
        data_apresentacao=datetime.now(timezone.utc).strftime("%d/%m/%Y"),
        estudo_id=snap.estudo_id,
        modo=modo,
        formato=rascunho.formato,
        propostas_selecionadas=propostas_selecionadas,
        ressalvas=ressalvas or [],
        avisos_acomodacao=coletar_divergencias_acomodacao(rascunho),
        totais_gerais=totais_gerais,
        secoes_regime=secoes_vm,
        beneficiarios=beneficiarios,
    )
