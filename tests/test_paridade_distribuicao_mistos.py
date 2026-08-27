"""Parte A — distribuição de atribuições (cenários mistos) + asserts da Parte B."""

from __future__ import annotations

from pathlib import Path

import pytest

from newport_app.draft_compiler import compile
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html
from newport_app.presentation.paridade_origem import divergencias_origem_completas
from newport_app.rascunho.cenarios_sync import (
    opcoes_usadas_nos_cenarios,
    propostas_fora_dos_cenarios,
)
from tests.gerador_celulas_estruturais import (
    CelulaDistribuicao,
    enumerar_celulas_distribuicao,
    gerar_rascunho_distribuicao,
)
from tests.test_paridade_matriz_html import _aprovar, _calcular_matriz


def test_contagem_celulas_distribuicao():
    dists = enumerar_celulas_distribuicao()
    assert len(dists) == 6
    assert {d.id for d in dists} == {
        "uniforme",
        "misto",
        "opcao_em_dois_cenarios",
        "opcao_nao_usada",
        "mais_cenarios_que_opcoes",
        "menos_cenarios_que_opcoes",
    }


@pytest.mark.parametrize(
    "dist",
    enumerar_celulas_distribuicao(),
    ids=lambda d: d.id,
)
def test_distribuicao_origem_e_invariantes(dist: CelulaDistribuicao, tmp_path: Path):
    rascunho = gerar_rascunho_distribuicao(dist)
    usadas = opcoes_usadas_nos_cenarios(rascunho)
    fora = propostas_fora_dos_cenarios(rascunho)
    n_cen = len(rascunho.cenarios)
    n_ops = len(rascunho.opcoes_proposta)

    if dist.id == "uniforme":
        assert n_cen == n_ops
        assert not fora
        assert len(usadas) == n_ops
    elif dist.id == "misto":
        assert n_cen == 1
        assert len(usadas) == 2
        atr_ops = {a.opcao_plano_id for a in rascunho.cenarios[0].atribuicoes}
        assert len(atr_ops) == 2
    elif dist.id == "opcao_em_dois_cenarios":
        assert n_cen == 2
        op0 = rascunho.opcoes_proposta[0].id
        assert all(
            any(a.opcao_plano_id == op0 for a in c.atribuicoes)
            for c in rascunho.cenarios
        )
        assert op0 in usadas
    elif dist.id == "opcao_nao_usada":
        assert fora
        assert rascunho.opcoes_proposta[-1].id in fora
    elif dist.id == "mais_cenarios_que_opcoes":
        assert n_cen > len(usadas)
        assert n_cen > 2
    elif dist.id == "menos_cenarios_que_opcoes":
        assert n_cen < n_ops
        assert len(usadas) < n_ops

    matriz, motor = _calcular_matriz(rascunho)
    rc = compile(rascunho, policy_registry=default_registry)
    assert rc.compilavel and rc.compilado is not None
    snap = _aprovar(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    assert set(ids) == set(usadas)

    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    html = render_html(vm)
    divs = divergencias_origem_completas(
        matriz=matriz,
        motor=motor,
        rascunho=rascunho,
        estudo=rc.compilado.estudo_input,
        policy=rc.compilado.effective_policy,
        vm=vm,
        html=html,
        opcao_ids=ids,
    )
    assert not divs, f"{dist.id}:\n" + "\n".join(divs)
