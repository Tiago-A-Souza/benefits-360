"""Comparativo expõe bloqueios do motor quando o cálculo retorna zero resultados."""

from __future__ import annotations

from datetime import date

from newport_app.adapters.motor_out import motor_result_para_comparativo
from newport_app.draft_compiler import compile
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_motor.engine import calcular
from newport_motor.models import AtribuicaoPlano, Cenario, EstudoInput
from newport_motor.provenance import ComponenteFinanceiro, ProvenienciaCampo
from newport_motor.result import MotorResult
from newport_motor.types import FormatoEstudo, OrigemValor, PriceBasis, RegimeCopartTipo
from tests.conftest import opcao_plano, policy_completa, regime, subgrupo_atual, tabela_padrao, vida_ficticia
from tests.test_comparativo_multiplas_propostas import _rascunho_quatro_propostas


def _comparativo_rascunho(rascunho):
    compilado = compile(rascunho)
    assert compilado.compilavel and compilado.compilado is not None
    motor = calcular(
        compilado.compilado.estudo_input,
        compilado.compilado.effective_policy,
    )
    return motor_result_para_comparativo(rascunho, motor), motor


def _comparativo_motor(rascunho, estudo: EstudoInput, policy):
    motor = calcular(estudo, policy)
    return motor_result_para_comparativo(rascunho, motor), motor


def _estudo_renovacao_minimo(*, atribuicoes: list[AtribuicaoPlano] | None = None):
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 1, 1), "sg-1")
    op = opcao_plano("op-1")
    sg = subgrupo_atual()
    if atribuicoes is None:
        atribuicoes = [
            AtribuicaoPlano(
                id="a1",
                alvo_tipo="subgrupo",
                alvo_id="sg-1",
                opcao_plano_id="op-1",
            )
        ]
    cenario = Cenario(id="c1", atribuicoes=atribuicoes)
    return EstudoInput(
        id="estudo-bloqueio",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )


def test_b06_subgrupo_sem_atribuicao_exposto_no_comparativo():
    rascunho = rascunho_demo_12_vidas()
    rascunho.cenarios[0].atribuicoes = []

    resp, motor = _comparativo_rascunho(rascunho)

    assert not motor.cenarios
    assert resp.consistencia is not None
    assert resp.consistencia.consistente is False
    assert resp.calculo_realizado is False
    bloqueios_b06 = [b for b in resp.consistencia.bloqueios if b.codigo == "B-06"]
    assert bloqueios_b06
    b06 = bloqueios_b06[0]
    assert b06.mensagem
    assert "B-06" in resp.consistencia.mensagem
    assert b06.alvo_rotulo == "Plano atual fictício"
    assert resp.consistencia.mensagem_contagem is not None
    assert "não produziu resultado" in resp.consistencia.mensagem_contagem
    assert not any(p.codigo == "APP-CMP-001" for p in resp.pendencias)


def test_b07_sem_data_referencia_idade_exposto_no_comparativo():
    rascunho = rascunho_demo_12_vidas()
    estudo = _estudo_renovacao_minimo()
    policy = policy_completa(data_ref=None)

    resp, motor = _comparativo_motor(rascunho, estudo, policy)

    assert not motor.cenarios
    bloqueios_b07 = [b for b in resp.consistencia.bloqueios if b.codigo == "B-07"]
    assert bloqueios_b07
    assert bloqueios_b07[0].alvo_rotulo == "Data de referência para idade"
    assert "B-07" in resp.consistencia.mensagem
    assert bloqueios_b07[0].etapa_sugerida == 1


def test_b02_price_basis_desconhecido_exposto_no_comparativo():
    rascunho = rascunho_demo_12_vidas()
    estudo = _estudo_renovacao_minimo()
    estudo.opcoes_plano[0].tabela = tabela_padrao(
        basis=PriceBasis.DESCONHECIDO,
    )
    estudo.opcoes_plano[0].total_recorrente = ComponenteFinanceiro(
        centavos=12_000_00,
        price_basis=PriceBasis.DESCONHECIDO,
        proveniencia=ProvenienciaCampo(origem=OrigemValor.MANUAL),
    )

    resp, motor = _comparativo_motor(rascunho, estudo, policy_completa())

    assert not motor.cenarios
    bloqueios_b02 = [b for b in resp.consistencia.bloqueios if b.codigo == "B-02"]
    assert bloqueios_b02
    assert "B-02" in resp.consistencia.mensagem
    assert "Proposta fictícia" in (bloqueios_b02[0].alvo_rotulo or "")


def test_estudo_valido_sem_regressao():
    rascunho = _rascunho_quatro_propostas()
    resp, _motor = _comparativo_rascunho(rascunho)

    assert resp.consistencia is not None
    assert resp.consistencia.consistente is True
    assert resp.consistencia.bloqueios == []
    assert resp.calculo_realizado is True


def test_zero_resultados_sem_bloqueios_preserva_mensagem_generica():
    rascunho = _rascunho_quatro_propostas()
    motor = MotorResult(
        estudo_id=rascunho.id,
        cenarios=[],
        validacoes=[],
        bloqueios_abertos=[],
        politicas_efetivas={"data_referencia_idade": date(2026, 6, 30).isoformat()},
    )

    resp = motor_result_para_comparativo(rascunho, motor)

    assert resp.consistencia is not None
    assert resp.consistencia.bloqueios == []
    assert resp.consistencia.mensagem_contagem is None
    assert "não produziu resultado" in (resp.consistencia.mensagem or "") or (
        "não produziram resultado" in (resp.consistencia.mensagem or "")
    )
    assert any(p.codigo == "APP-CMP-001" for p in resp.pendencias)
