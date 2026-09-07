"""Tabela única e compacta da aba de grupo familiar."""

from __future__ import annotations

import re
from pathlib import Path

from newport_app.models.snapshot import GerarApresentacaoRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.formatacao import formatar_reais
from newport_app.presentation.html_renderer import (
    RENDERER_VERSAO,
    _CSS,
    render_html,
    render_html_completo,
)
from newport_app.presentation.paridade_estrutural import assert_paridade_estrutural
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.hashing import hash_snapshot_canonico
from tests.test_apresentacao_seguro_novo import _rascunho_ivtec_novo
from tests.test_correcao_resumo_regime import _aprovar as _aprovar_tmp
from tests.test_frente2_grupo_familiar import (
    _GABARITO,
    _anistia_com_vinculos,
    _carimbar_vinculos_por_ordem,
    _ids_seis,
)
from tests.test_fase2_tarefa2 import _aprovar, _stack
from tests.test_paridade_matriz_html import (
    _aprovar as _aprovar_matriz,
    _calcular_matriz,
)

_SCRIPT_TAG = re.compile(r"<script\b", re.IGNORECASE)
_TH = re.compile(r"<th[^>]*>(.*?)</th>", re.S)
_TAG = re.compile(r"<[^>]+>")


def _html_anistia_grupos(tmp_path: Path, *, agregados: bool = False) -> tuple[str, object]:
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(
        snap,
        modo="grupo_familiar",
        propostas_selecionadas=_ids_seis(),
        beneficiarios_agregados=agregados,
    )
    return render_html(vm), vm


def _html_tela(html: str) -> str:
    tela = re.search(
        r"<div class='rolo grupo-familiar-tela'>(.*?)</div>\s*<div class='grupo-familiar-impressao'",
        html,
        re.S,
    )
    if tela:
        return tela.group(1)
    unica = re.search(r"<table class='tabela-grupo-familiar[^']*'>.*?</table>", html, re.S)
    assert unica, "tabela de grupo familiar ausente"
    return unica.group(0)


def _rotulos_th(html: str) -> list[str]:
    tabela = re.search(
        r"<table class='tabela-grupo-familiar[^']*'>(.*?)</table>", _html_tela(html), re.S
    )
    assert tabela, "tabela de grupo familiar ausente"
    thead = re.search(r"<thead>(.*?)</thead>", tabela.group(1), re.S)
    assert thead, "thead ausente"
    saida = []
    for raw in _TH.findall(thead.group(1)):
        texto = _TAG.sub("", raw)
        texto = re.sub(r"\s+", " ", texto).strip()
        saida.append(texto)
    return saida


def test_01_anistia_uma_tabela_um_cabecalho(tmp_path: Path):
    html, vm = _html_anistia_grupos(tmp_path)
    tela = _html_tela(html)
    assert len(vm.grupos_familiares) == 27
    assert sum(len(g.membros) for g in vm.grupos_familiares) == 41
    assert tela.count("<table class='tabela-grupo-familiar") == 1
    assert tela.count("<thead>") == 1
    assert "grupo-familiar-titulo" not in html
    assert tela.count("<tbody class='grupo-familiar'>") == 27


def test_02_subtotal_so_grupos_com_mais_de_uma_pessoa(tmp_path: Path):
    html, vm = _html_anistia_grupos(tmp_path)
    multi = [g for g in vm.grupos_familiares if len(g.membros) > 1]
    solo = [g for g in vm.grupos_familiares if len(g.membros) == 1]
    assert len(multi) == 12
    assert len(solo) == 15
    assert all(g.exibir_subtotal for g in multi)
    assert all(not g.exibir_subtotal for g in solo)
    assert _html_tela(html).count("Sub Total ") == 12
    for g in solo:
        assert g.exibir_subtotal is False


def test_03_total_geral_com_contagem_de_vidas(tmp_path: Path):
    html, _vm = _html_anistia_grupos(tmp_path)
    assert "Total 41 Vidas" in html
    assert "grupo-familiar-total" in html


def test_04_soma_grupos_igual_faixas_por_proposta(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_tmp(tmp_path, rascunho)
    ids = _ids_seis()
    vm_g = construir_view_model(snap, modo="grupo_familiar", propostas_selecionadas=ids)
    vm_f = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    for op_id in ids:
        soma = 0
        for g in vm_g.grupos_familiares:
            for m in g.membros:
                col = next(c for c in m.propostas if c.opcao_id == op_id)
                soma += col.valor_centavos or 0
        assert soma == vm_f.totais_gerais.propostas[op_id]
        assert soma == vm_g.totais_gerais.propostas[op_id]


def test_05_ordem_alfabetica_pelo_titular(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    for i, v in enumerate(rascunho.vidas):
        if v.parentesco and str(v.parentesco.value).lower() == "titular":
            v.nome = f"Titular {chr(65 + (i % 26))}{i:02d}"
        else:
            v.nome = f"Dependente {i:02d}"
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="grupo_familiar", propostas_selecionadas=_ids_seis()[:1]
    )
    rotulos = [g.rotulo for g in vm.grupos_familiares if not g.sem_vinculo_resolvido]
    assert rotulos == sorted(rotulos, key=str.casefold)


def test_06_versao_sem_nomes_identificavel(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    for i, v in enumerate(rascunho.vidas):
        v.nome = f"Pessoa Segredo {i}"
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(
        snap,
        modo="grupo_familiar",
        propostas_selecionadas=_ids_seis()[:1],
        beneficiarios_agregados=True,
    )
    html = render_html(vm)
    for v in rascunho.vidas:
        assert v.nome not in html
    assert vm.grupos_familiares[0].rotulo == "Grupo 1"
    assert "Grupo 1" in html
    assert "Sub Total Grupo" in html
    assert " · titular" in html or " · cônjuge" in html
    assert "Membro" in html


def test_07_ivtec_doze_grupos_sem_subtotal(tmp_path: Path):
    rascunho = _rascunho_ivtec_novo()
    _carimbar_vinculos_por_ordem(rascunho)
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(
        snap,
        modo="grupo_familiar",
        propostas_selecionadas=["op-bronze", "op-prata"],
    )
    assert len(vm.grupos_familiares) == 12
    assert all(len(g.membros) == 1 for g in vm.grupos_familiares)
    assert all(not g.exibir_subtotal for g in vm.grupos_familiares)
    html = render_html(vm)
    assert "Sub Total " not in html
    assert "3.741,89" in html
    assert "5.652,04" in html
    assert vm.totais_gerais.propostas["op-bronze"] == 374_189
    assert vm.totais_gerais.propostas["op-prata"] == 565_204


def test_08_colunas_iguais_as_de_hoje(tmp_path: Path):
    html, vm = _html_anistia_grupos(tmp_path)
    cab = _rotulos_th(html)
    fixos = ["Nome", "Idade", "Faixa", "Vínculo", "Plano atual", "Contrato atual"]
    assert cab[:6] == fixos
    assert len(cab) == 6 + len(vm.propostas_selecionadas)
    assert "Reajuste" not in cab
    assert "Idade" in cab  # coluna já existia; a referência pede para não acrescentar outra


def test_09_regimes_continuam_em_secoes_separadas(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_tmp(tmp_path, rascunho)
    ids = _ids_seis()
    html = render_html_completo(
        construir_view_model(snap, modo="resumo", propostas_selecionadas=ids),
        construir_view_model(snap, modo="faixas", propostas_selecionadas=ids),
        construir_view_model(snap, modo="grupo_familiar", propostas_selecionadas=ids),
    )
    faixas = re.search(
        r'id="visao-faixas".*?(?=<section class="visao visao-benef")', html, re.S
    )
    assert faixas
    corpo = faixas.group(0)
    assert "Sem coparticipação" in corpo
    assert "Coparticipação" in corpo
    assert corpo.count("<section class='secao-regime'>") >= 2
    assert "lado a lado" not in corpo.lower()


def test_10_zero_script(tmp_path: Path):
    html, _vm = _html_anistia_grupos(tmp_path)
    assert _SCRIPT_TAG.search(html) is None
    assert "<script" not in html.lower()


def test_11_impressao_thead_e_subtotal_com_o_grupo(tmp_path: Path):
    html, _vm = _html_anistia_grupos(tmp_path)
    assert "thead{display:table-header-group}" in html
    assert "table.tabela-grupo-familiar thead{display:table-header-group}" in html
    assert "tbody.grupo-familiar{" in _CSS or "tbody.grupo-familiar{" in html
    assert "break-inside:avoid" in html
    assert "page-break-inside:avoid" in html
    assert _html_tela(html).count("<tbody class='grupo-familiar'>") == 27
    assert "subtotal-grupo" in html


def test_12_gabarito_anistia_intacto(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_tmp(tmp_path, rascunho)
    ids = _ids_seis()
    html_r = render_html(
        construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    )
    html_f = render_html(
        construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    )
    html_g = render_html(
        construir_view_model(snap, modo="grupo_familiar", propostas_selecionadas=ids)
    )
    assert formatar_reais(_GABARITO["consolidado_atual"]) == "R$ 47.613,62"
    assert formatar_reais(_GABARITO["consolidado_proposta"]) == "R$ 48.479,31"
    assert formatar_reais(_GABARITO["prata"][0]) == "R$ 23.607,17"
    assert formatar_reais(_GABARITO["prata"][1]) == "R$ 6.100,61"
    assert "48.479,31" in html_r
    assert "23.607,17" in html_r
    assert "6.100,61" in html_r
    assert "23.607,17" in html_f
    assert "6.100,61" in html_f
    assert "48.479,31" in html_g


def test_13_hash_snapshot_inalterado(tmp_path: Path, capsys):
    rascunho = _anistia_com_vinculos()
    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_antes = hash_snapshot_canonico(nucleo_antes)
    repo, _, snap_svc, apres = _stack(tmp_path, "hash-gfc")
    snap = _aprovar(repo, snap_svc, rascunho)
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


def test_15_paridade_estrutural_verde(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar_matriz(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="grupo_familiar", propostas_selecionadas=ids)
    assert_paridade_estrutural(matriz, vm, rascunho=rascunho)


def test_renderer_versao_patch():
    assert RENDERER_VERSAO == "html@2.11.2"
