"""Paginação por colunas na impressão da aba de grupo familiar."""

from __future__ import annotations

import re
from pathlib import Path

from newport_app.models.snapshot import GerarApresentacaoRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import MAX_PROPOSTAS_POR_PAGINA, construir_view_model
from newport_app.presentation.colisao_coluna import id_coluna_vm
from newport_app.presentation.nome_plano_exibicao import nome_plano_documento
from newport_app.presentation.formatacao import formatar_reais
from newport_app.presentation.html_renderer import render_html
from newport_app.presentation.paridade_estrutural import assert_paridade_estrutural
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.hashing import hash_snapshot_canonico
from tests.test_correcao_resumo_regime import _aprovar as _aprovar_tmp
from tests.test_frente2_grupo_familiar import (
    _GABARITO,
    _anistia_com_vinculos,
    _ids_seis,
)
from tests.test_fase2_tarefa2 import _aprovar, _stack
from tests.test_paridade_matriz_html import (
    _aprovar as _aprovar_matriz,
    _calcular_matriz,
)

_SCRIPT_TAG = re.compile(r"<script\b", re.IGNORECASE)
_TH = re.compile(r"<th[^>]*>(.*?)</th>", re.S)
_TR = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S)
_TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TAG = re.compile(r"<[^>]+>")
_FIXOS = ["Nome", "Idade", "Faixa", "Vínculo", "Plano atual", "Contrato atual"]


def _html_anistia(tmp_path: Path, ids: list[str] | None = None) -> tuple[str, object]:
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_tmp(tmp_path, rascunho)
    escolhidas = ids if ids is not None else _ids_seis()
    vm = construir_view_model(
        snap, modo="grupo_familiar", propostas_selecionadas=escolhidas
    )
    return render_html(vm), vm


def _texto(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub("", html)).strip()


def _rotulos_th(tabela: str) -> list[str]:
    thead = re.search(r"<thead>(.*?)</thead>", tabela, re.S)
    assert thead
    return [_texto(raw) for raw in _TH.findall(thead.group(1))]


def _tabelas_tela(html: str) -> list[str]:
    wrap = re.search(
        r"<div class='grupo-familiar-tela'>(.*?)</div>\s*<div class='grupo-familiar-impressao'",
        html,
        re.S,
    )
    bloco = wrap.group(1) if wrap else html
    return re.findall(
        r"<table class='tabela-grupo-familiar[^']*'>(.*?)</table>", bloco, re.S
    )


def _tabela_tela(html: str) -> str:
    tabelas = _tabelas_tela(html)
    assert tabelas
    return tabelas[0]


def _blocos_impressao(html: str) -> list[str]:
    return re.findall(
        r"<table class='tabela-grupo-familiar[^']*tabela-grupo-bloco'>(.*?)</table>",
        html,
        re.S,
    )


def _linhas_membro(tabela: str) -> list[list[str]]:
    linhas = []
    for tr in _TR.findall(tabela):
        if "subtotal-grupo" in tr or "total-geral" in tr or "grupo-cab" in tr:
            continue
        tds = [_texto(td) for td in _TD.findall(tr)]
        if tds:
            linhas.append(tds)
    return linhas


def test_01_anistia_seis_propostas_aparecem_na_impressao(tmp_path: Path):
    html, vm = _html_anistia(tmp_path)
    assert MAX_PROPOSTAS_POR_PAGINA == 3
    blocos = _blocos_impressao(html)
    assert blocos
    for bloco in blocos:
        cab = _rotulos_th(bloco)
        assert cab[:6] == _FIXOS
        assert 1 <= len(cab) - 6 <= MAX_PROPOSTAS_POR_PAGINA
    nomes = []
    for bloco in blocos:
        nomes.extend(_rotulos_th(bloco)[6:])
    rotulos = []
    for op_id in vm.propostas_selecionadas:
        for secao in vm.secoes_regime:
            prop = next((p for p in secao.propostas if id_coluna_vm(p) == op_id), None)
            if prop and prop.plano_nome:
                rotulos.append(nome_plano_documento(prop.plano_nome.strip()))
                break
    assert len(rotulos) == 6
    assert set(nomes) == set(rotulos)


def test_02_cada_bloco_repete_identificacao_e_contrato(tmp_path: Path):
    html, _vm = _html_anistia(tmp_path)
    for bloco in _blocos_impressao(html):
        assert _rotulos_th(bloco)[:6] == _FIXOS


def test_03_subtotais_em_todos_os_blocos(tmp_path: Path):
    html, vm = _html_anistia(tmp_path)
    n_multi = sum(1 for g in vm.grupos_familiares if g.exibir_subtotal)
    assert n_multi == 12
    telas = _tabelas_tela(html)
    assert telas
    for tab in telas:
        n = tab.count("Sub Total ")
        assert n >= 1
    assert sum(t.count("Sub Total ") for t in telas) == n_multi
    for bloco in _blocos_impressao(html):
        assert "Sub Total " in bloco


def test_04_total_geral_em_todos_os_blocos(tmp_path: Path):
    html, _vm = _html_anistia(tmp_path)
    totais = []
    for bloco in _blocos_impressao(html):
        m = re.search(r"Total (\d+) Vidas", bloco)
        assert m
        totais.append(int(m.group(1)))
    # Cada grupo se pagina; a soma das páginas distintas não é 41×N —
    # cada fatia do mesmo grupo repete o total daquele grupo.
    assert totais
    assert all(n > 0 for n in totais)


def test_05_mesmo_valor_em_qualquer_bloco(tmp_path: Path):
    html, vm = _html_anistia(tmp_path)
    telas = _tabelas_tela(html)
    blocos = _blocos_impressao(html)
    assert telas and blocos
    tela0 = _linhas_membro(telas[0])
    assert tela0
    # Primeira seção: as fatias de impressão que repetem as mesmas vidas.
    mesma = [b for b in blocos if len(_linhas_membro(b)) == len(tela0)]
    assert mesma
    for i_op in range(min(MAX_PROPOSTAS_POR_PAGINA, len(vm.propostas_selecionadas))):
        for linha_tela, linha_bloco in zip(tela0, _linhas_membro(mesma[0]), strict=True):
            assert linha_tela[0] == linha_bloco[0]
            assert linha_tela[6 + i_op] == linha_bloco[6 + i_op]


def test_06_tres_propostas_um_bloco_so(tmp_path: Path):
    html, vm = _html_anistia(tmp_path, ids=_ids_seis()[:3])
    assert len(vm.propostas_selecionadas) == 3
    n_grupos = len({m.subgrupo_id for g in vm.grupos_familiares for m in g.membros if m.subgrupo_id})
    assert "tabela-grupo-bloco" not in html
    assert html.count("<table class='tabela-grupo-familiar") == n_grupos


def test_07_tela_continua_uma_tabela(tmp_path: Path):
    html, vm = _html_anistia(tmp_path)
    n_grupos = len({m.subgrupo_id for g in vm.grupos_familiares for m in g.membros if m.subgrupo_id})
    assert html.count("class='grupo-familiar-tela'") == 1
    assert len(_tabelas_tela(html)) == n_grupos
    assert "grupo-familiar-impressao{display:none}" in html
    assert ".rolo{" in html or "overflow-x:auto" in html


def test_08_impressao_thead_e_subtotal_preso(tmp_path: Path):
    html, _vm = _html_anistia(tmp_path)
    assert "thead{display:table-header-group}" in html
    assert "tbody.grupo-familiar{" in html
    assert "break-inside:avoid" in html
    assert "grupo-familiar-tela{display:none !important}" in html
    assert "table-layout:fixed" in html
    assert "overflow-wrap:break-word" in html


def test_09_zero_script(tmp_path: Path):
    html, _vm = _html_anistia(tmp_path)
    assert _SCRIPT_TAG.search(html) is None


def test_10_gabarito_anistia_intacto(tmp_path: Path):
    html, _vm = _html_anistia(tmp_path)
    assert formatar_reais(_GABARITO["prata"][0]) == "R$ 23.607,17"
    assert formatar_reais(_GABARITO["prata"][1]) == "R$ 6.100,61"
    assert formatar_reais(_GABARITO["consolidado_proposta"]) == "R$ 48.479,31"
    assert "48.479,31" in html


def test_11_hash_snapshot_inalterado(tmp_path: Path, capsys):
    rascunho = _anistia_com_vinculos()
    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_antes = hash_snapshot_canonico(nucleo_antes)
    repo, _, snap_svc, apres = _stack(tmp_path, "hash-gfp")
    snap = _aprovar(repo, snap_svc, rascunho)
    assert snap.hash_sha256 == h_antes
    apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(modo="completo", propostas_selecionadas=_ids_seis()),
    )
    snap_depois = snap_svc.obter_snapshot(snap.id)
    assert snap_depois.hash_sha256 == h_antes
    _, nucleo_depois, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_depois = hash_snapshot_canonico(nucleo_depois)
    assert h_antes == h_depois
    print(f"HASH_ANTES={h_antes}")
    print(f"HASH_DEPOIS={h_depois}")


def test_13_paridade_estrutural_verde(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar_matriz(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="grupo_familiar", propostas_selecionadas=ids)
    assert_paridade_estrutural(matriz, vm, rascunho=rascunho)
