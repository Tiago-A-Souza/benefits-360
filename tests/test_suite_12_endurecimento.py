"""Suíte 1.2 — Endurecimento final do motor puro."""

from datetime import date

import pytest
from pydantic import ValidationError

from newport_motor.engine import calcular
from newport_motor.models import (
    AtribuicaoPlano,
    Cenario,
    CustoUnico,
    EstudoInput,
    OpcaoPlano,
    TabelaPrecoFaixa,
)
from newport_motor.policy import EffectivePolicy, TolerancePolicy
from newport_motor.provenance import ComponenteFinanceiro, ProvenienciaCampo
from newport_motor.types import (
    FormatoEstudo,
    OrigemValor,
    PriceBasis,
    RateBasisPoints,
    RegimeCopartTipo,
    SeveridadeValidacao,
    TipoFiscal,
)
from tests.conftest import opcao_plano, policy_completa, regime, subgrupo_atual, vida_ficticia


def _estudo_renovacao_minimo() -> EstudoInput:
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 1, 1), "sg-1")
    op = opcao_plano("op-1")
    sg = subgrupo_atual()
    c = Cenario(
        id="c1",
        atribuicoes=[
            AtribuicaoPlano(id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1")
        ],
    )
    return EstudoInput(
        id="estudo-12",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[c],
    )


def test_renovacao_sem_fatura_sem_faixa_bloqueia_b05():
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 1, 1), "sg-1", valor_fatura=None)
    sg = subgrupo_atual(tabela_atual=[])
    op = opcao_plano("op-1")
    est = EstudoInput(
        id="e",
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
    result = calcular(est, policy_completa())
    assert result.tem_bloqueio
    assert "B-05" in result.codigos_bloqueio()
    assert not result.cenarios


def test_fatura_zero_explicita_nao_confundida_com_ausencia():
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia(
        "v1",
        date(1990, 1, 1),
        "sg-1",
        valor_fatura=0,
        fatura_basis=PriceBasis.EXCLUI_IOF,
    )
    sg = subgrupo_atual(tabela_atual=[])
    op = opcao_plano("op-1")
    est = EstudoInput(
        id="e",
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
    result = calcular(est, policy_completa())
    bloqueios_b05_baseline = [
        v
        for v in result.validacoes
        if v.codigo == "B-05" and "baseline_atual" in (v.alvo_ref or "")
    ]
    assert not bloqueios_b05_baseline
    assert result.cenarios
    rv = result.cenarios[0].secoes[0].subgrupos[0].vidas[0]
    assert rv.atual_vigente_centavos.centavos == 0


def test_estudo_sem_cenarios_b06():
    reg = regime(RegimeCopartTipo.SEM)
    est = EstudoInput(
        id="e",
        formato=FormatoEstudo.NOVO,
        vidas=[vida_ficticia("v1", date(1990, 1, 1), None)],
        opcoes_plano=[opcao_plano("op-1")],
        regimes_copart=[reg],
        cenarios=[],
    )
    result = calcular(est, EffectivePolicy(data_referencia_idade=date(2026, 6, 30)))
    assert "B-06" in result.codigos_bloqueio()
    assert not result.cenarios


def test_estudo_sem_opcoes_b05():
    reg = regime(RegimeCopartTipo.SEM)
    est = EstudoInput(
        id="e",
        formato=FormatoEstudo.NOVO,
        vidas=[vida_ficticia("v1", date(1990, 1, 1), None)],
        opcoes_plano=[],
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
    result = calcular(est, EffectivePolicy(data_referencia_idade=date(2026, 6, 30)))
    assert "B-05" in result.codigos_bloqueio()


def test_cenario_vazio_b06():
    reg = regime(RegimeCopartTipo.SEM)
    est = EstudoInput(
        id="e",
        formato=FormatoEstudo.NOVO,
        vidas=[vida_ficticia("v1", date(1990, 1, 1), None)],
        opcoes_plano=[opcao_plano("op-1")],
        regimes_copart=[reg],
        cenarios=[Cenario(id="c1", atribuicoes=[])],
    )
    result = calcular(est, EffectivePolicy(data_referencia_idade=date(2026, 6, 30)))
    assert "B-06" in result.codigos_bloqueio()


def test_nascimento_futuro_b05_sem_excecao():
    reg = regime(RegimeCopartTipo.SEM)
    est = EstudoInput(
        id="e",
        formato=FormatoEstudo.NOVO,
        vidas=[vida_ficticia("v1", date(2027, 1, 1), None)],
        opcoes_plano=[opcao_plano("op-1")],
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
    result = calcular(est, EffectivePolicy(data_referencia_idade=date(2026, 6, 30)))
    assert "B-05" in result.codigos_bloqueio()
    assert not result.cenarios


@pytest.mark.parametrize(
    "campo, fabrica",
    [
        (
            "vidas",
            lambda: EstudoInput(
                id="e",
                formato=FormatoEstudo.NOVO,
                vidas=[
                    vida_ficticia("v1", date(1990, 1, 1), None),
                    vida_ficticia("v1", date(1985, 1, 1), None),
                ],
            ),
        ),
        (
            "subgrupos_atuais",
            lambda: EstudoInput(
                id="e",
                formato=FormatoEstudo.RENOVACAO,
                vidas=[vida_ficticia("v1", date(1990, 1, 1), "sg-1")],
                subgrupos_atuais=[subgrupo_atual("sg-1"), subgrupo_atual("sg-1")],
            ),
        ),
        (
            "opcoes_plano",
            lambda: EstudoInput(
                id="e",
                formato=FormatoEstudo.NOVO,
                vidas=[vida_ficticia("v1", date(1990, 1, 1), None)],
                opcoes_plano=[opcao_plano("op-1"), opcao_plano("op-1")],
            ),
        ),
        (
            "cenarios",
            lambda: EstudoInput(
                id="e",
                formato=FormatoEstudo.NOVO,
                vidas=[vida_ficticia("v1", date(1990, 1, 1), None)],
                cenarios=[Cenario(id="c1"), Cenario(id="c1")],
            ),
        ),
        (
            "regimes_copart",
            lambda: EstudoInput(
                id="e",
                formato=FormatoEstudo.NOVO,
                vidas=[vida_ficticia("v1", date(1990, 1, 1), None)],
                regimes_copart=[regime(RegimeCopartTipo.SEM), regime(RegimeCopartTipo.SEM)],
            ),
        ),
    ],
)
def test_ids_duplicados_rejeitados(campo, fabrica):
    with pytest.raises(ValidationError, match=f"ID duplicado em {campo}"):
        fabrica()


def test_componente_financeiro_negativo_rejeitado():
    with pytest.raises(ValidationError, match="centavos não pode ser negativo"):
        ComponenteFinanceiro(centavos=-100, price_basis=PriceBasis.EXCLUI_IOF)


def test_policy_iof_bps_negativo_rejeitado():
    with pytest.raises(ValidationError, match="iof_bps não pode ser negativo"):
        EffectivePolicy(
            data_referencia_idade=date(2026, 6, 30),
            iof_bps=RateBasisPoints(-1),
        )


def test_tolerancia_negativa_rejeitada():
    with pytest.raises(ValidationError, match="tolerância não pode ser negativa"):
        TolerancePolicy(por_vida_centavos=-1)


def test_reajuste_negativo_b07():
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 1, 1), "sg-1")
    sg = subgrupo_atual(reajuste_bps=-500)
    op = opcao_plano("op-1")
    est = EstudoInput(
        id="e",
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
    result = calcular(est, policy_completa())
    assert "B-07" in result.codigos_bloqueio()
    assert not result.cenarios


def test_primeira_parcela_menor_que_custos_b02_claro():
    reg = regime(RegimeCopartTipo.SEM)
    op = opcao_plano(
        "op-1",
        tabela_basis=PriceBasis.INCLUI_IOF,
        base=10_238_00,
        incremento=0,
        total_recorrente=10_238_00,
        total_recorrente_basis=PriceBasis.INCLUI_IOF,
        total_primeira=300_00,
        custos_unicos=[CustoUnico(id="cu", descricao="Taxa", valor_centavos=500_00)],
    )
    op.total_primeira_parcela = ComponenteFinanceiro(
        centavos=300_00,
        price_basis=PriceBasis.EXCLUI_IOF,
        proveniencia=ProvenienciaCampo(origem=OrigemValor.MANUAL),
    )
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
    result = calcular(est, EffectivePolicy(data_referencia_idade=date(2026, 6, 30)))
    msgs = [
        v.mensagem
        for v in result.validacoes
        if v.codigo == "B-02" and v.severidade == SeveridadeValidacao.BLOQUEANTE
    ]
    assert any("menor que a soma dos custos" in m for m in msgs)


def test_fatura_ia_nao_confirmada_b03():
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 1, 1), "sg-1", valor_fatura=80_000)
    v.fatura_proveniencia = ProvenienciaCampo(origem=OrigemValor.IA, confirmado=False)
    est = _estudo_renovacao_minimo()
    est.vidas = [v]
    result = calcular(est, policy_completa())
    assert "B-03" in result.codigos_bloqueio()


def test_tabela_atual_ia_nao_confirmada_b03():
    reg = regime(RegimeCopartTipo.SEM)
    tabela = [
        TabelaPrecoFaixa(
            faixa=f,
            valor_centavos=80_000 + f * 8_000,
            price_basis=PriceBasis.EXCLUI_IOF,
            proveniencia=ProvenienciaCampo(origem=OrigemValor.IA, confirmado=False),
        )
        for f in range(10)
    ]
    est = _estudo_renovacao_minimo()
    est.subgrupos_atuais = [subgrupo_atual(tabela_atual=tabela)]
    result = calcular(est, policy_completa())
    assert "B-03" in result.codigos_bloqueio()


def test_saida_preserva_linhagem_fatura_tabela_proposta():
    est = _estudo_renovacao_minimo()
    result = calcular(est, policy_completa())
    assert not result.tem_bloqueio
    rv = result.cenarios[0].secoes[0].subgrupos[0].vidas[0]
    assert rv.proposta_centavos.proveniencia.origem == OrigemValor.CALCULADO
    assert any("opcao:op-1:tabela:faixa:" in f.alvo_ref for f in rv.proposta_centavos.fontes)
    assert rv.atual_vigente_centavos.proveniencia.origem == OrigemValor.CALCULADO
    assert any(
        "subgrupo:sg-1:tabela_atual:faixa:" in f.alvo_ref
        for f in rv.atual_vigente_centavos.fontes
    )
    assert rv.diff_mes_centavos is not None
    assert len(rv.diff_mes_centavos.fontes) >= 1
