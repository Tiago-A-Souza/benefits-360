"""FASE 5 — faixas etárias por grupo de beneficiários."""

from __future__ import annotations

import json
import re
from pathlib import Path

from newport_app.presentation.builder import MAX_PROPOSTAS_POR_PAGINA, construir_view_model
from newport_app.presentation.colisao_coluna import chave_de_coluna, id_coluna_vm
from newport_app.presentation.html_renderer import render_html
from newport_app.presentation.paridade_estrutural import divergencias_estruturais
from newport_app.presentation.paridade_html import divergencias_html_vm
from newport_app.models.draft import AtribuicaoRascunho, CenarioRascunho
from newport_app.presentation.tabela_densa import (
    chunks_propostas,
    ids_do_grupo,
    montar_blocos,
    planos_das_faixas,
)
from tests.test_apresentacao_seguro_novo import _rascunho_ivtec_novo
from tests.test_correcao_resumo_regime import _ids
from tests.test_faixas_colunas_ocultas import _html_completo_anistia
from tests.test_paridade_matriz_html import (
    _GABARITO,
    _aprovar,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
    assert_gabarito_propostas,
)

_SCRIPT = re.compile(r"<script\b", re.IGNORECASE)


def _vm_html(tmp_path: Path, rascunho, *, modo: str = "faixas"):
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [chave_de_coluna(p) for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo=modo, propostas_selecionadas=ids)
    return vm, render_html(vm), ids


def _tabelas_faixas(html: str) -> list[str]:
    tela = re.search(
        r"<div class='layout-tela'>(.*?)</div>\s*<div class='layout-impressao'>",
        html,
        flags=re.S,
    )
    bloco = tela.group(1) if tela else html
    return re.findall(
        r"<table class='[^']*tabela-faixas[^']*'>(.*?)</table>", bloco, flags=re.S
    )


def test_01_dois_grupos_duas_secoes(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    vm, html, _ = _vm_html(tmp_path, rascunho)
    planos = planos_das_faixas(vm, seguro_novo=False)
    assert len(planos) == 2
    assert _tabelas_faixas(html)
    tela = re.search(
        r"<div class='layout-tela'>(.*?)</div>\s*<div class='layout-impressao'>",
        html,
        flags=re.S,
    )
    bloco = tela.group(1) if tela else html
    assert bloco.count("class='grupo-cab'") == 2
    assert len(_tabelas_faixas(html)) == 2
    for pl in planos:
        assert pl.plano_nome in html


def test_02_secao_so_planos_do_grupo(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    vm, html, ids = _vm_html(tmp_path, rascunho)
    planos = planos_das_faixas(vm, seguro_novo=False)
    assert len(planos) == 2
    for pl in planos:
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


def test_03_faixas_sem_vidas_nao_aparecem(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    vm, html, _ = _vm_html(tmp_path, rascunho)
    for tab, pl in zip(_tabelas_faixas(html), planos_das_faixas(vm, seguro_novo=False)):
        ocupadas = {fx.rotulo for fx in pl.faixas if fx.qtd_total > 0}
        vazias = {fx.rotulo for fx in pl.faixas if fx.qtd_total == 0}
        for rot in ocupadas:
            assert rot in tab
        for rot in vazias:
            assert f"data-fx='{rot}'" not in tab


def test_04_acomodacao_e_modalidade_no_topo(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    _, html, _ = _vm_html(tmp_path, rascunho)
    for tab in _tabelas_faixas(html):
        assert "Acomodação" in tab
        assert "Modalidade" in tab


def test_04b_acomodacao_por_grupo_nao_agrega_cenario(tmp_path: Path):
    """Cenário misto: resumo agrega «misto»; seção do grupo usa o plano daquele grupo."""
    from tests.test_correcao_resumo_regime import _rascunho_anistia_seis

    rascunho = _rascunho_anistia_seis()
    for op in rascunho.opcoes_proposta:
        if op.id == "op-executivo":
            op.acomodacao = None
    rascunho.cenarios = [
        CenarioRascunho(
            id="c-misto",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a-sga",
                    alvo_tipo="subgrupo",
                    alvo_id="sg-a",
                    opcao_plano_id="op-prata",
                ),
                AtribuicaoRascunho(
                    id="a-sgb",
                    alvo_tipo="subgrupo",
                    alvo_id="sg-b",
                    opcao_plano_id="op-executivo",
                ),
            ],
        )
    ]
    matriz, _ = _calcular_matriz(rascunho)
    assert matriz.propostas[0].acomodacao == "misto"
    vm, html, ids = _vm_html(tmp_path, rascunho)
    planos = planos_das_faixas(vm, seguro_novo=False)
    s750 = next(p for p in planos if p.subgrupo_id == "sg-a")
    one = next(p for p in planos if p.subgrupo_id == "sg-b")
    blocos_s750 = montar_blocos(
        vm, ids_do_grupo(vm, ids, s750), seguro_novo=False, plano=s750
    )
    blocos_one = montar_blocos(
        vm, ids_do_grupo(vm, ids, one), seguro_novo=False, plano=one
    )
    prop_bloco = next(b for b in blocos_s750 if not b.atual)
    assert prop_bloco.acomodacao == "Apartamento"
    prop_one = next(b for b in blocos_one if not b.atual)
    assert prop_one.acomodacao == "—"
    for tab, pl in zip(_tabelas_faixas(html), planos):
        if pl.subgrupo_id != "sg-a":
            continue
        idx = tab.index("Acomodação")
        trecho = tab[idx : idx + 400]
        assert "Apartamento" in trecho
        assert "misto" not in trecho.lower()


def test_05_total_com_vidas_do_grupo(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    vm, html, _ = _vm_html(tmp_path, rascunho)
    for tab, pl in zip(_tabelas_faixas(html), planos_das_faixas(vm, seguro_novo=False)):
        vidas = sum(fx.qtd_total for fx in pl.faixas)
        assert re.search(rf"<td class='col-vidas'>{vidas}</td>", tab)
        assert "<td>Total</td>" in tab


def test_06_soma_secoes_igual_total_do_estudo(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    vm, _, ids = _vm_html(tmp_path, rascunho)
    planos = planos_das_faixas(vm, seguro_novo=False)
    for oid in ids:
        soma = 0
        for pl in planos:
            prop = next(p for s in vm.secoes_regime for p in s.propostas if id_coluna_vm(p) == oid)
            sub = prop.subtotais_por_subgrupo.get(pl.subgrupo_id) or 0
            soma += sub
        total = vm.totais_gerais.propostas.get(oid)
        assert soma == total


def test_08_um_col_titdep_para_o_documento(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert html.count('id="col-titdep"') == 1
    assert "#col-titdep:checked ~ * .tabela-faixas th.col-titdep" in html
    assert "#col-titdep:checked ~ * .tabela-faixas td.col-titdep" in html


def test_07_mockup_mesma_estrutura(tmp_path: Path):
    mockup = (
        Path(__file__).resolve().parents[1] / "docs" / "faixas-por-grupo.html"
    ).read_text(encoding="utf-8")
    assert mockup.count('class="grupo-cab"') == 2
    assert "Faixas sem vidas não aparecem" in mockup
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1000)
    vm, html, _ = _vm_html(tmp_path, rascunho)
    tela = re.search(
        r"<div class='layout-tela'>(.*?)</div>\s*<div class='layout-impressao'>",
        html,
        flags=re.S,
    )
    bloco = tela.group(1) if tela else html
    assert bloco.count("class='grupo-cab'") == 2
    assert "Acomodação" in bloco and "Modalidade" in bloco
    assert "28.862,01" in bloco
    assert "18.751,61" in bloco
    for tab in _tabelas_faixas(html):
        assert "Acomodação" in tab
        assert "<td>Total</td>" in tab
        assert "Diferença mensal" in tab
    del vm


def test_09_zero_script(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    _, html, _ = _vm_html(tmp_path, rascunho)
    assert _SCRIPT.search(html) is None


def test_17_um_vigente_uma_secao(tmp_path: Path):
    from newport_app.seed.ficticio import rascunho_demo_12_vidas

    rascunho = rascunho_demo_12_vidas()
    vm, html, _ = _vm_html(tmp_path, rascunho)
    assert len(planos_das_faixas(vm, seguro_novo=False)) == 1
    tela = re.search(
        r"<div class='layout-tela'>(.*?)</div>\s*<div class='layout-impressao'>",
        html,
        flags=re.S,
    )
    bloco = tela.group(1) if tela else html
    assert bloco.count("class='grupo-cab'") == 1
    assert len(_tabelas_faixas(html)) == 1


def test_18_seguro_novo_uma_tabela(tmp_path: Path):
    rascunho = _rascunho_ivtec_novo()
    snap = _aprovar(tmp_path, rascunho)
    ids = _ids(snap)
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    html = render_html(vm)
    assert "class='grupo-cab'" not in html
    assert "tabela-faixas" in html
    assert MAX_PROPOSTAS_POR_PAGINA == 3


def test_10_paridade_matriz_documento_faixas(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz, _ = _calcular_matriz(rascunho)
    vm, html, ids = _vm_html(tmp_path, rascunho)
    assert not divergencias_estruturais(matriz, vm, rascunho=rascunho)
    assert not divergencias_html_vm(vm, html)
    planos = planos_das_faixas(vm, seguro_novo=False)
    tabelas = _tabelas_faixas(html)
    assert len(tabelas) == len(planos)
    matriz_por_sg = {p.subgrupo_id: p for p in matriz.planos_atuais}
    for tab, pl in zip(tabelas, planos):
        mp = matriz_por_sg.get(pl.subgrupo_id)
        assert mp is not None
        ocupadas_vm = {fx.rotulo for fx in pl.faixas if fx.qtd_total > 0}
        ocupadas_mx = {fx.rotulo for fx in mp.faixas if fx.quantidade > 0}
        assert ocupadas_vm == ocupadas_mx
        for rot in ocupadas_vm:
            assert f"data-fx='{rot}'" in tab
        assert pl.subtotal_reajustado_centavos == mp.reajustado_centavos
    del ids


def test_12_gabaritos_valor_por_valor(tmp_path: Path):
    for bps, s750, one in (
        (1000, 2_886_201, 1_875_161),
        (1200, 2_938_676, 1_909_255),
    ):
        rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=bps)
        vm, html, _ = _vm_html(tmp_path, rascunho)
        por_sg = {pl.subgrupo_id: pl for pl in planos_das_faixas(vm, seguro_novo=False)}
        assert por_sg["sg-a"].subtotal_reajustado_centavos == s750
        assert por_sg["sg-b"].subtotal_reajustado_centavos == one
        assert vm.totais_gerais.atual_centavos == s750 + one
        from newport_app.presentation.formatacao import formatar_reais

        assert formatar_reais(s750).replace("R$ ", "") in html
        assert formatar_reais(one).replace("R$ ", "") in html
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path / "gab", rascunho)
    ids = [chave_de_coluna(p) for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    assert_gabarito_propostas(matriz, vm, gab)
    assert vm.totais_gerais.atual_centavos == 4_847_931
    rascunho_n = _rascunho_ivtec_novo()
    snap_n = _aprovar(tmp_path / "ivtec", rascunho_n)
    ids_n = _ids(snap_n)
    vm_n = construir_view_model(snap_n, modo="faixas", propostas_selecionadas=ids_n)
    assert vm_n.totais_gerais.propostas["op-bronze"] == 374_189
    assert vm_n.totais_gerais.propostas["op-prata"] == 565_204


def test_16_impressao_mesmo_criterio(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    vm, html, ids = _vm_html(tmp_path, rascunho)
    assert MAX_PROPOSTAS_POR_PAGINA == 3
    impressao = re.search(
        r"<div class='layout-impressao'>(.*)$",
        html,
        flags=re.S,
    )
    bloco = impressao.group(1) if impressao else html
    esperado = 0
    for pl in planos_das_faixas(vm, seguro_novo=False):
        ids_g = ids_do_grupo(vm, ids, pl)
        esperado += len(chunks_propostas(ids_g))
        for ch in chunks_propostas(ids_g):
            assert len(ch) <= MAX_PROPOSTAS_POR_PAGINA
    n_tabs = len(
        re.findall(r"<table class='[^']*tabela-faixas[^']*'>", bloco)
    )
    assert n_tabs == esperado
