"""Mapeamento RascunhoEstudo → EstudoInput + EffectivePolicy."""

from __future__ import annotations

from newport_app.models.compilation import ErroCompilacao
from newport_app.models.draft import (
    ComponenteFinanceiroRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
    RascunhoEstudo,
    TabelaFaixaRascunho,
)
from newport_app.policy.registry import PolicySet
from newport_motor.models import (
    AtribuicaoPlano,
    Cenario,
    CustoUnico,
    EstudoInput,
    OpcaoPlano,
    RegimeCopart,
    SubgrupoAtual,
    TabelaPrecoFaixa,
    Vida,
)
from newport_motor.policy import EffectivePolicy
from newport_motor.provenance import ComponenteFinanceiro, ProvenienciaCampo
from newport_motor.types import (
    AlvoTipo,
    BaselineEscolhido,
    FormatoEstudo,
    OrigemValor,
    PrecedenciaAtualVida,
    PriceBasis,
    RegimeCopartTipo,
    TipoFiscal,
)


def _erro(codigo: str, caminho: str, mensagem: str) -> ErroCompilacao:
    return ErroCompilacao(
        codigo=codigo,
        caminho=caminho,
        mensagem=mensagem,
        severidade="bloqueante",
    )


def mapear_price_basis(
    basis: PriceBasisRascunho,
    tipo_fiscal: str,
    caminho: str,
) -> PriceBasis | ErroCompilacao:
    if basis == PriceBasisRascunho.NAO_APLICA:
        if tipo_fiscal != "operadora":
            return _erro(
                "APP-BAS-001",
                caminho,
                "A opção 'não se aplica' só é permitida para operadoras sem IOF.",
            )
        return PriceBasis.EXCLUI_IOF
    if basis == PriceBasisRascunho.INCLUI_IOF:
        return PriceBasis.INCLUI_IOF
    if basis == PriceBasisRascunho.EXCLUI_IOF:
        return PriceBasis.EXCLUI_IOF
    return PriceBasis.DESCONHECIDO


def _proveniencia_motor(prov: ProvenienciaRascunho) -> ProvenienciaCampo:
    return ProvenienciaCampo(
        origem=OrigemValor(prov.origem.value),
        documento_id=prov.documento_id,
        extrator_versao=prov.extrator_versao,
        confirmado=prov.confirmado,
    )


def _componente_motor(
    comp: ComponenteFinanceiroRascunho | None,
    tipo_fiscal: str,
    caminho: str,
    erros: list[ErroCompilacao],
) -> ComponenteFinanceiro | None:
    if comp is None:
        return None
    basis = mapear_price_basis(comp.price_basis, tipo_fiscal, caminho)
    if isinstance(basis, ErroCompilacao):
        erros.append(basis)
        return None
    return ComponenteFinanceiro(
        centavos=comp.centavos,
        price_basis=basis,
        proveniencia=_proveniencia_motor(comp.proveniencia),
    )


def _tabela_faixa_motor(
    faixa: TabelaFaixaRascunho,
    tipo_fiscal: str,
    caminho: str,
    erros: list[ErroCompilacao],
) -> TabelaPrecoFaixa | None:
    basis = mapear_price_basis(faixa.price_basis, tipo_fiscal, caminho)
    if isinstance(basis, ErroCompilacao):
        erros.append(basis)
        return None
    return TabelaPrecoFaixa(
        faixa=faixa.faixa,
        valor_centavos=faixa.valor_centavos,
        quantidade_cotada=faixa.quantidade_cotada,
        price_basis=basis,
        proveniencia=_proveniencia_motor(faixa.proveniencia),
    )


def mapear_estudo_input(
    rascunho: RascunhoEstudo,
) -> tuple[EstudoInput | None, list[ErroCompilacao]]:
    erros: list[ErroCompilacao] = []

    vidas: list[Vida] = []
    for idx, v in enumerate(rascunho.vidas):
        fatura_basis: PriceBasis | None = None
        if v.valor_fatura is not None:
            sg_tipo = "seguradora"
            if v.subgrupo_atual_id:
                sg = next(
                    (s for s in rascunho.subgrupos_atuais if s.id == v.subgrupo_atual_id),
                    None,
                )
                if sg is not None:
                    sg_tipo = sg.tipo_fiscal
            mapped = mapear_price_basis(
                v.valor_fatura.price_basis,
                sg_tipo,
                f"/vidas/{idx}/valor_fatura/price_basis",
            )
            if isinstance(mapped, ErroCompilacao):
                erros.append(mapped)
                continue
            fatura_basis = mapped
        vidas.append(
            Vida(
                id=v.id,
                nome=v.nome,
                nascimento=v.nascimento,
                incluida=v.incluida,
                subgrupo_atual_id=v.subgrupo_atual_id,
                valor_fatura_centavos=(
                    v.valor_fatura.centavos if v.valor_fatura else None
                ),
                fatura_price_basis=fatura_basis,
                fatura_proveniencia=(
                    _proveniencia_motor(v.valor_fatura.proveniencia)
                    if v.valor_fatura
                    else None
                ),
            )
        )

    subgrupos: list[SubgrupoAtual] = []
    for idx, sg in enumerate(rascunho.subgrupos_atuais):
        basis = mapear_price_basis(
            sg.fatura_price_basis,
            sg.tipo_fiscal,
            f"/subgrupos_atuais/{idx}/fatura_price_basis",
        )
        if isinstance(basis, ErroCompilacao):
            erros.append(basis)
            continue
        tabela: list[TabelaPrecoFaixa] = []
        for f_idx, faixa in enumerate(sg.tabela_atual):
            item = _tabela_faixa_motor(
                faixa,
                sg.tipo_fiscal,
                f"/subgrupos_atuais/{idx}/tabela_atual/{f_idx}/price_basis",
                erros,
            )
            if item is not None:
                tabela.append(item)
        subgrupos.append(
            SubgrupoAtual(
                id=sg.id,
                operadora=sg.operadora,
                tipo_fiscal=TipoFiscal(sg.tipo_fiscal),
                plano_nome=sg.plano_nome,
                regime_copart_id=sg.regime_copart_id,
                reajuste_bps=sg.reajuste_bps,
                fatura_price_basis=basis,
                subtotal_impresso=_componente_motor(
                    sg.subtotal_atual_impresso,
                    sg.tipo_fiscal,
                    f"/subgrupos_atuais/{idx}/subtotal_atual_impresso/price_basis",
                    erros,
                ),
                tabela_atual=tabela,
            )
        )

    opcoes: list[OpcaoPlano] = []
    for idx, op in enumerate(rascunho.opcoes_proposta):
        tabela: list[TabelaPrecoFaixa] = []
        for f_idx, faixa in enumerate(op.tabela):
            item = _tabela_faixa_motor(
                faixa,
                op.tipo_fiscal,
                f"/opcoes_proposta/{idx}/tabela/{f_idx}/price_basis",
                erros,
            )
            if item is not None:
                tabela.append(item)
        opcoes.append(
            OpcaoPlano(
                id=op.id,
                operadora=op.operadora,
                plano_nome=op.plano_nome,
                regime_copart_id=op.regime_copart_id,
                tipo_fiscal=TipoFiscal(op.tipo_fiscal),
                tabela=tabela,
                premio_saude=_componente_motor(
                    op.premio_saude,
                    op.tipo_fiscal,
                    f"/opcoes_proposta/{idx}/premio_saude/price_basis",
                    erros,
                ),
                iof=_componente_motor(
                    op.iof,
                    op.tipo_fiscal,
                    f"/opcoes_proposta/{idx}/iof/price_basis",
                    erros,
                ),
                total_recorrente=_componente_motor(
                    op.total_recorrente,
                    op.tipo_fiscal,
                    f"/opcoes_proposta/{idx}/total_recorrente/price_basis",
                    erros,
                ),
                total_primeira_parcela=_componente_motor(
                    op.total_primeira_parcela,
                    op.tipo_fiscal,
                    f"/opcoes_proposta/{idx}/total_primeira_parcela/price_basis",
                    erros,
                ),
                subtotal_impresso=_componente_motor(
                    op.subtotal_impresso,
                    op.tipo_fiscal,
                    f"/opcoes_proposta/{idx}/subtotal_impresso/price_basis",
                    erros,
                ),
                custos_unicos=[
                    CustoUnico(
                        id=cu.id,
                        descricao=cu.descricao,
                        valor_centavos=cu.valor.centavos or 0,
                        proveniencia=_proveniencia_motor(cu.valor.proveniencia),
                    )
                    for cu in op.custos_unicos
                ],
                documento_id=op.documento_cotacao_id,
            )
        )

    regimes = [
        RegimeCopart(id=r.id, tipo=RegimeCopartTipo(r.tipo))
        for r in rascunho.regimes_copart
    ]
    cenarios = [
        Cenario(
            id=c.id,
            rotulo=c.rotulo,
            atribuicoes=[
                AtribuicaoPlano(
                    id=a.id,
                    alvo_tipo=AlvoTipo(a.alvo_tipo),
                    alvo_id=a.alvo_id,
                    opcao_plano_id=a.opcao_plano_id,
                )
                for a in c.atribuicoes
            ],
        )
        for c in rascunho.cenarios
    ]

    if erros:
        return None, erros

    return (
        EstudoInput(
            id=rascunho.id,
            formato=FormatoEstudo(rascunho.formato),
            vidas=vidas,
            subgrupos_atuais=subgrupos,
            opcoes_plano=opcoes,
            regimes_copart=regimes,
            cenarios=cenarios,
        ),
        [],
    )


def mapear_effective_policy(
    rascunho: RascunhoEstudo,
    policy_set: PolicySet,
    erros: list[ErroCompilacao],
) -> EffectivePolicy | None:
    esc = rascunho.escolhas

    if esc.data_referencia_idade is None:
        erros.append(
            _erro(
                "APP-ESC-001",
                "/escolhas/data_referencia_idade",
                "Informe a data de referência para calcular as idades do estudo.",
            )
        )

    baseline = esc.baseline_escolhido
    if not baseline.confirmado or baseline.valor is None:
        erros.append(
            _erro(
                "APP-ESC-002",
                "/escolhas/baseline_escolhido/confirmado",
                "Confirme qual valor considerar como situação atual: "
                "contrato vigente ou reajustado.",
            )
        )

    precedencia = esc.precedencia_atual_vida
    if not precedencia.confirmado or precedencia.valor is None:
        erros.append(
            _erro(
                "APP-ESC-003",
                "/escolhas/precedencia_atual_vida/confirmado",
                "Confirme qual fonte prevalece em caso de diferença: "
                "tabela do plano atual ou valor da fatura.",
            )
        )

    if erros:
        return None

    baseline_map = {
        "vigente": BaselineEscolhido.VIGENTE,
        "reajustado": BaselineEscolhido.REAJUSTADO,
    }
    precedencia_map = {
        "tabela_atual": PrecedenciaAtualVida.TABELA_ATUAL,
        "valor_fatura": PrecedenciaAtualVida.VALOR_FATURA,
    }

    return EffectivePolicy(
        policy_set_versao=policy_set.versao,
        data_referencia_idade=esc.data_referencia_idade,
        baseline_escolhido=baseline_map[baseline.valor],  # type: ignore[index]
        precedencia_atual_vida=precedencia_map[precedencia.valor],  # type: ignore[index]
        iof_bps=policy_set.iof_bps,
        tolerancias=policy_set.tolerancias,
        estrategia_arredondamento=policy_set.estrategia_arredondamento,
        max_vidas_homologadas=policy_set.max_vidas_homologadas,
        politicas_resolvidas=policy_set.politicas_resolvidas,
    )
