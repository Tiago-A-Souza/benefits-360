"""Bloco 2 — encurtamento de nomes de plano no documento."""

from __future__ import annotations

from pathlib import Path

from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.colisao_coluna import chave_de_coluna
from newport_app.presentation.html_renderer import render_html, render_html_completo
from newport_app.presentation.nome_plano_exibicao import encurtar_nome_plano_exibicao
from newport_app.presentation.tabela_densa import html_linhas_nome_plano_documento
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_paridade_matriz_html import _aprovar, _calcular_matriz


def test_encurtar_executivo_r1_apartamento_nacional():
    curto, abr = encurtar_nome_plano_exibicao("Executivo R1 Apartamento (Nacional)")
    assert curto == "Executivo R1"
    assert abr == "Nacional"


def test_encurtar_especial_e_ouro_mais_permanecem():
    assert encurtar_nome_plano_exibicao("Especial 100 R1") == ("Especial 100 R1", None)
    assert encurtar_nome_plano_exibicao("OURO MAIS I Q") == ("OURO MAIS I Q", None)


def test_documento_encurta_cabecalho_e_nota_cobertura(tmp_path: Path):
    rascunho = _rascunho_anistia_seis()
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [chave_de_coluna(p) for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    html = render_html(vm)
    assert html_linhas_nome_plano_documento(
        "Executivo R1 Apartamento (Nacional)"
    ) == "Executivo R1"
    assert "Executivo R1 Apartamento (Nacional)" not in html or "title=" in html
    assert "Executivo R1" in html
    assert "Abrangência de cobertura" in html
    assert "Executivo R1" in html.split("Abrangência de cobertura")[1]


def test_nome_completo_permanece_no_rascunho():
    rascunho = _rascunho_anistia_seis()
    op = next(o for o in rascunho.opcoes_proposta if o.id == "op-executivo")
    assert "Apartamento" in op.plano_nome
    assert encurtar_nome_plano_exibicao(op.plano_nome)[0] == "Executivo R1"


def test_completo_tres_abas_cabecalhos_encurtados(tmp_path: Path):
    rascunho = _rascunho_anistia_seis()
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [chave_de_coluna(p) for p in matriz.propostas if p.calculo_realizado]
    kwargs = dict(propostas_selecionadas=ids)
    vm_r = construir_view_model(snap, modo="resumo", **kwargs)
    vm_f = construir_view_model(snap, modo="faixas", **kwargs)
    vm_g = construir_view_model(
        snap, modo="grupo_familiar", beneficiarios_agregados=False, **kwargs
    )
    html = render_html_completo(vm_r, vm_f, vm_g)
    assert "Abrangência de cobertura" in html
    assert "Executivo R1" in html
    assert "OURO MAIS I Q" in html
