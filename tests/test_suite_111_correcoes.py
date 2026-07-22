"""Suíte 1.1.1 — Correções piloto (Alternativa A): prêmio+IOF, 1ª parcela, estratégias."""

from datetime import date

import pytest
from pydantic import ValidationError

from newport_motor.engine import calcular
from newport_motor.finance import (
    primeira_parcela_normalizada,
    recorrente_de_premio_e_iof,
    recorrente_para_primeira_parcela,
)
from newport_motor.models import AtribuicaoPlano, Cenario, CustoUnico, EstudoInput
from newport_motor.policy import EffectivePolicy
from newport_motor.provenance import ComponenteFinanceiro, ProvenienciaCampo
from newport_motor.rounding import apply_iof_strategy
from newport_motor.types import (
    FormatoEstudo,
    OrigemValor,
    PriceBasis,
    RateBasisPoints,
    RegimeCopartTipo,
    RoundingStrategy,
    SeveridadeValidacao,
    TipoFiscal,
)
from tests.conftest import opcao_plano, policy_completa, regime, subgrupo_atual, vida_ficticia


IOF = RateBasisPoints(238)
TF = TipoFiscal.SEGURADORA


def test_premio_exclui_iof_mais_iof_explicito():
    assert recorrente_de_premio_e_iof(
        10_000_00, PriceBasis.EXCLUI_IOF, 238_00, TF, IOF
    ) == 10_238_00


def test_premio_inclui_iof_iof_informativo_nao_soma():
    assert recorrente_de_premio_e_iof(
        10_238_00, PriceBasis.INCLUI_IOF, 238_00, TF, IOF
    ) == 10_238_00


def test_primeira_parcela_bases_diferentes_custo_unico():
    custos = 500_00
    recorrente = 10_238_00
    primeira = 10_500_00
    esperado = recorrente_para_primeira_parcela(
        recorrente, PriceBasis.INCLUI_IOF, custos, TF, IOF
    )
    primeira_equiv = primeira_parcela_normalizada(
        primeira, PriceBasis.EXCLUI_IOF, custos, TF, IOF
    )
    assert esperado == 10_738_00
    assert primeira_equiv == esperado
    assert primeira_equiv != 10_750_00


def test_soma_entao_aplica_bloqueia_b07():
    estudo = _estudo_minimo()
    policy = policy_completa(estrategia=RoundingStrategy.SOMA_ENTAO_APLICA)
    result = calcular(estudo, policy)
    assert result.tem_bloqueio
    assert "B-07" in result.codigos_bloqueio()
    assert not result.cenarios


def test_no_total_bloqueia_b07():
    estudo = _estudo_minimo()
    policy = policy_completa(estrategia=RoundingStrategy.NO_TOTAL)
    result = calcular(estudo, policy)
    assert result.tem_bloqueio
    assert "B-07" in result.codigos_bloqueio()
    assert not result.cenarios


def test_por_vida_entao_soma_operacional():
    estudo = _estudo_minimo()
    policy = policy_completa(estrategia=RoundingStrategy.POR_VIDA_ENTAO_SOMA)
    result = calcular(estudo, policy)
    assert not result.tem_bloqueio
    assert result.cenarios


def test_inclui_iof_preservado_exatamente_por_vida():
    valores = [(10_238_00, PriceBasis.INCLUI_IOF)]
    com_iof = apply_iof_strategy(valores, TF, IOF, RoundingStrategy.POR_VIDA_ENTAO_SOMA)
    assert int(com_iof[0]) == 10_238_00


def test_alvo_tipo_invalido_rejeitado():
    with pytest.raises(ValidationError):
        AtribuicaoPlano(
            id="a1",
            alvo_tipo="grupo",
            alvo_id="sg-1",
            opcao_plano_id="op-1",
        )


def test_primeira_parcela_reconcilia_no_motor():
    """Integração: 1ª parcela exclui_iof + recorrente inclui_iof + custos únicos."""
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 1, 1), None)
    op = opcao_plano(
        "op-1",
        tipo_fiscal=TipoFiscal.SEGURADORA,
        tabela_basis=PriceBasis.INCLUI_IOF,
        base=10_238_00,
        incremento=0,
        total_recorrente=10_238_00,
        total_recorrente_basis=PriceBasis.INCLUI_IOF,
        total_primeira=10_500_00,
        custos_unicos=[CustoUnico(id="cu1", descricao="Taxa", valor_centavos=500_00)],
    )
    op.total_primeira_parcela = ComponenteFinanceiro(
        centavos=10_500_00,
        price_basis=PriceBasis.EXCLUI_IOF,
        proveniencia=ProvenienciaCampo(origem=OrigemValor.MANUAL),
    )
    cenario = Cenario(
        id="c1",
        atribuicoes=[
            AtribuicaoPlano(id="a1", alvo_tipo="vida", alvo_id="v1", opcao_plano_id="op-1")
        ],
    )
    estudo = EstudoInput(
        id="estudo-111",
        formato=FormatoEstudo.NOVO,
        vidas=[v],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )
    policy = EffectivePolicy(data_referencia_idade=date(2026, 6, 30))
    result = calcular(estudo, policy)
    bloqueios_b02 = [
        v
        for v in result.validacoes
        if v.codigo == "B-02" and v.severidade == SeveridadeValidacao.BLOQUEANTE
    ]
    assert not bloqueios_b02, bloqueios_b02


def _estudo_minimo() -> EstudoInput:
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
        id="estudo-111-min",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )
