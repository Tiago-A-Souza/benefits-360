"""Suíte D — Atual e reajuste (renovação)."""

from datetime import date

from newport_motor.engine import calcular
from newport_motor.models import AtribuicaoPlano, Cenario, EstudoInput
from newport_motor.money import apply_rate_bps
from newport_motor.types import BaselineEscolhido, FormatoEstudo, RegimeCopartTipo, TipoFiscal
from tests.conftest import opcao_plano, policy_completa, regime, subgrupo_atual, vida_ficticia


def test_atual_vigente_reajustado_e_diferencas():
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 6, 1), "sg-1")
    op = opcao_plano("op-1")
    sg = subgrupo_atual(reajuste_bps=1198)
    cenario = Cenario(
        id="c1",
        atribuicoes=[
            AtribuicaoPlano(id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1")
        ],
    )
    estudo = EstudoInput(
        id="estudo-d",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )
    policy = policy_completa(baseline=BaselineEscolhido.REAJUSTADO)
    result = calcular(estudo, policy)
    rv = result.cenarios[0].secoes[0].subgrupos[0].vidas[0]
    vigente = rv.atual_vigente_centavos.centavos
    reajustado = rv.atual_reajustado_centavos.centavos
    assert reajustado == apply_rate_bps(vigente, 1198)
    assert rv.diff_mes_centavos.centavos == rv.proposta_centavos.centavos - reajustado
    assert rv.diff_ano_centavos.centavos == rv.diff_mes_centavos.centavos * 12


def test_baseline_vigente():
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 6, 1), "sg-1")
    op = opcao_plano("op-1")
    sg = subgrupo_atual(reajuste_bps=1000)
    cenario = Cenario(
        id="c1",
        atribuicoes=[
            AtribuicaoPlano(id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1")
        ],
    )
    estudo = EstudoInput(
        id="estudo-d2",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )
    policy = policy_completa(baseline=BaselineEscolhido.VIGENTE)
    result = calcular(estudo, policy)
    assert result.cenarios[0].baseline_apresentado == "vigente"
