"""Suíte E — Idade/faixa, precedência atual (DP-01, DP-08)."""

from datetime import date

from newport_motor.engine import calcular
from newport_motor.faixa import faixa_em
from newport_motor.models import AtribuicaoPlano, Cenario, EstudoInput
from newport_motor.money import apply_rate_bps
from newport_motor.types import (
    FormatoEstudo,
    PrecedenciaAtualVida,
    PriceBasis,
    RateBasisPoints,
    RegimeCopartTipo,
    SeveridadeValidacao,
)
from tests.conftest import opcao_plano, policy_completa, regime, subgrupo_atual, vida_ficticia


def test_faixa_na_data_referencia():
    nasc = date(1990, 6, 15)
    ref = date(2026, 6, 30)
    idade, faixa = faixa_em(nasc, ref)
    assert idade == 36
    assert faixa == 4


def test_data_referencia_ausente_bloqueia_b07():
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 1, 1), "sg-1")
    op = opcao_plano("op-1")
    sg = subgrupo_atual()
    cenario = Cenario(
        id="c1",
        atribuicoes=[
            AtribuicaoPlano(id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1")
        ],
    )
    estudo = EstudoInput(
        id="estudo-e",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )
    policy = policy_completa(data_ref=None)
    result = calcular(estudo, policy)
    assert "B-07" in result.codigos_bloqueio()
    assert not result.cenarios


def test_idade_valor_suspeita_b04():
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 1, 1), "sg-1", valor_fatura=999_99, fatura_basis=PriceBasis.EXCLUI_IOF)
    op = opcao_plano("op-1")
    sg = subgrupo_atual()
    cenario = Cenario(
        id="c1",
        atribuicoes=[
            AtribuicaoPlano(id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1")
        ],
    )
    estudo = EstudoInput(
        id="estudo-e2",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )
    result = calcular(estudo, policy_completa())
    b04 = [v for v in result.validacoes if v.codigo == "B-04" and v.severidade == SeveridadeValidacao.BLOQUEANTE]
    assert b04
    assert "faixa candidata" not in b04[0].mensagem.lower()


def test_sem_tabela_atual_nao_bloqueia_b04():
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 1, 1), "sg-1", valor_fatura=999_99)
    op = opcao_plano("op-1")
    sg = subgrupo_atual(tabela_atual=[])
    cenario = Cenario(
        id="c1",
        atribuicoes=[
            AtribuicaoPlano(id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1")
        ],
    )
    estudo = EstudoInput(
        id="estudo-e3",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )
    result = calcular(estudo, policy_completa())
    b04_bloq = [v for v in result.validacoes if v.codigo == "B-04" and v.severidade == SeveridadeValidacao.BLOQUEANTE]
    assert not b04_bloq


def test_precedencia_obrigatoria_quando_ambos_existem():
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 1, 1), "sg-1", valor_fatura=999_99, fatura_basis=PriceBasis.EXCLUI_IOF)
    op = opcao_plano("op-1")
    sg = subgrupo_atual()
    cenario = Cenario(
        id="c1",
        atribuicoes=[AtribuicaoPlano(id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1")],
    )
    estudo = EstudoInput(
        id="prec",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )
    policy = policy_completa(precedencia=None)
    result = calcular(estudo, policy)
    assert "B-07" in result.codigos_bloqueio()
    assert not result.cenarios


def test_precedencia_tabela_atual():
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia(
        "v1", date(1990, 1, 1), "sg-1",
        valor_fatura=999_99, fatura_basis=PriceBasis.EXCLUI_IOF,
    )
    v.idade_valor_resolvido = True  # B-04 já tratado; testa só precedência de cálculo
    op = opcao_plano("op-1")
    sg = subgrupo_atual()
    cenario = Cenario(
        id="c1",
        atribuicoes=[AtribuicaoPlano(id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1")],
    )
    estudo = EstudoInput(
        id="prec2",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )
    policy = policy_completa(precedencia=PrecedenciaAtualVida.TABELA_ATUAL)
    result = calcular(estudo, policy)
    assert result.cenarios
    esperado = apply_rate_bps(112_000, RateBasisPoints(238))
    assert result.cenarios[0].secoes[0].subgrupos[0].vidas[0].atual_vigente_centavos.centavos == esperado
