"""Frente 1 — indicadores do resumo executivo no documento = matriz."""

from __future__ import annotations

from pathlib import Path

import pytest

from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html
from newport_app.presentation.indicadores_resumo import (
    AUSENCIA,
    divergencias_indicadores_resumo,
    rotulos_indicadores_html,
    rotulos_indicadores_matriz,
    rotulos_indicadores_vm,
)
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from tests.test_comparativo_seguro_novo import _rascunho_ivtec_novo
from tests.test_paridade_matriz_html import (
    _aprovar,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
)


def _resumo(tmp: Path, rascunho):
    sincronizar_cenarios(rascunho)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    return matriz, vm, render_html(vm), ids


def test_01_renovacao_mesmos_indicadores_matriz_documento(tmp_path: Path):
    matriz, vm, html, _ = _resumo(
        tmp_path, _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    )
    assert not divergencias_indicadores_resumo(matriz=matriz, vm=vm, html=html)
    for rotulo in (
        "Acomodação",
        "Coparticipação",
        "Custo total mensal",
        "Variação do custo",
        "Validade da cotação",
    ):
        assert rotulo in rotulos_indicadores_html(html)
        assert rotulo in rotulos_indicadores_matriz(matriz)


def test_02_seguro_novo_indicadores_aplicaveis(tmp_path: Path):
    matriz, vm, html, _ = _resumo(tmp_path, _rascunho_ivtec_novo())
    assert not divergencias_indicadores_resumo(matriz=matriz, vm=vm, html=html)
    for rotulo in (
        "Acomodação",
        "Coparticipação",
        "Custo total mensal",
        "Validade da cotação",
    ):
        assert rotulo in html


def test_03_anistia_custo_variacao_validade_por_coluna(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    # Validade explícita nas opções
    for op in rascunho.opcoes_proposta:
        assert op.validade_oficial is not None
    _, vm, html, ids = _resumo(tmp_path, rascunho)
    assert "Custo total mensal" in html
    assert "Variação do custo" in html
    assert "Validade da cotação" in html
    # Valores Anistia 12%
    assert "48.479,31" in html
    assert "23.607,17" in html
    assert "6.100,61" in html
    for secao in vm.secoes_regime:
        validade = next(
            (i for i in secao.indicadores_resumo if i.rotulo == "Validade da cotação"),
            None,
        )
        if validade is None:
            continue
        for oid in ids:
            if oid not in validade.propostas:
                continue
            cel = validade.propostas[oid]
            assert not cel.ausente
            assert cel.texto  # data formatada
    assert any(
        oid in i.propostas and not i.propostas[oid].ausente
        for s in vm.secoes_regime
        for i in s.indicadores_resumo
        if i.rotulo == "Validade da cotação"
        for oid in ids
    )

def test_04_acomodacao_ausente_aparece_como_ausente(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    for pl in rascunho.subgrupos_atuais:
        pl.acomodacao = None
    for op in rascunho.opcoes_proposta:
        op.acomodacao = None
    _, vm, html, _ = _resumo(tmp_path, rascunho)
    assert "Acomodação" in html
    # Documento comunica ausência como a matriz («—»), não zero.
    assert AUSENCIA in html
    assert "Acomodação</td><td class='atual'>0</td>" not in html
    for secao in vm.secoes_regime:
        lin = next(i for i in secao.indicadores_resumo if i.rotulo == "Acomodação")
        assert lin.atual is not None and lin.atual.ausente
        for cel in lin.propostas.values():
            assert cel.ausente
            assert cel.texto == AUSENCIA


def test_05_assert_falha_quando_indicador_removido_do_documento(tmp_path: Path):
    from newport_app.presentation import html_renderer

    matriz, vm, html_ok, _ = _resumo(
        tmp_path, _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    )
    assert not divergencias_indicadores_resumo(matriz=matriz, vm=vm, html=html_ok)

    orig = html_renderer._render_resumo

    def wrapped(model, secao, rotulos, op_ids, *, seguro_novo):
        # Remove um indicador do VM antes de renderizar.
        secao = secao.model_copy(
            update={
                "indicadores_resumo": [
                    i
                    for i in secao.indicadores_resumo
                    if i.rotulo != "Validade da cotação"
                ]
            }
        )
        return orig(model, secao, rotulos, op_ids, seguro_novo=seguro_novo)

    html_renderer._render_resumo = wrapped  # type: ignore[assignment]
    try:
        html_mut = render_html(vm)
    finally:
        html_renderer._render_resumo = orig

    divs = divergencias_indicadores_resumo(matriz=matriz, html=html_mut)
    assert divs, "remover Validade deveria acusar divergência de indicadores"
    assert any("Validade" in d or "só_matriz" in d for d in divs)
    assert "Validade da cotação" not in rotulos_indicadores_html(html_mut)
