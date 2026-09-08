"""Asserções de origem — coluna ↔ grade e metadado ↔ opção."""

from __future__ import annotations

from pathlib import Path

import pytest

from newport_app.draft_compiler import compile
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html
from newport_app.presentation.paridade_origem import divergencias_origem_completas
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from tests.gerador_celulas_estruturais import CelulaEstrutural, gerar_rascunho
from tests.test_paridade_matriz_html import (
    _aprovar,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
)


def _html_origem(snap, ids: list[str]) -> tuple[object, str]:
    vm_f = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    vm_r = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    return vm_f, render_html(vm_f) + render_html(vm_r)


@pytest.mark.parametrize(
    "celula",
    [
        CelulaEstrutural("renovacao", 2, 1, 2),
        CelulaEstrutural("renovacao", 2, 2, 3),
        CelulaEstrutural("renovacao", 3, 1, 3),
    ],
    ids=lambda c: c.nome,
)
def test_coluna_e_metadado_contra_origem(celula: CelulaEstrutural, tmp_path: Path):
    rascunho = gerar_rascunho(celula)
    sincronizar_cenarios(rascunho)
    matriz, motor = _calcular_matriz(rascunho)
    rc = compile(rascunho, policy_registry=default_registry)
    assert rc.compilavel and rc.compilado is not None
    snap = _aprovar(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm, html = _html_origem(snap, ids)
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
    assert not divs, "\n".join(divs)


def test_origem_gabarito_anistia_dois_planos(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz, motor = _calcular_matriz(rascunho)
    rc = compile(rascunho, policy_registry=default_registry)
    assert rc.compilavel and rc.compilado is not None
    snap = _aprovar(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm, html = _html_origem(snap, ids)
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
    assert not divs, "\n".join(divs)
