"""Dados fictícios para demonstração — equivalente à fixture renovacao_1plano_12vidas."""

from __future__ import annotations

from datetime import date

from newport_app.models.draft import (
    AtribuicaoRascunho,
    CenarioRascunho,
    EscolhasEstudo,
    OpcaoPropostaRascunho,
    RascunhoEstudo,
    RegimeCopartRascunho,
    SubgrupoRascunho,
    TabelaFaixaRascunho,
    VidaRascunho,
)


def _tabela_atual() -> list[TabelaFaixaRascunho]:
    return [
        TabelaFaixaRascunho(faixa=f, valor_centavos=80_000 + f * 8_000) for f in range(10)
    ]


def _tabela_proposta() -> list[TabelaFaixaRascunho]:
    return [
        TabelaFaixaRascunho(faixa=f, valor_centavos=100_000 + f * 10_000) for f in range(10)
    ]


def _escolhas_padrao() -> EscolhasEstudo:
    return EscolhasEstudo(
        data_referencia_idade=date(2026, 6, 30),
        valor_atual_referencia="reajustado",
        prioridade_fatura_ou_tabela="tabela_atual",
        max_beneficiarios_homologados=29,
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
        id=estudo_id,
        titulo=titulo,
        formato="renovacao",
        vidas=vidas,
        subgrupos_atuais=[
            SubgrupoRascunho(
                id="sg-1",
                operadora="Operadora Demo",
                plano_nome="Plano atual fictício",
                regime_copart_id="regime-sem",
                tipo_fiscal="seguradora",
                reajuste_bps=1198,
                fatura_inclui_iof=False,
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
                valores_incluem_iof=False,
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
        escolhas=_escolhas_padrao(),
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
