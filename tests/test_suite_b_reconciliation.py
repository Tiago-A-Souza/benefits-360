"""Suíte B — Reconciliação (B-02)."""

from datetime import date

from newport_motor.engine import calcular
from newport_motor.models import AtribuicaoPlano, Cenario, EstudoInput
from newport_motor.policy import EffectivePolicy, TolerancePolicy
from newport_motor.types import FormatoEstudo, RegimeCopartTipo, SeveridadeValidacao
from tests.conftest import (
    opcao_plano,
    policy_completa,
    regime,
    subgrupo_atual,
    vida_ficticia,
)


def _estudo_renovacao_2_vidas(total_recorrente: int | None):
    reg = regime(RegimeCopartTipo.SEM)
    v1 = vida_ficticia("v1", date(1990, 3, 15), "sg-1")
    v2 = vida_ficticia("v2", date(1985, 7, 20), "sg-1")
    op = opcao_plano("op-1", total_recorrente=total_recorrente)
    sg = subgrupo_atual()
    cenario = Cenario(
        id="c1",
        atribuicoes=[
            AtribuicaoPlano(
                id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1"
            )
        ],
    )
    return EstudoInput(
        id="estudo-b",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v1, v2],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )


def _subtotal_calculado(estudo, policy):
    result = calcular(estudo, policy)
    return result.cenarios[0].secoes[0].subgrupos[0].subtotal_proposta_centavos.centavos


def test_reconciliacao_ok():
    estudo = _estudo_renovacao_2_vidas(total_recorrente=None)
    policy = policy_completa()
    subtotal = _subtotal_calculado(estudo, policy)
    from newport_motor.provenance import ComponenteFinanceiro, ProvenienciaCampo
    from newport_motor.types import OrigemValor, PriceBasis

    estudo.opcoes_plano[0].total_recorrente = ComponenteFinanceiro(
        centavos=subtotal,
        price_basis=PriceBasis.INCLUI_IOF,
        proveniencia=ProvenienciaCampo(origem=OrigemValor.MANUAL),
    )
    result = calcular(estudo, policy)
    bloqueios_b02 = [
        v for v in result.validacoes if v.codigo == "B-02" and v.severidade == SeveridadeValidacao.BLOQUEANTE
    ]
    assert not bloqueios_b02
    assert result.cenarios


def test_reconciliacao_total_ausente_nao_quebra():
    estudo = _estudo_renovacao_2_vidas(total_recorrente=None)
    result = calcular(estudo, policy_completa())
    assert result.cenarios
    bloqueios_b02 = [
        v for v in result.validacoes if v.codigo == "B-02" and v.severidade == SeveridadeValidacao.BLOQUEANTE
    ]
    assert not bloqueios_b02


def test_reconciliacao_bloqueante_fora_tolerancia():
    estudo = _estudo_renovacao_2_vidas(total_recorrente=99_999_99)
    from newport_motor.provenance import ComponenteFinanceiro, ProvenienciaCampo
    from newport_motor.types import OrigemValor, PriceBasis

    estudo.opcoes_plano[0].total_recorrente = ComponenteFinanceiro(
        centavos=99_999_99,
        price_basis=PriceBasis.INCLUI_IOF,
        proveniencia=ProvenienciaCampo(origem=OrigemValor.MANUAL),
    )
    result = calcular(estudo, policy_completa())
    bloqueios = [
        v for v in result.validacoes if v.codigo == "B-02" and v.severidade == SeveridadeValidacao.BLOQUEANTE
    ]
    assert bloqueios


def test_tolerancias_vindas_da_policy():
    estudo = _estudo_renovacao_2_vidas(total_recorrente=99_999_99)
    from newport_motor.provenance import ComponenteFinanceiro, ProvenienciaCampo
    from newport_motor.types import OrigemValor, PriceBasis

    estudo.opcoes_plano[0].total_recorrente = ComponenteFinanceiro(
        centavos=99_999_99,
        price_basis=PriceBasis.INCLUI_IOF,
        proveniencia=ProvenienciaCampo(origem=OrigemValor.MANUAL),
    )
    policy = policy_completa()
    policy.tolerancias = TolerancePolicy(total_centavos=10_000_000)
    result = calcular(estudo, policy)
    bloqueios = [
        v for v in result.validacoes if v.codigo == "B-02" and v.severidade == SeveridadeValidacao.BLOQUEANTE
    ]
    assert not bloqueios
