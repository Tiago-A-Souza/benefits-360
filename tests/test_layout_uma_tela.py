"""Layout denso: resumo e faixas em uma tabela com blocos de coluna por regime."""

from __future__ import annotations

import json
import re
from pathlib import Path

from newport_app.cotacao_pdf.faixas import ROTULOS_FAIXA
from newport_app.models.presentation import FaixaApresentacao, PlanoAtualApresentacao
from newport_app.models.snapshot import GerarApresentacaoRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import MAX_PROPOSTAS_POR_PAGINA, construir_view_model
from newport_app.presentation.formatacao import formatar_reais
from newport_app.presentation.html_renderer import (
    RENDERER_VERSAO,
    render_html,
    render_html_completo,
)
from newport_app.presentation.paridade_estrutural import divergencias_estruturais
from newport_app.presentation.paridade_html import divergencias_html_vm
from newport_app.presentation.tabela_densa import (
    ROTULO_COLUNA_ATUAL,
    BlocoColuna,
    _html_unitarios_atual,
)
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.hashing import hash_snapshot_canonico
from tests.test_apresentacao_seguro_novo import _rascunho_ivtec_novo
from tests.test_correcao_resumo_regime import (
    _aprovar as _aprovar_anistia,
    _celula_resumo,
    _ids,
    _rascunho_anistia_seis,
    _tabelas_resumo,
)
from tests.test_fase2_tarefa2 import _aprovar as _aprovar_stack
from tests.test_fase2_tarefa2 import _stack
from tests.test_faixas_colunas_ocultas import _html_completo_anistia
from tests.test_frente2_grupo_familiar import _anistia_com_vinculos, _ids_seis
from tests.test_paridade_matriz_html import (
    _GABARITO,
    _aprovar as _aprovar_gabarito,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
    assert_gabarito_propostas,
)

_SCRIPT = re.compile(r"<script\b", re.IGNORECASE)
_FIXTURE_SEIS = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "paridade_matriz"
    / "anistia_seis_propostas.json"
)


def _secao(html: str, secao_id: str) -> str:
    start = html.find(f'id="{secao_id}"')
    assert start >= 0, f"seção {secao_id} ausente"
    nxt = len(html)
    for other in ("visao-resumo", "visao-faixas", "visao-benef", "visao-regras"):
        if other == secao_id:
            continue
        pos = html.find(f'id="{other}"', start + 1)
        if pos != -1:
            nxt = min(nxt, pos)
    return html[start:nxt]


def _tabela_tela(html: str, classe: str) -> str:
    tela = re.search(
        rf"<div class='layout-tela'>(.*?)</div>\s*<div class='layout-impressao'>",
        html,
        flags=re.S,
    )
    bloco = tela.group(1) if tela else html
    tabs = re.findall(
        rf"<table class='[^']*{classe}[^']*'>(.*?)</table>", bloco, flags=re.S
    )
    assert tabs, f"tabela {classe} ausente"
    return tabs[0]


def _cols_bloco_plano(tabela: str) -> list[str]:
    m = re.search(r"<tr class='bloco-plano'>(.*?)</tr>", tabela, flags=re.S)
    assert m, "linha bloco-plano ausente"
    return re.findall(r"<th[^>]*>.*?</th>", m.group(1), flags=re.S)


def _visivel(inner: str) -> str:
    return re.sub(r"<[^>]+>", "", inner).replace("\xa0", " ").strip()


def _tds_atual(tabela: str) -> list[str]:
    return re.findall(r"<td class='atual'[^>]*>(.*?)</td>", tabela, flags=re.S)


def test_01_resumo_uma_tabela_com_blocos(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    resumo = _secao(html, "visao-resumo")
    tela = _tabela_tela(resumo, "tabela-resumo")
    assert "bloco-regime" in tela and "bloco-plano" in tela
    assert "Plano atual" in tela
    assert "Propostas" in tela
    assert resumo.count("class='bloco-regime'") >= 1
    # Tela: uma tabela. Impressão clona em chunks.
    n_tela = len(
        re.findall(
            r"<table class='[^']*tabela-resumo[^']*'>",
            re.search(
                r"<div class='layout-tela'>(.*?)</div>\s*<div class='layout-impressao'>",
                resumo,
                flags=re.S,
            ).group(1),
        )
    )
    assert n_tela == 1


def test_02_resumo_mantem_linhas(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    resumo = _secao(html, "visao-resumo")
    for rotulo in (
        "Consolidado",
        "Diferença mensal",
        "Diferença anual",
        "Validade da cotação",
        "Acomodação",
        "Coparticipação",
        "Custo total mensal",
    ):
        assert rotulo in resumo
    spec = json.loads(_FIXTURE_SEIS.read_text(encoding="utf-8"))
    for pl in spec["planos"]:
        assert pl["plano_nome"] in resumo
    assert "48.479,31" in resumo
    assert "23.607,17" in resumo
    assert "21.354,64" in resumo


def test_03_acomodacao_e_modalidade_no_topo(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    tela = _tabela_tela(_secao(html, "visao-resumo"), "tabela-resumo")
    assert "linha-topo" in tela
    assert re.search(r"<tr class='linha-topo'><td>Acomodação</td>", tela)
    assert re.search(r"<td>Modalidade</td>", tela)


def test_04_valores_identicos_gabarito(tmp_path: Path):
    spec = json.loads(_FIXTURE_SEIS.read_text(encoding="utf-8"))
    rascunho = _rascunho_anistia_seis()
    snap = _aprovar_anistia(tmp_path, rascunho)
    ids = [p["id"] for p in spec["propostas"]]
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    html = render_html(vm)
    tabelas = _tabelas_resumo(html)
    rotulos = {p["id"]: p["plano_nome"] for p in spec["propostas"]}
    s750 = spec["planos"][0]["plano_nome"]
    one = spec["planos"][1]["plano_nome"]
    for gab in spec["gabarito"]:
        nome = rotulos[gab["opcao_id"]]
        assert _celula_resumo(tabelas, s750, nome) == formatar_reais(gab["s750"])
        assert _celula_resumo(tabelas, one, nome) == formatar_reais(gab["one"])
        assert _celula_resumo(tabelas, "Consolidado", nome) == formatar_reais(
            gab["consolidado"]
        )


def test_05_todas_as_propostas_aparecem(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    tela = _tabela_tela(_secao(html, "visao-resumo"), "tabela-resumo")
    spec = json.loads(_FIXTURE_SEIS.read_text(encoding="utf-8"))
    nomes = [p["plano_nome"] for p in spec["propostas"]]
    for nome in nomes:
        assert nome in tela
    cols = _cols_bloco_plano(tela)
    n_atual = sum(1 for c in cols if "class='atual'" in c)
    n_prop = len(cols) - n_atual
    assert n_atual == 1
    assert n_prop == len(nomes)


def test_06_faixas_padrao_sem_tit_dep_vidas(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert ".tabela-faixas th.col-titdep,.tabela-faixas td.col-titdep" in html
    assert ".tabela-faixas th.col-vidas,.tabela-faixas td.col-vidas{display:none}" in html
    tela = _tabela_tela(_secao(html, "visao-faixas"), "tabela-faixas")
    for rotulo in ROTULOS_FAIXA:
        assert rotulo in tela
    assert "class='col-titdep'" in tela
    assert "class='col-vidas'" in tela


def test_07_controle_titdep_permanece(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert html.count('id="col-titdep"') == 1
    assert "#col-titdep:checked ~ * .tabela-faixas th.col-titdep" in html
    assert "#col-titdep:checked ~ * .tabela-faixas th.col-vidas" in html
    assert "checked" not in html.split('id="col-titdep"')[1][:80]


def test_08_grupo_familiar_intocado(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    benef = _secao(html, "visao-benef")
    assert "tabela-densa" not in benef
    assert "tabela-grupo-familiar" in benef
    assert "grupo-familiar-titulo" not in benef
    assert "Detalhamento por grupo familiar" in benef


def test_09_sem_bloco_vazio_quando_so_um_regime(tmp_path: Path):
    rascunho = rascunho_demo_12_vidas()
    snap = _aprovar_anistia(tmp_path, rascunho)
    ids = _ids(snap)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    html = render_html(vm)
    n_prop_blocks = html.count("Propostas ")
    assert n_prop_blocks >= 1
    assert html.count("class='bloco-regime'") >= 1
    # Um regime de propostas: não há bloco extra sem colunas.
    assert "Propostas " in html


def test_10_um_plano_vigente_uma_coluna_atual(tmp_path: Path):
    rascunho = rascunho_demo_12_vidas()
    snap = _aprovar_anistia(tmp_path, rascunho)
    ids = _ids(snap)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    html = render_html(vm)
    m = re.search(
        r"<th class='atual' colspan='(\d+)'>Plano atual", html
    ) or re.search(r"<th class='atual' colspan='(\d+)'>", html)
    assert m, "bloco do atual ausente"
    assert m.group(1) == "1"


def test_11_seguro_novo_sem_bloco_atual(tmp_path: Path):
    rascunho = _rascunho_ivtec_novo()
    snap = _aprovar_anistia(tmp_path, rascunho)
    ids = _ids(snap)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    html = render_html(vm)
    assert "Plano atual" not in html
    assert "Contrato atual" not in html
    assert "bloco-regime" in html


def test_12_zero_script(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert _SCRIPT.search(html) is None
    assert "<script" not in html.lower()
    assert RENDERER_VERSAO.startswith("html@2.13")


def test_13_impressao_pagina_por_colunas(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert "layout-impressao" in html
    assert "layout-tela" in html
    assert MAX_PROPOSTAS_POR_PAGINA == 3
    resumo = _secao(html, "visao-resumo")
    parte = resumo.split("layout-impressao", 1)[1]
    chunks = re.findall(
        r"<table class='[^']*tabela-resumo[^']*'>(.*?)</table>",
        parte,
        flags=re.S,
    )
    assert len(chunks) >= 2
    for tab in chunks:
        cols = _cols_bloco_plano(tab)
        n_atual = sum(1 for c in cols if "class='atual'" in c)
        assert len(cols) - n_atual <= MAX_PROPOSTAS_POR_PAGINA
        assert "bloco-regime" in tab


def test_14_gabarito_anistia_intacto(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar_gabarito(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="resumo", propostas_selecionadas=["op-prata", "op-ouro"]
    )
    html = render_html(vm)
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    assert_gabarito_propostas(matriz, vm, gab)
    assert "48.479,31" in html
    assert "23.607,17" in html
    assert "6.100,61" in html


def test_15_hash_snapshot_inalterado(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_antes = hash_snapshot_canonico(nucleo_antes)
    repo, _, snap_svc, apres = _stack(tmp_path, "hash-uma-tela")
    snap = _aprovar_stack(repo, snap_svc, rascunho)
    assert snap.hash_sha256 == h_antes
    apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(
            modo="completo", propostas_selecionadas=["op-1", "op-2"]
        ),
    )
    snap_depois = snap_svc.obter_snapshot(snap.id)
    assert snap_depois.hash_sha256 == h_antes
    _, nucleo_depois, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_depois = hash_snapshot_canonico(nucleo_depois)
    assert h_antes == h_depois
    assert len(h_antes) == 64
    print(f"HASH_ANTES={h_antes}")
    print(f"HASH_DEPOIS={h_depois}")


def test_17_paridade_estrutural_verde(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_anistia(tmp_path, rascunho)
    ids = _ids_seis()
    matriz, _ = _calcular_matriz(rascunho)
    for modo in ("resumo", "faixas", "grupo_familiar"):
        vm = construir_view_model(
            snap,
            modo=modo,
            propostas_selecionadas=ids,
            beneficiarios_agregados=(modo != "grupo_familiar"),
        )
        assert not divergencias_estruturais(matriz, vm, rascunho=rascunho)
        html = render_html(vm)
        assert not divergencias_html_vm(vm, html)


def test_18_atual_uma_coluna_dois_vigentes(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    for classe in ("tabela-resumo", "tabela-faixas"):
        secao = "visao-resumo" if classe == "tabela-resumo" else "visao-faixas"
        tela = _tabela_tela(_secao(html, secao), classe)
        cols = _cols_bloco_plano(tela)
        n_atual = sum(1 for c in cols if "class='atual'" in c)
        assert n_atual == 1, classe
        assert ROTULO_COLUNA_ATUAL in tela
        assert "<td class='atual'></td>" not in tela


def test_19_tres_vigentes_continua_uma_coluna(tmp_path: Path):
    planos = [
        PlanoAtualApresentacao(
            subgrupo_id=f"s{i}", operadora="AMIL", plano_nome=f"Plano {i}"
        )
        for i in range(3)
    ]
    bloco = BlocoColuna(rotulo="Plano atual", atual=True, planos=planos)
    assert bloco.n_cols == 1

    rascunho = _rascunho_anistia_seis()
    snap = _aprovar_anistia(tmp_path, rascunho)
    ids = _ids(snap)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    extra = vm.secoes_regime[0].planos_atuais[0].model_copy(
        update={"subgrupo_id": "sg-c", "plano_nome": "AMIL EXTRA - Apto."}
    )
    for secao in vm.secoes_regime:
        secao.planos_atuais.append(extra)
    html = render_html(vm)
    tela = _tabela_tela(html, "tabela-resumo")
    cols = _cols_bloco_plano(tela)
    assert sum(1 for c in cols if "class='atual'" in c) == 1
    assert "AMIL EXTRA - Apto." in tela
    assert "Consolidado" in tela
    assert "<td class='atual'></td>" not in tela


def test_20_nenhuma_celula_vazia_no_bloco_atual(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    for secao, classe in (
        ("visao-resumo", "tabela-resumo"),
        ("visao-faixas", "tabela-faixas"),
    ):
        tela = _tabela_tela(_secao(html, secao), classe)
        vazias = [c for c in _tds_atual(tela) if not _visivel(c)]
        assert vazias == [], f"{classe}: {len(vazias)} células vazias no atual"


def test_21_diferenca_anual_travesao_resumo_e_faixas(tmp_path: Path):
    rascunho = _rascunho_anistia_seis()
    snap = _aprovar_anistia(tmp_path, rascunho)
    ids = _ids(snap)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    achou = False
    for secao in vm.secoes_regime:
        for lin in secao.indicadores_resumo:
            if lin.rotulo != "Diferença anual":
                continue
            achou = True
            assert lin.atual is not None
            assert lin.atual.ausente is True
            assert lin.atual.texto == "—"
            assert lin.atual.texto != ""
    assert achou

    html = render_html(vm)
    resumo = _tabela_tela(html, "tabela-resumo")
    m = re.search(r"<tr[^>]*><td>Diferença anual</td>(.*?)</tr>", resumo, flags=re.S)
    assert m
    atual = re.search(r"<td class='atual'[^>]*>(.*?)</td>", m.group(1), flags=re.S)
    assert atual and _visivel(atual.group(1)) == "—"

    vm_f = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    faixas = _tabela_tela(render_html(vm_f), "tabela-faixas")
    m = re.search(r"<tr><td>Diferença anual</td>(.*?)</tr>", faixas, flags=re.S)
    assert m
    atual = re.search(r"<td class='atual'[^>]*>(.*?)</td>", m.group(1), flags=re.S)
    assert atual and _visivel(atual.group(1)) == "—"


def test_22_modalidade_compulsorio_nao_copia_proposta(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    tela = _tabela_tela(_secao(html, "visao-resumo"), "tabela-resumo")
    m = re.search(
        r"<tr class='linha-topo linha-topo-extra'><td>Modalidade</td>(.*?)</tr>",
        tela,
        flags=re.S,
    )
    assert m
    cells = re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), flags=re.S)
    assert cells
    assert _visivel(cells[0]) == "Compulsório"
    for inner in cells[1:]:
        assert "Compulsório" not in _visivel(inner)
        assert _visivel(inner) == "—"

    rascunho = _rascunho_anistia_seis()
    assert all(op.modalidade is None for op in rascunho.opcoes_proposta)


def test_23_faixas_totais_atual_e_consolidado(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    tela = _tabela_tela(_secao(html, "visao-faixas"), "tabela-faixas")
    m = re.search(r"<tfoot><tr><td>Totais</td>(.*?)</tr>", tela, flags=re.S)
    assert m
    atual = re.search(r"<td class='atual'[^>]*>(.*?)</td>", m.group(1), flags=re.S)
    assert atual
    assert "48.479,31" in _visivel(atual.group(1))
    assert sum(1 for c in _cols_bloco_plano(tela) if "class='atual'" in c) == 1


def test_24_faixas_unitario_divergente_rotulado():
    p1 = PlanoAtualApresentacao(
        subgrupo_id="a",
        operadora="AMIL",
        plano_nome="S750",
        faixas=[
            FaixaApresentacao(
                faixa=3,
                rotulo="29 a 33 anos",
                atual_reajustado_unitario_centavos=10000,
            )
        ],
    )
    p2 = PlanoAtualApresentacao(
        subgrupo_id="b",
        operadora="AMIL",
        plano_nome="ONE",
        faixas=[
            FaixaApresentacao(
                faixa=3,
                rotulo="29 a 33 anos",
                atual_reajustado_unitario_centavos=20000,
            )
        ],
    )
    html = _html_unitarios_atual([p1, p2], "29 a 33 anos")
    assert "S750" in html and "ONE" in html
    assert "100,00" in html and "200,00" in html
    igual = _html_unitarios_atual(
        [
            p1,
            PlanoAtualApresentacao(
                subgrupo_id="b",
                operadora="AMIL",
                plano_nome="ONE",
                faixas=[
                    FaixaApresentacao(
                        faixa=3,
                        rotulo="29 a 33 anos",
                        atual_reajustado_unitario_centavos=10000,
                    )
                ],
            ),
        ],
        "29 a 33 anos",
    )
    assert "S750" not in igual and "ONE" not in igual
    assert "100,00" in igual
    vazio = _html_unitarios_atual([p1, p2], "59 a 99 anos")
    assert vazio == "—"


def test_percentual_ao_lado_do_valor_resumo_e_faixas(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert ".tabela-densa .money{display:inline-flex" in html
    assert ".tabela-resumo .ajuste,.tabela-faixas .ajuste{display:inline}" in html
    assert "table.tabela-grupo-familiar .ajuste{display:block" in html
    resumo = _tabela_tela(_secao(html, "visao-resumo"), "tabela-resumo")
    assert "class='ajuste'" in resumo
    assert "+12%" in resumo
