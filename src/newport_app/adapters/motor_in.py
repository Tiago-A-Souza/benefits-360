"""Adaptação mínima RascunhoEstudo → tipos do motor."""

from __future__ import annotations

from newport_app.models.draft import RascunhoEstudo
from newport_motor.models import (
    AtribuicaoPlano,
    Cenario,
    EstudoInput,
    OpcaoPlano,
    RegimeCopart,
    SubgrupoAtual,
    TabelaPrecoFaixa,
    Vida,
)
from newport_motor.policy import EffectivePolicy
from newport_motor.provenance import ProvenienciaCampo
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


def _basis_inclui_iof(inclui: bool) -> PriceBasis:
    return PriceBasis.INCLUI_IOF if inclui else PriceBasis.EXCLUI_IOF


def rascunho_para_estudo_input(rascunho: RascunhoEstudo) -> EstudoInput:
    prov_manual = ProvenienciaCampo(origem=OrigemValor.MANUAL, confirmado=True)
    vidas = [
        Vida(
            id=v.id,
            nome=v.nome,
            nascimento=v.nascimento,
            incluida=v.incluida,
            subgrupo_atual_id=v.subgrupo_atual_id,
        )
        for v in rascunho.vidas
    ]
    subgrupos = [
        SubgrupoAtual(
            id=sg.id,
            operadora=sg.operadora,
            tipo_fiscal=TipoFiscal(sg.tipo_fiscal),
            plano_nome=sg.plano_nome,
            regime_copart_id=sg.regime_copart_id,
            reajuste_bps=sg.reajuste_bps,
            fatura_price_basis=_basis_inclui_iof(sg.fatura_inclui_iof),
            tabela_atual=[
                TabelaPrecoFaixa(
                    faixa=t.faixa,
                    valor_centavos=t.valor_centavos,
                    quantidade_cotada=t.quantidade_cotada,
                    price_basis=PriceBasis.EXCLUI_IOF,
                    proveniencia=prov_manual,
                )
                for t in sg.tabela_atual
            ],
        )
        for sg in rascunho.subgrupos_atuais
    ]
    opcoes = [
        OpcaoPlano(
            id=op.id,
            operadora=op.operadora,
            plano_nome=op.plano_nome,
            regime_copart_id=op.regime_copart_id,
            tipo_fiscal=TipoFiscal(op.tipo_fiscal),
            tabela=[
                TabelaPrecoFaixa(
                    faixa=t.faixa,
                    valor_centavos=t.valor_centavos,
                    quantidade_cotada=t.quantidade_cotada,
                    price_basis=_basis_inclui_iof(op.valores_incluem_iof),
                    proveniencia=prov_manual,
                )
                for t in op.tabela
            ],
        )
        for op in rascunho.opcoes_proposta
    ]
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
    return EstudoInput(
        id=rascunho.id,
        formato=FormatoEstudo(rascunho.formato),
        vidas=vidas,
        subgrupos_atuais=subgrupos,
        opcoes_plano=opcoes,
        regimes_copart=regimes,
        cenarios=cenarios,
    )


def rascunho_para_policy(rascunho: RascunhoEstudo) -> EffectivePolicy:
    esc = rascunho.escolhas
    baseline_map = {
        "vigente": BaselineEscolhido.VIGENTE,
        "reajustado": BaselineEscolhido.REAJUSTADO,
    }
    precedencia_map = {
        "tabela_atual": PrecedenciaAtualVida.TABELA_ATUAL,
        "valor_fatura": PrecedenciaAtualVida.VALOR_FATURA,
    }
    return EffectivePolicy(
        data_referencia_idade=esc.data_referencia_idade,
        baseline_escolhido=baseline_map[esc.valor_atual_referencia],
        precedencia_atual_vida=precedencia_map[esc.prioridade_fatura_ou_tabela],
        max_vidas_homologadas=esc.max_beneficiarios_homologados,
    )
