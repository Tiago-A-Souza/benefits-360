"""FASE 6 — grupo familiar por grupo de beneficiários."""

from __future__ import annotations

import json
import re
from pathlib import Path

from newport_app.presentation.builder import MAX_PROPOSTAS_POR_PAGINA, construir_view_model
from newport_app.presentation.colisao_coluna import chave_de_coluna, id_coluna_vm
from newport_app.presentation.html_renderer import render_html
from newport_app.presentation.paridade_estrutural import divergencias_estruturais
from newport_app.presentation.paridade_html import divergencias_html_vm
from newport_app.presentation.tabela_densa import ids_do_grupo, planos_das_faixas
from tests.test_apresentacao_seguro_novo import _rascunho_ivtec_novo
from tests.test_correcao_resumo_regime import _ids
from tests.test_frente2_grupo_familiar import (
    _GABARITO,
    _anistia_com_vinculos,
    _carimbar_vinculos_por_ordem,
)
from tests.test_paridade_matriz_html import (
    _GABARITO as _GABARITO_DOIS,
    _aprovar,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
)

_SCRIPT = re.compile(r"<script\b", re.IGNORECASE)
_SINAL_DIVIDIDA = "também em outro grupo"


def _vm_html(tmp_path: Path, rascunho, *, modo: str = "grupo_familiar", agregados: bool = False):
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [chave_de_coluna(p) for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(
        snap,
        modo=modo,
        propostas_selecionadas=ids,
        beneficiarios_agregados=agregados,
    )
    return vm, render_html(vm), ids


def _tela_gf(html: str) -> str:
    wrap = re.search(
        r"<div class='grupo-familiar-tela'>(.*?)</div>\s*<div class='grupo-familiar-impressao'",
        html,
        flags=re.S,
    )
    if wrap:
        return wrap.group(1)
    m = re.search(
        r"<div class='layout-tela'>(.*?)</div>\s*<div class='layout-impressao'>",
        html,
        flags=re.S,
    )
    if m:
        return m.group(1)
    return html


def _tabelas_gf(html: str) -> list[str]:
    return re.findall(
        r"<table class='[^']*tabela-grupo-familiar[^']*'>(.*?)</table>",
        _tela_gf(html),
        flags=re.S,
    )


def _cruzar_familia(rascunho):
    """Titular num grupo, um dependente no outro — a família atravessa subgrupos."""
    sgs = [s.id for s in rascunho.subgrupos_atuais]
    assert len(sgs) >= 2
    por_chave: dict[str, list] = {}
    for v in rascunho.vidas:
        chave = v.vinculo_grupo_chave or ""
        por_chave.setdefault(chave, []).append(v)
    for membros in por_chave.values():
        titular = next(
            (v for v in membros if v.parentesco and str(v.parentesco.value).lower() == "titular"),
            None,
        )
        deps = [v for v in membros if v is not titular]
        if titular is None or not deps:
            continue
        outro = next((s for s in sgs if s != titular.subgrupo_atual_id), None)
        if outro is None:
            continue
        deps[0].subgrupo_atual_id = outro
        return titular, deps[0]
    raise AssertionError("nenhuma família com dependente para cruzar")


def test_01_dois_grupos_duas_secoes(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    vm, html, _ = _vm_html(tmp_path, rascunho)
    planos = planos_das_faixas(vm, seguro_novo=False)
    assert len(planos) == 2
    tela = _tela_gf(html)
    assert tela.count("<div class='grupo-cab'") == 2
    assert len(_tabelas_gf(html)) == 2
    for pl in planos:
        assert pl.plano_nome in html


def test_02_secao_so_planos_do_grupo(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    vm, html, ids = _vm_html(tmp_path, rascunho)
    for pl in planos_das_faixas(vm, seguro_novo=False):
        ids_g = ids_do_grupo(vm, ids, pl)
        for oid in ids:
            prop = next(
                p
                for s in vm.secoes_regime
                for p in s.propostas
                if id_coluna_vm(p) == oid
            )
            atribuidos = prop.nomes_atribuidos_por_subgrupo
            if atribuidos and pl.subgrupo_id not in atribuidos:
                assert oid not in ids_g
            else:
                assert oid in ids_g
    del html


def test_03_secao_so_familias_do_grupo(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    vm, html, _ = _vm_html(tmp_path, rascunho)
    for tab, pl in zip(_tabelas_gf(html), planos_das_faixas(vm, seguro_novo=False)):
        nomes = {m.nome for g in vm.grupos_familiares for m in g.membros if m.subgrupo_id == pl.subgrupo_id}
        fora = {m.nome for g in vm.grupos_familiares for m in g.membros if m.subgrupo_id != pl.subgrupo_id}
        for nome in nomes:
            assert f">{nome}</td>" in tab
        for nome in fora:
            assert f">{nome}</td>" not in tab


def test_04_soma_secoes_igual_vidas_do_estudo(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    vm, html, _ = _vm_html(tmp_path, rascunho)
    totais = [int(n) for n in re.findall(r"Total (\d+) Vidas", _tela_gf(html))]
    assert sum(totais) == sum(len(g.membros) for g in vm.grupos_familiares) == 41


def test_05_subtotal_so_multiplos_no_grupo(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    vm, html, _ = _vm_html(tmp_path, rascunho)
    esperado = 0
    for pl in planos_das_faixas(vm, seguro_novo=False):
        for g in vm.grupos_familiares:
            n = sum(1 for m in g.membros if m.subgrupo_id == pl.subgrupo_id)
            if n > 1:
                esperado += 1
    assert _tela_gf(html).count("Sub Total ") == esperado


def test_06_ordem_alfabetica_por_titular(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    for i, v in enumerate(rascunho.vidas):
        if v.parentesco and str(v.parentesco.value).lower() == "titular":
            v.nome = f"Titular {chr(65 + (i % 26))}{i:02d}"
        else:
            v.nome = f"Dependente {i:02d}"
    vm, html, _ = _vm_html(tmp_path, rascunho)
    for pl in planos_das_faixas(vm, seguro_novo=False):
        rotulos = [
            g.rotulo
            for g in vm.grupos_familiares
            if any(m.subgrupo_id == pl.subgrupo_id for m in g.membros)
            and not g.sem_vinculo_resolvido
        ]
        assert rotulos == sorted(rotulos, key=str.casefold)
    del html


def test_07_mockup_mesma_estrutura(tmp_path: Path):
    mockup = (
        Path(__file__).resolve().parents[1] / "docs" / "grupo-familiar-por-grupo.html"
    ).read_text(encoding="utf-8")
    assert mockup.count('class="grupo-cab"') == 2
    rascunho = _anistia_com_vinculos()
    _, html, _ = _vm_html(tmp_path, rascunho)
    tela = _tela_gf(html)
    assert tela.count("<div class='grupo-cab'") == 2
    assert "Sub Total " in tela
    assert "Total " in tela


def test_08_familia_dividida_aparece_nas_duas(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    titular, dep = _cruzar_familia(rascunho)
    vm, html, _ = _vm_html(tmp_path, rascunho)
    tabelas = _tabelas_gf(html)
    assert len(tabelas) == 2
    assert sum(1 for tab in tabelas if f">{titular.nome}</td>" in tab) == 1
    assert sum(1 for tab in tabelas if f">{dep.nome}</td>" in tab) == 1
    assert _SINAL_DIVIDIDA in html
    familia = next(
        g
        for g in vm.grupos_familiares
        if any(m.vida_id == titular.id for m in g.membros)
    )
    assert {m.subgrupo_id for m in familia.membros} == {
        titular.subgrupo_atual_id,
        dep.subgrupo_atual_id,
    }


def test_09_subtotal_de_cada_pedaco(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    titular, dep = _cruzar_familia(rascunho)
    vm, html, _ = _vm_html(tmp_path, rascunho)
    familia = next(
        g
        for g in vm.grupos_familiares
        if any(m.vida_id == titular.id for m in g.membros)
    )
    for tab, pl in zip(_tabelas_gf(html), planos_das_faixas(vm, seguro_novo=False)):
        n = sum(1 for m in familia.membros if m.subgrupo_id == pl.subgrupo_id)
        if n > 1:
            assert f"Sub Total {familia.rotulo}" in tab
        elif n == 1:
            # o pedaço de uma pessoa não ganha subtotal próprio, só o sinal
            pass
    del titular, dep


def test_10_cabecalho_sinaliza_familia_dividida(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    _cruzar_familia(rascunho)
    _, html, _ = _vm_html(tmp_path, rascunho)
    assert "familia-dividida" in html
    assert _SINAL_DIVIDIDA in html


def test_11_soma_partes_igual_vidas_da_familia(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    titular, dep = _cruzar_familia(rascunho)
    vm, html, _ = _vm_html(tmp_path, rascunho)
    familia = next(
        g
        for g in vm.grupos_familiares
        if any(m.vida_id == titular.id for m in g.membros)
    )
    n_html = sum(
        tab.count(f">{m.nome}</td>")
        for tab in _tabelas_gf(html)
        for m in familia.membros
    )
    assert n_html == len(familia.membros)
    totais = [int(n) for n in re.findall(r"Total (\d+) Vidas", _tela_gf(html))]
    assert sum(totais) == sum(len(g.membros) for g in vm.grupos_familiares)
    del dep


def test_12_versao_sem_nomes(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    for i, v in enumerate(rascunho.vidas):
        v.nome = f"Pessoa Segredo {i}"
    vm, html, _ = _vm_html(tmp_path, rascunho, agregados=True)
    for v in rascunho.vidas:
        assert v.nome not in html
    assert vm.grupos_familiares[0].rotulo == "Grupo 1"
    assert "Grupo 1" in html
    assert "Sub Total Grupo" in html
    assert " · titular" in html or " · cônjuge" in html
    assert "Membro" in html


def test_13_sem_vinculo_resolvido(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    rascunho.vidas[0].vinculo_grupo_chave = None
    vm, html, _ = _vm_html(tmp_path, rascunho)
    orfaos = [g for g in vm.grupos_familiares if g.sem_vinculo_resolvido]
    assert len(orfaos) == 1
    assert len(orfaos[0].membros) == 1
    assert "sem vínculo resolvido" not in html
    assert html.count("tr class='grupo-cab'") == 0


def test_14_zero_script(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    _, html, _ = _vm_html(tmp_path, rascunho)
    assert _SCRIPT.search(html) is None


def test_15_paridade_matriz_documento(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    matriz, _ = _calcular_matriz(rascunho)
    vm, html, ids = _vm_html(tmp_path, rascunho)
    assert not divergencias_estruturais(matriz, vm, rascunho=rascunho)
    assert not divergencias_html_vm(vm, html)
    del ids


def test_17_gabaritos(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    vm, html, _ = _vm_html(tmp_path, rascunho, modo="resumo")
    assert vm.totais_gerais.atual_centavos in (
        _GABARITO["consolidado_atual"],
        4_847_931,
    )
    assert "48.479,31" in html
    r2 = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz, _ = _calcular_matriz(r2)
    snap = _aprovar(tmp_path / "g", r2)
    ids = [chave_de_coluna(p) for p in matriz.propostas if p.calculo_realizado]
    vm2 = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    gab = json.loads(_GABARITO_DOIS.read_text(encoding="utf-8"))
    from tests.test_paridade_matriz_html import assert_gabarito_propostas

    assert_gabarito_propostas(matriz, vm2, gab)
    assert vm2.totais_gerais.atual_centavos == 4_847_931
    r_n = _rascunho_ivtec_novo()
    _carimbar_vinculos_por_ordem(r_n)
    snap_n = _aprovar(tmp_path / "n", r_n)
    vm_n = construir_view_model(
        snap_n, modo="grupo_familiar", propostas_selecionadas=_ids(snap_n)
    )
    assert vm_n.totais_gerais.propostas["op-bronze"] == 374_189
    assert vm_n.totais_gerais.propostas["op-prata"] == 565_204


def test_21_um_vigente_uma_secao(tmp_path: Path):
    from newport_app.seed.ficticio import rascunho_demo_12_vidas

    rascunho = rascunho_demo_12_vidas()
    _carimbar_vinculos_por_ordem(rascunho)
    vm, html, _ = _vm_html(tmp_path, rascunho)
    assert len(planos_das_faixas(vm, seguro_novo=False)) == 1
    assert _tela_gf(html).count("<div class='grupo-cab'") == 1
    assert len(_tabelas_gf(html)) == 1


def test_22_seguro_novo(tmp_path: Path):
    rascunho = _rascunho_ivtec_novo()
    _carimbar_vinculos_por_ordem(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = _ids(snap)
    vm = construir_view_model(snap, modo="grupo_familiar", propostas_selecionadas=ids)
    html = render_html(vm)
    assert "<div class='grupo-cab'" not in html
    assert "tabela-grupo-familiar" in html
    assert MAX_PROPOSTAS_POR_PAGINA == 3
    assert vm.totais_gerais.propostas["op-bronze"] == 374_189
