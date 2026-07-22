"""Suíte 1.2.1 — Semântica de subtotais e endurecimentos cirúrgicos."""

from datetime import date

from newport_motor.engine import calcular
from newport_motor.models import (
    AtribuicaoPlano,
    Cenario,
    DocumentoCotacao,
    EstudoInput,
)
from newport_motor.money import apply_rate_bps
from newport_motor.provenance import ComponenteFinanceiro, ProvenienciaCampo
from newport_motor.types import (
    EstadoExtracao,
    FormatoEstudo,
    OrigemValor,
    PriceBasis,
    RateBasisPoints,
    RegimeCopartTipo,
    SeveridadeValidacao,
    TipoFiscal,
)
from tests.conftest import opcao_plano, policy_completa, regime, subgrupo_atual, tabela_padrao, vida_ficticia

IOF = RateBasisPoints(238)


def _estudo_subtotais_separados(
    subtotal_atual_impresso: int,
    subtotal_proposta_impresso: int | None = None,
):
    """1 vida faixa 4; atual tabela 100k exclui; proposta tabela 80k exclui."""
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 1, 1), "sg-1")
    atual_vigente = apply_rate_bps(100_000, IOF)
    proposta = apply_rate_bps(80_000, IOF)
    sg = subgrupo_atual(
        base_tabela=100_000,
        incremento=0,
        tabela_basis=PriceBasis.EXCLUI_IOF,
        subtotal_impresso=ComponenteFinanceiro(
            centavos=subtotal_atual_impresso,
            price_basis=PriceBasis.INCLUI_IOF,
            proveniencia=ProvenienciaCampo(origem=OrigemValor.MANUAL),
        ),
    )
    op = opcao_plano(
        "op-1",
        base=80_000,
        incremento=0,
        tabela_basis=PriceBasis.EXCLUI_IOF,
        total_recorrente=proposta,
        total_recorrente_basis=PriceBasis.INCLUI_IOF,
    )
    if subtotal_proposta_impresso is not None:
        op.subtotal_impresso = ComponenteFinanceiro(
            centavos=subtotal_proposta_impresso,
            price_basis=PriceBasis.INCLUI_IOF,
            proveniencia=ProvenienciaCampo(origem=OrigemValor.MANUAL),
        )
    est = EstudoInput(
        id="estudo-121",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[
            Cenario(
                id="c1",
                atribuicoes=[
                    AtribuicaoPlano(
                        id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1"
                    )
                ],
            )
        ],
    )
    return est, atual_vigente, proposta


def test_subtotal_atual_e_proposta_diferentes_sem_b02():
    """Subtotal atual 10.000, proposta 8.000 — diferença legítima não gera B-02."""
    atual_vigente = apply_rate_bps(100_000, IOF)
    proposta = apply_rate_bps(80_000, IOF)
    est, _, _ = _estudo_subtotais_separados(
        subtotal_atual_impresso=atual_vigente,
        subtotal_proposta_impresso=proposta,
    )
    result = calcular(est, policy_completa())
    bloqueios_b02 = [
        v for v in result.validacoes if v.codigo == "B-02" and v.severidade == SeveridadeValidacao.BLOQUEANTE
    ]
    assert not bloqueios_b02, bloqueios_b02
    rv = result.cenarios[0].secoes[0].subgrupos[0].vidas[0]
    assert rv.atual_vigente_centavos.centavos == atual_vigente
    assert rv.proposta_centavos.centavos == proposta


def test_subtotal_atual_divergente_b02():
    atual_vigente = apply_rate_bps(100_000, IOF)
    est, _, _ = _estudo_subtotais_separados(
        subtotal_atual_impresso=atual_vigente + 500,
    )
    result = calcular(est, policy_completa())
    bloqueios = [
        v
        for v in result.validacoes
        if v.codigo == "B-02"
        and v.severidade == SeveridadeValidacao.BLOQUEANTE
        and "Subtotal atual" in v.mensagem
    ]
    assert bloqueios


def test_subtotal_proposta_divergente_b02():
    atual_vigente = apply_rate_bps(100_000, IOF)
    proposta = apply_rate_bps(80_000, IOF)
    est, _, _ = _estudo_subtotais_separados(
        subtotal_atual_impresso=atual_vigente,
        subtotal_proposta_impresso=proposta + 500,
    )
    result = calcular(est, policy_completa())
    bloqueios = [
        v
        for v in result.validacoes
        if v.codigo == "B-02"
        and v.severidade == SeveridadeValidacao.BLOQUEANTE
        and "Subtotal da proposta" in v.mensagem
    ]
    assert bloqueios


def test_b03_extraido_nao_confirmado_com_documento_alerta():
    reg = regime(RegimeCopartTipo.SEM)
    doc = DocumentoCotacao(
        id="doc-alerta",
        operadora="X",
        estado_extracao=EstadoExtracao.EXTRAIDO_COM_ALERTA,
    )
    v = vida_ficticia("v1", date(1990, 1, 1), "sg-1", valor_fatura=80_000)
    v.fatura_proveniencia = ProvenienciaCampo(
        origem=OrigemValor.EXTRAIDO,
        documento_id="doc-alerta",
        confirmado=False,
    )
    est = EstudoInput(
        id="e",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[subgrupo_atual(tabela_atual=[])],
        opcoes_plano=[opcao_plano("op-1")],
        regimes_copart=[reg],
        documentos=[doc],
        cenarios=[
            Cenario(
                id="c1",
                atribuicoes=[
                    AtribuicaoPlano(
                        id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1"
                    )
                ],
            )
        ],
    )
    result = calcular(est, policy_completa())
    assert "B-03" in result.codigos_bloqueio()


def test_alvo_tipo_incompativel_renovacao_b06():
    reg = regime(RegimeCopartTipo.SEM)
    est = EstudoInput(
        id="e",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[vida_ficticia("sg-1", date(1990, 1, 1), "sg-1")],
        subgrupos_atuais=[subgrupo_atual("sg-1")],
        opcoes_plano=[opcao_plano("op-1")],
        regimes_copart=[reg],
        cenarios=[
            Cenario(
                id="c1",
                atribuicoes=[
                    AtribuicaoPlano(
                        id="a1", alvo_tipo="vida", alvo_id="sg-1", opcao_plano_id="op-1"
                    )
                ],
            )
        ],
    )
    result = calcular(est, policy_completa())
    assert "B-06" in result.codigos_bloqueio()
    assert any("alvo_tipo=subgrupo" in v.mensagem for v in result.validacoes)


def test_alvo_tipo_incompativel_novo_b06():
    reg = regime(RegimeCopartTipo.SEM)
    est = EstudoInput(
        id="e",
        formato=FormatoEstudo.NOVO,
        vidas=[vida_ficticia("sg-1", date(1990, 1, 1), None)],
        opcoes_plano=[opcao_plano("op-1")],
        regimes_copart=[reg],
        cenarios=[
            Cenario(
                id="c1",
                atribuicoes=[
                    AtribuicaoPlano(
                        id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1"
                    )
                ],
            )
        ],
    )
    result = calcular(est, policy_completa(data_ref=date(2026, 6, 30), baseline=None, precedencia=None))
    assert "B-06" in result.codigos_bloqueio()


def test_documento_inexistente_b05():
    reg = regime(RegimeCopartTipo.SEM)
    op = opcao_plano("op-1", doc_id="doc-fantasma")
    est = EstudoInput(
        id="e",
        formato=FormatoEstudo.NOVO,
        vidas=[vida_ficticia("v1", date(1990, 1, 1), None)],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[
            Cenario(
                id="c1",
                atribuicoes=[
                    AtribuicaoPlano(
                        id="a1", alvo_tipo="vida", alvo_id="v1", opcao_plano_id="op-1"
                    )
                ],
            )
        ],
    )
    result = calcular(est, policy_completa(data_ref=date(2026, 6, 30), baseline=None, precedencia=None))
    assert "B-05" in result.codigos_bloqueio()


def test_linhagem_preserva_pagina_e_trecho():
    from newport_motor.models import TabelaPrecoFaixa

    reg = regime(RegimeCopartTipo.SEM)
    tabela = tabela_padrao(100_000, 10_000, PriceBasis.EXCLUI_IOF)
    tabela[4] = TabelaPrecoFaixa(
        faixa=4,
        valor_centavos=100_000,
        price_basis=PriceBasis.EXCLUI_IOF,
        proveniencia=ProvenienciaCampo(
            origem=OrigemValor.EXTRAIDO,
            documento_id="doc-1",
            evidencia_pagina=3,
            evidencia_trecho="Tabela faixa 34-36",
        ),
    )
    op = opcao_plano("op-1")
    op.tabela = tabela
    est = EstudoInput(
        id="e",
        formato=FormatoEstudo.NOVO,
        vidas=[vida_ficticia("v1", date(1990, 1, 1), None)],
        opcoes_plano=[op],
        regimes_copart=[reg],
        documentos=[DocumentoCotacao(id="doc-1", operadora="X")],
        cenarios=[
            Cenario(
                id="c1",
                atribuicoes=[
                    AtribuicaoPlano(
                        id="a1", alvo_tipo="vida", alvo_id="v1", opcao_plano_id="op-1"
                    )
                ],
            )
        ],
    )
    result = calcular(est, policy_completa(data_ref=date(2026, 6, 30), baseline=None, precedencia=None))
    fonte = result.cenarios[0].secoes[0].subgrupos[0].vidas[0].proposta_centavos.fontes[0]
    assert fonte.evidencia_pagina == 3
    assert fonte.evidencia_trecho == "Tabela faixa 34-36"
