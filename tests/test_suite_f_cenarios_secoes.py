"""Suíte F — Cenários e seções por regime (P6)."""

from datetime import date

from newport_motor.engine import calcular
from newport_motor.models import AtribuicaoPlano, Cenario, EstudoInput
from newport_motor.types import FormatoEstudo, RegimeCopartTipo, SeveridadeValidacao
from tests.conftest import opcao_plano, policy_completa, regime, subgrupo_atual, vida_ficticia


def test_secoes_disjuntas_por_regime():
    r_sem = regime(RegimeCopartTipo.SEM, "a")
    r_parcial = regime(RegimeCopartTipo.PARCIAL, "b")
    sg1 = subgrupo_atual("sg-1")
    sg2 = subgrupo_atual("sg-2", operadora="Amil")
    sg2.tipo_fiscal = sg2.tipo_fiscal  # operadora
    from newport_motor.types import TipoFiscal

    sg2 = subgrupo_atual("sg-2", operadora="Amil", tipo_fiscal=TipoFiscal.OPERADORA)
    v1 = vida_ficticia("v1", date(1988, 1, 1), "sg-1")
    v2 = vida_ficticia("v2", date(1992, 1, 1), "sg-2")
    op1 = opcao_plano("op-1", regime_id=r_sem.id)
    op2 = opcao_plano("op-2", operadora="Amil", regime_id=r_parcial.id, tipo_fiscal=TipoFiscal.OPERADORA)
    cenario = Cenario(
        id="c1",
        atribuicoes=[
            AtribuicaoPlano(id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1"),
            AtribuicaoPlano(id="a2", alvo_tipo="subgrupo", alvo_id="sg-2", opcao_plano_id="op-2"),
        ],
    )
    estudo = EstudoInput(
        id="estudo-f",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v1, v2],
        subgrupos_atuais=[sg1, sg2],
        opcoes_plano=[op1, op2],
        regimes_copart=[r_sem, r_parcial],
        cenarios=[cenario],
    )
    result = calcular(estudo, policy_completa())
    assert len(result.cenarios[0].secoes) == 2
    tipos = {s.regime_tipo for s in result.cenarios[0].secoes}
    assert RegimeCopartTipo.SEM in tipos
    assert RegimeCopartTipo.PARCIAL in tipos


def test_b06_atribuicao_ausente():
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 1, 1), "sg-1")
    op = opcao_plano("op-1")
    sg = subgrupo_atual()
    cenario = Cenario(id="c1", atribuicoes=[])
    estudo = EstudoInput(
        id="estudo-f2",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )
    result = calcular(estudo, policy_completa())
    assert "B-06" in result.codigos_bloqueio()
    assert not result.cenarios
