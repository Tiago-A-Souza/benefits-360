"""Suíte G — Pureza e EffectivePolicy."""

import json
from datetime import date

from newport_motor.engine import calcular
from newport_motor.models import AtribuicaoPlano, Cenario, EstudoInput
from newport_motor.policy import EffectivePolicy, TolerancePolicy
from newport_motor.types import BaselineEscolhido, FormatoEstudo, RegimeCopartTipo, RoundingStrategy
from tests.conftest import opcao_plano, policy_completa, regime, subgrupo_atual, vida_ficticia


def _estudo_minimo():
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
    return EstudoInput(
        id="estudo-g",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )


def test_mesmo_input_mesmo_output():
    estudo = _estudo_minimo()
    policy = policy_completa()
    r1 = calcular(estudo, policy)
    r2 = calcular(estudo, policy)
    assert r1.model_dump() == r2.model_dump()


def test_politicas_efetivas_embutidas():
    estudo = _estudo_minimo()
    policy = EffectivePolicy(
        data_referencia_idade=date(2026, 6, 30),
        baseline_escolhido=BaselineEscolhido.REAJUSTADO,
        tolerancias=TolerancePolicy(por_vida_centavos=2),
        estrategia_arredondamento=RoundingStrategy.POR_VIDA_ENTAO_SOMA,
        policy_set_versao="test-v1",
    )
    result = calcular(estudo, policy)
    assert result.politicas_efetivas["policy_set_versao"] == "test-v1"
    assert result.politicas_efetivas["tolerancias"]["por_vida_centavos"] == 2


def test_tolerancias_da_policy_afetam_resultado():
    estudo = _estudo_minimo()
    policy = policy_completa()
    assert "tolerancias" in policy.as_snapshot_dict()
