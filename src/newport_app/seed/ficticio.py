"""Dados fictícios para demonstração — RascunhoEstudo v1."""

from __future__ import annotations

from datetime import date

from newport_app.models.draft import (
    AtribuicaoRascunho,
    CampoConfirmavelBaseline,
    CampoConfirmavelPrecedencia,
    CenarioRascunho,
    EmpresaCliente,
    EscolhasEstudo,
    OpcaoPropostaRascunho,
    OrigemValorRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
    RASCUNHO_VERSAO_ATUAL,
    RascunhoEstudo,
    RegimeCopartRascunho,
    SubgrupoAtualRascunho,
    TabelaFaixaRascunho,
    VidaRascunho,
)
from newport_app.policy.registry import POLICY_SET_VERSAO_PADRAO


def _prov_manual_confirmada() -> ProvenienciaRascunho:
    return ProvenienciaRascunho(
        origem=OrigemValorRascunho.MANUAL,
        extrator_versao="manual",
        confirmado=True,
    )


def _faixa_atual(f: int) -> TabelaFaixaRascunho:
    return TabelaFaixaRascunho(
        faixa=f,
        valor_centavos=80_000 + f * 8_000,
        quantidade_cotada=None,
        price_basis=PriceBasisRascunho.EXCLUI_IOF,
        proveniencia=_prov_manual_confirmada(),
    )


def _faixa_proposta(f: int) -> TabelaFaixaRascunho:
    return TabelaFaixaRascunho(
        faixa=f,
        valor_centavos=100_000 + f * 10_000,
        quantidade_cotada=0,
        price_basis=PriceBasisRascunho.EXCLUI_IOF,
        proveniencia=_prov_manual_confirmada(),
    )


def _tabela_atual() -> list[TabelaFaixaRascunho]:
    return [_faixa_atual(f) for f in range(10)]


def _tabela_proposta() -> list[TabelaFaixaRascunho]:
    return [_faixa_proposta(f) for f in range(10)]


def _escolhas_confirmadas() -> EscolhasEstudo:
    return EscolhasEstudo(
        data_referencia_idade=date(2026, 6, 30),
        baseline_escolhido=CampoConfirmavelBaseline(
            valor="reajustado",
            confirmado=True,
        ),
        precedencia_atual_vida=CampoConfirmavelPrecedencia(
            valor="tabela_atual",
            confirmado=True,
        ),
    )


def _corpo_renovacao(
    estudo_id: str,
    titulo: str,
    n_vidas: int,
) -> RascunhoEstudo:
    vidas = [
        VidaRascunho(
            id=f"v{i}",
            nome=f"Beneficiário fictício {i + 1}",
            nascimento=date(1970 + (i % 30), 1, 1),
            incluida=True,
            subgrupo_atual_id="sg-1",
        )
        for i in range(n_vidas)
    ]
    return RascunhoEstudo(
        rascunho_versao=RASCUNHO_VERSAO_ATUAL,
        policy_set_versao=POLICY_SET_VERSAO_PADRAO,
        id=estudo_id,
        titulo=titulo,
        formato="renovacao",
        empresa_cliente=EmpresaCliente(nome="Empresa Demonstração Ltda."),
        vidas=vidas,
        subgrupos_atuais=[
            SubgrupoAtualRascunho(
                id="sg-1",
                operadora="Operadora Demo",
                plano_nome="Plano atual fictício",
                regime_copart_id="regime-sem",
                tipo_fiscal="seguradora",
                reajuste_bps=1198,
                fatura_price_basis=PriceBasisRascunho.EXCLUI_IOF,
                tabela_atual=_tabela_atual(),
            )
        ],
        opcoes_proposta=[
            OpcaoPropostaRascunho(
                id="op-1",
                operadora="Operadora Demo",
                plano_nome="Proposta fictícia",
                regime_copart_id="regime-sem",
                tipo_fiscal="seguradora",
                tabela=_tabela_proposta(),
            )
        ],
        regimes_copart=[RegimeCopartRascunho(id="regime-sem", tipo="sem")],
        cenarios=[
            CenarioRascunho(
                id="c1",
                rotulo="Cenário principal",
                atribuicoes=[
                    AtribuicaoRascunho(
                        id="a1",
                        alvo_tipo="subgrupo",
                        alvo_id="sg-1",
                        opcao_plano_id="op-1",
                    )
                ],
            )
        ],
        escolhas=_escolhas_confirmadas(),
    )


def rascunho_demo_12_vidas() -> RascunhoEstudo:
    return _corpo_renovacao(
        "demo-12",
        "Renovação fictícia — 12 beneficiários",
        12,
    )


def rascunho_demo_41_vidas() -> RascunhoEstudo:
    return _corpo_renovacao(
        "demo-41",
        "Renovação fictícia — 41 beneficiários (escala)",
        41,
    )
