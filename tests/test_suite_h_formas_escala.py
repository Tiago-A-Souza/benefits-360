"""Suíte H — Formas, escala e proveniência."""

from datetime import date

from newport_motor.engine import calcular
from newport_motor.models import AtribuicaoPlano, Cenario, EstudoInput
from newport_motor.provenance import ProvenienciaCampo
from newport_motor.types import (
    FormatoEstudo,
    OrigemValor,
    RegimeCopartTipo,
    SeveridadeValidacao,
    TipoFiscal,
)
from tests.conftest import opcao_plano, policy_completa, regime, subgrupo_atual, vida_ficticia


def _estudo_n_vidas(n: int, copart: RegimeCopartTipo = RegimeCopartTipo.SEM):
    reg = regime(copart)
    vidas = [
        vida_ficticia(
            f"v{i}",
            date(1980 + (i % 30), 1, 1),
            "sg-1",
        )
        for i in range(n)
    ]
    op = opcao_plano("op-1", regime_id=reg.id)
    sg = subgrupo_atual()
    cenario = Cenario(
        id="c1",
        atribuicoes=[
            AtribuicaoPlano(id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1")
        ],
    )
    return EstudoInput(
        id=f"estudo-h-{n}",
        formato=FormatoEstudo.RENOVACAO,
        vidas=vidas,
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )


def test_escala_1_12_20_29_vidas():
    for n in (1, 12, 20, 29):
        result = calcular(_estudo_n_vidas(n), policy_completa())
        assert result.cenarios
        assert len(result.cenarios[0].secoes[0].subgrupos[0].vidas) == n


def test_b08_mais_de_29_vidas():
    result = calcular(_estudo_n_vidas(30), policy_completa(max_vidas_homologadas=29))
    assert "H-01" in [v.codigo for v in result.validacoes]
    assert "B-08" not in result.codigos_bloqueio()
    assert result.cenarios
    assert len(result.cenarios[0].secoes[0].subgrupos[0].vidas) == 30


def test_copart_sem_parcial_percentual():
    for copart in (RegimeCopartTipo.SEM, RegimeCopartTipo.PARCIAL, RegimeCopartTipo.PERCENTUAL):
        result = calcular(_estudo_n_vidas(3, copart), policy_completa())
        assert result.cenarios[0].secoes[0].regime_tipo == copart


def test_dois_planos():
    r1 = regime(RegimeCopartTipo.SEM, "a")
    r2 = regime(RegimeCopartTipo.PERCENTUAL, "b")
    sg1 = subgrupo_atual("sg-1")
    sg2 = subgrupo_atual("sg-2", operadora="SulAmerica")
    v1 = vida_ficticia("v1", date(1985, 1, 1), "sg-1")
    v2 = vida_ficticia("v2", date(1990, 1, 1), "sg-2")
    op1 = opcao_plano("op-1", regime_id=r1.id)
    op2 = opcao_plano("op-2", operadora="SulAmerica", regime_id=r2.id)
    cenario = Cenario(
        id="c1",
        atribuicoes=[
            AtribuicaoPlano(id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1"),
            AtribuicaoPlano(id="a2", alvo_tipo="subgrupo", alvo_id="sg-2", opcao_plano_id="op-2"),
        ],
    )
    estudo = EstudoInput(
        id="estudo-h-2planos",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v1, v2],
        subgrupos_atuais=[sg1, sg2],
        opcoes_plano=[op1, op2],
        regimes_copart=[r1, r2],
        cenarios=[cenario],
    )
    result = calcular(estudo, policy_completa())
    assert len(result.cenarios[0].secoes) == 2


def test_proveniencia_nos_valores_calculados():
    result = calcular(_estudo_n_vidas(1), policy_completa())
    valor = result.cenarios[0].secoes[0].subgrupos[0].vidas[0].proposta_centavos
    assert valor.proveniencia.origem == OrigemValor.CALCULADO
    assert valor.proveniencia.extrator_versao == "motor@0.1.2"


def test_b03_origem_ia_nao_confirmada():
    reg = regime(RegimeCopartTipo.SEM)
    v = vida_ficticia("v1", date(1990, 1, 1), "sg-1")
    op = opcao_plano("op-1")
    op.tabela[0].proveniencia = ProvenienciaCampo(origem=OrigemValor.IA, confirmado=False)
    sg = subgrupo_atual()
    cenario = Cenario(
        id="c1",
        atribuicoes=[
            AtribuicaoPlano(id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1")
        ],
    )
    estudo = EstudoInput(
        id="estudo-h-b03",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v],
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )
    result = calcular(estudo, policy_completa())
    assert "B-03" in result.codigos_bloqueio()
