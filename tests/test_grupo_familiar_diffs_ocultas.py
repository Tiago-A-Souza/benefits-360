"""Diferenças do grupo familiar ocultas por padrão — checkbox + CSS irmão.

Mesma técnica das colunas Tit./Dep.: zero JavaScript, um controle para a aba.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from newport_app.models.snapshot import GerarApresentacaoRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.formatacao import formatar_reais
from newport_app.presentation.html_renderer import (
    RENDERER_VERSAO,
    render_html,
    render_html_completo,
)
from newport_app.presentation.paridade_estrutural import assert_paridade_estrutural
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.hashing import hash_snapshot_canonico
from tests.test_correcao_resumo_regime import _aprovar as _aprovar_anistia
from tests.test_fase2_tarefa2 import _aprovar as _aprovar_stack
from tests.test_fase2_tarefa2 import _stack
from tests.test_frente2_grupo_familiar import (
    _GABARITO,
    _anistia_com_vinculos,
    _carimbar_vinculos_por_ordem,
    _ids_seis,
)
from tests.test_paridade_matriz_html import (
    _aprovar as _aprovar_matriz,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
)

_SCRIPT = re.compile(r"<script\b", re.IGNORECASE)
_CMP = (
    Path(__file__).resolve().parents[1]
    / "web"
    / "src"
    / "comparativo"
    / "ComparativoExperiencia.jsx"
)


def _html_completo_anistia(tmp_path: Path) -> tuple[str, object]:
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_anistia(tmp_path, rascunho)
    ids = _ids_seis()
    vm_r = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    vm_f = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    vm_g = construir_view_model(
        snap,
        modo="grupo_familiar",
        propostas_selecionadas=ids,
        beneficiarios_agregados=False,
    )
    return render_html_completo(vm_r, vm_f, vm_g), snap


def _tabelas_grupo(html: str) -> list[str]:
    return re.findall(
        r"<table class='tabela-grupo-familiar[^']*'>(.*?)</table>", html, flags=re.S
    )


def test_01_abre_sem_diferencas_visiveis(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert 'id="col-diffs"' in html
    assert "checked" not in html.split('id="col-diffs"')[1][:80]
    assert ".tabela-grupo-familiar .diff-vs-atual{display:none}" in html
    tabelas = _tabelas_grupo(html)
    assert tabelas
    for tab in tabelas:
        assert "diff-vs-atual" in tab


def test_02_um_controle_revela_todas_as_linhas(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert html.count('id="col-diffs"') == 1
    assert html.count('for="col-diffs"') == 1
    assert "#col-diffs:checked ~ * .tabela-grupo-familiar .diff-vs-atual{display:block}" in html
    assert len(_tabelas_grupo(html)) >= 1


def test_03_segundo_clique_oculta(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert '<input type="checkbox" id="col-diffs"' in html
    assert "ctrl-diffs-abrir" in html and "ctrl-diffs-fechar" in html
    assert "#col-diffs:checked ~ .ctrl-diffs .ctrl-diffs-abrir{display:none}" in html
    assert "#col-diffs:checked ~ .ctrl-diffs .ctrl-diffs-fechar{display:inline}" in html


def test_04_zero_javascript(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert _SCRIPT.search(html) is None
    assert "<script" not in html.lower()
    assert 'type="checkbox" id="col-diffs"' in html
    assert "#col-diffs:checked ~ * .tabela-grupo-familiar" in html


def test_05_vale_na_tela_e_na_impressao(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    benef = html.split('id="visao-benef"')[1]
    assert 'id="col-diffs"' in benef
    assert "grupo-familiar-tela" in html or "tabela-grupo-familiar" in html
    compacto = html.replace(" ", "")
    assert ".ctrl-diffs" in compacto and "display:none!important" in compacto
    bloco_print = html.split("@media print")[1].split("}", 8)[0]
    assert "diff-vs-atual" not in bloco_print


def test_06_valores_principais_permanecem(tmp_path: Path):
    html, snap = _html_completo_anistia(tmp_path)
    ids = _ids_seis()
    vm = construir_view_model(
        snap, modo="grupo_familiar", propostas_selecionadas=ids, beneficiarios_agregados=True
    )
    assert vm.totais_gerais.propostas
    for cents in vm.totais_gerais.propostas.values():
        if cents is None:
            continue
        assert formatar_reais(cents).replace("R$ ", "") in html
    if vm.totais_gerais.atual_centavos is not None:
        assert formatar_reais(vm.totais_gerais.atual_centavos).replace("R$ ", "") in html


def test_07_titdep_independente(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert 'id="col-titdep"' in html
    assert 'id="col-diffs"' in html
    faixas = html.split('id="visao-faixas"')[1].split('id="visao-benef"')[0]
    benef = html.split('id="visao-benef"')[1]
    assert 'id="col-titdep"' in faixas
    assert 'id="col-diffs"' not in faixas
    assert 'id="col-diffs"' in benef
    assert 'id="col-titdep"' not in benef
    assert "#col-titdep:checked ~ * .tabela-faixas th.col-titdep" in html
    assert "#col-diffs:checked ~ * .tabela-grupo-familiar .diff-vs-atual" in html


def test_08_subtotais_e_total_seguem_o_controle(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert "subtotal-grupo" in html
    assert "total-geral" in html
    for trecho in re.findall(
        r"<tr class='total-row[^']*'>(.*?)</tr>", html, flags=re.S
    ):
        if "diff-vs-atual" in trecho:
            assert "class='uni diff-vs-atual'" in trecho


def test_21_gabarito_anistia_intacto(tmp_path: Path):
    gab_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "paridade_matriz"
        / "gabarito_dois_planos.json"
    )
    gab = json.loads(gab_path.read_text(encoding="utf-8"))
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    _carimbar_vinculos_por_ordem(rascunho)
    snap = _aprovar_matriz(tmp_path, rascunho)
    matriz, _ = _calcular_matriz(rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    html_r = render_html(
        construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    )
    prata = next(s for s in gab["propostas"] if s["chave"] == "prata")
    assert prata["plano_a_centavos"] == _GABARITO["prata"][0] == 2_360_717
    assert prata["plano_b_centavos"] == _GABARITO["prata"][1] == 610_061
    assert gab["reajuste"]["1200"]["consolidado_centavos"] == _GABARITO["consolidado_proposta"] == 4_847_931
    assert "48.479,31" in html_r
    assert "23.607,17" in html_r
    assert "6.100,61" in html_r
    assert formatar_reais(_GABARITO["consolidado_proposta"]) == "R$ 48.479,31"


def test_22_hash_snapshot_inalterado(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_antes = hash_snapshot_canonico(nucleo_antes)
    repo, _, snap_svc, apres = _stack(tmp_path, "hash-diffs")
    snap = _aprovar_stack(repo, snap_svc, rascunho)
    assert snap.hash_sha256 == h_antes
    apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(modo="completo", propostas_selecionadas=_ids_seis()[:2]),
    )
    snap_depois = snap_svc.obter_snapshot(snap.id)
    assert snap_depois.hash_sha256 == h_antes
    _, nucleo_depois, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_depois = hash_snapshot_canonico(nucleo_depois)
    assert h_antes == h_depois
    print(f"HASH_ANTES={h_antes}")
    print(f"HASH_DEPOIS={h_depois}")


def test_24_paridade_estrutural_verde(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar_matriz(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="grupo_familiar", propostas_selecionadas=ids)
    assert_paridade_estrutural(matriz, vm, rascunho=rascunho)


def test_renderer_versao_patch():
    assert RENDERER_VERSAO == "html@2.13.8"
    src = _CMP.read_text(encoding="utf-8")
    assert "col-diffs" not in src
    assert "Ver diferenças contra o contrato atual" not in src


def test_modo_pagina_unica_tem_controle(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_anistia(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="grupo_familiar", propostas_selecionadas=_ids_seis()
    )
    html = render_html(vm)
    assert 'id="col-diffs"' in html
    assert _SCRIPT.search(html) is None
