"""Suíte 1.2.2 — Escopo de vidas: B-08, H-01 e max_vidas_homologadas na policy."""

from __future__ import annotations

from datetime import date

from newport_motor.engine import calcular
from newport_motor.models import AtribuicaoPlano, Cenario, EstudoInput
from newport_motor.types import (
    FormatoEstudo,
    RegimeCopartTipo,
    SeveridadeValidacao,
)
from tests.conftest import opcao_plano, policy_completa, regime, subgrupo_atual, vida_ficticia


def _estudo_n_vidas(n: int, incluidas: bool = True) -> EstudoInput:
    reg = regime(RegimeCopartTipo.SEM)
    vidas = [
        vida_ficticia(
            f"v{i}",
            date(1980 + (i % 30), 1, 1),
            "sg-1",
            incluida=incluidas,
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
        id=f"estudo-122-{n}",
        formato=FormatoEstudo.RENOVACAO,
        vidas=vidas,
        subgrupos_atuais=[sg],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )


def _count_resultado_vidas(result) -> int:
    return len(result.cenarios[0].secoes[0].subgrupos[0].vidas)


def test_b08_zero_vidas_bloqueia_sem_calculo():
    estudo = _estudo_n_vidas(3, incluidas=False)
    result = calcular(estudo, policy_completa())
    assert "B-08" in result.codigos_bloqueio()
    assert not result.cenarios


def test_faixa_homologada_1_e_29_sem_h01():
    for n in (1, 29):
        result = calcular(_estudo_n_vidas(n), policy_completa(max_vidas_homologadas=29))
        assert result.cenarios
        assert _count_resultado_vidas(result) == n
        assert "H-01" not in [v.codigo for v in result.validacoes]
        assert "B-08" not in result.codigos_bloqueio()


def test_acima_faixa_homologada_calcula_com_h01():
    for n in (30, 41, 100):
        estudo = _estudo_n_vidas(n)
        result = calcular(estudo, policy_completa(max_vidas_homologadas=29))
        assert result.cenarios
        assert _count_resultado_vidas(result) == n
        assert len(estudo.vidas_incluidas()) == n
        h01 = [v for v in result.validacoes if v.codigo == "H-01"]
        assert len(h01) == 1
        assert h01[0].severidade == SeveridadeValidacao.ALERTA
        assert "B-08" not in result.codigos_bloqueio()
        assert not result.tem_bloqueio


def test_max_vidas_homologadas_none_sem_h01():
    result = calcular(_estudo_n_vidas(100), policy_completa(max_vidas_homologadas=None))
    assert result.cenarios
    assert _count_resultado_vidas(result) == 100
    assert "H-01" not in [v.codigo for v in result.validacoes]


def test_determinismo_escopo_vidas():
    estudo = _estudo_n_vidas(41)
    policy = policy_completa(max_vidas_homologadas=29)
    r1 = calcular(estudo, policy)
    r2 = calcular(estudo, policy)
    assert r1.model_dump() == r2.model_dump()


def test_nenhuma_vida_removida_ou_truncada():
    estudo = _estudo_n_vidas(41)
    assert len(estudo.vidas) == 41
    assert len(estudo.vidas_incluidas()) == 41
    result = calcular(estudo, policy_completa(max_vidas_homologadas=29))
    assert len(estudo.vidas) == 41
    assert len(estudo.vidas_incluidas()) == 41
    assert _count_resultado_vidas(result) == 41


def test_max_vidas_homologadas_na_politica_efetiva():
    result = calcular(_estudo_n_vidas(30), policy_completa(max_vidas_homologadas=29))
    assert result.politicas_efetivas["max_vidas_homologadas"] == 29
