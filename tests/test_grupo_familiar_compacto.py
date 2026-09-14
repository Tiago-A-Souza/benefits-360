"""Tabela única e compacta da aba de grupo familiar."""

from __future__ import annotations

import re
from pathlib import Path

from newport_app.models.snapshot import GerarApresentacaoRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.colisao_coluna import coluna_bate
from newport_app.presentation.formatacao import formatar_reais
from newport_app.presentation.html_renderer import (
    RENDERER_VERSAO,
    _CSS,
    render_html,
    render_html_completo,
)
from newport_app.presentation.paridade_estrutural import assert_paridade_estrutural
from newport_app.presentation.paridade_html import divergencias_html_vm
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
    wrap = re.search(
        r"<div class='grupo-familiar-tela'>(.*?)</div>\s*<div class='grupo-familiar-impressao'",
        html,
        re.S,
    )
    if wrap:
        return wrap.group(1)
    tela = re.search(
        r"<div class='rolo grupo-familiar-tela'>(.*?)</div>\s*<div class='grupo-familiar-impressao'",
        html,
        re.S,
    )
    if tela:
        return tela.group(1)
    tabelas = re.findall(
        r"<table class='tabela-grupo-familiar[^']*'>.*?</table>", html, re.S
    )
    assert tabelas, "tabela de grupo familiar ausente"
    return "".join(tabelas)


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
    n_grupos = len({m.subgrupo_id for g in vm.grupos_familiares for m in g.membros if m.subgrupo_id})
    assert n_grupos >= 2
    assert tela.count("<table class='tabela-grupo-familiar") == n_grupos
    assert tela.count("<thead>") == n_grupos
    assert tela.count("<div class='grupo-cab'") == n_grupos
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
    html, vm = _html_anistia_grupos(tmp_path)
    tela = _html_tela(html)
    totais = re.findall(r"Total (\d+) Vidas", tela)
    assert totais
    assert sum(int(n) for n in totais) == 41
    assert "grupo-familiar-total" in html
    del vm


def test_04_soma_grupos_igual_faixas_por_proposta(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_tmp(tmp_path, rascunho)
    ids = _ids_seis()
    vm_g = construir_view_model(snap, modo="grupo_familiar", propostas_selecionadas=ids)
    vm_f = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    for op_id in vm_g.propostas_selecionadas:
        soma = 0
        for g in vm_g.grupos_familiares:
            for m in g.membros:
                col = next(c for c in m.propostas if coluna_bate(c, op_id))
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
    """IVTEC com carimbo parcial: titulares agrupados; órfãos iniciais em bloco único."""
    rascunho = _rascunho_ivtec_novo()
    _carimbar_vinculos_por_ordem(rascunho)
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(
        snap,
        modo="grupo_familiar",
        propostas_selecionadas=["op-bronze", "op-prata"],
    )
    assert len(vm.grupos_familiares) == 9
    assert sum(len(g.membros) for g in vm.grupos_familiares) == 12
    orfaos = [g for g in vm.grupos_familiares if g.sem_vinculo_resolvido]
    assert len(orfaos) == 1
    assert len(orfaos[0].membros) == 4
    assert orfaos[0].exibir_subtotal
    html = render_html(vm)
    assert html.count("tr class='grupo-cab'") == 1
    assert "sem vínculo resolvido" not in html
    assert "Sub Total Sem vínculo familiar na base" in html
    assert "3.741,89" in html
    assert "5.652,04" in html
    assert vm.totais_gerais.propostas["op-bronze"] == 374_189
    assert vm.totais_gerais.propostas["op-prata"] == 565_204


def test_07c_mix_dois_orfaos_cabecalho_bloco_unico(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    for v in rascunho.vidas[:2]:
        v.vinculo_grupo_chave = None
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(
        snap,
        modo="grupo_familiar",
        propostas_selecionadas=_ids_seis()[:1],
    )
    orfaos = [g for g in vm.grupos_familiares if g.sem_vinculo_resolvido]
    assert len(orfaos) == 1
    assert len(orfaos[0].membros) == 2
    html = render_html(vm)
    assert html.count("Sem vínculo familiar na base") >= 1
    assert "sem vínculo resolvido" not in html
    assert sum(len(g.membros) for g in vm.grupos_familiares) == 41


def test_07b_ivtec_sem_vinculo_lista_plana(tmp_path: Path):
    """IVTEC real sem CPF titular: uma tabela, aviso único, sem cabeçalhos Grupo N."""
    rascunho = _rascunho_ivtec_novo()
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(
        snap,
        modo="grupo_familiar",
        propostas_selecionadas=["op-bronze", "op-prata"],
        beneficiarios_agregados=True,
    )
    assert len(vm.grupos_familiares) == 1
    assert vm.grupos_familiares[0].lista_plana_sem_vinculo
    assert len(vm.grupos_familiares[0].membros) == 12
    assert vm.aviso_vinculo_familiar == (
        "A base importada não traz vínculo familiar. "
        "Beneficiários listados individualmente."
    )
    html = render_html(vm)
    tela = _html_tela(html)
    assert tela.count("<table class='tabela-grupo-familiar") == 1
    assert tela.count("<tbody class='grupo-familiar'>") == 1
    assert tela.count("tr class='grupo-cab'") == 0
    assert "Grupo 1" not in html
    assert "Grupo 12" not in html
    assert vm.aviso_vinculo_familiar in html
    assert "Total 12 Vidas" in tela
    assert vm.totais_gerais.propostas["op-bronze"] == 374_189
    assert vm.totais_gerais.propostas["op-prata"] == 565_204
    assert not divergencias_html_vm(vm, html)


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
    assert "48.479,31" in html_f
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
    assert RENDERER_VERSAO == "html@2.13.8"


def test_rotulo_reajuste_cabecalho():
    from newport_app.presentation.html_renderer import _rotulo_reajuste_cabecalho

    assert _rotulo_reajuste_cabecalho(None) == "REAJUSTADO"
    assert _rotulo_reajuste_cabecalho("+12%") == "REAJUSTADO 12%"
    assert _rotulo_reajuste_cabecalho("-3,50%") == "REAJUSTADO -3,50%"
    assert _rotulo_reajuste_cabecalho("0%") == "REAJUSTADO 0%"


def test_percentual_cabecalho_unico_nao_usa_o_primeiro():
    """Dois planos vigentes com taxas distintas → sem taxa única no cabeçalho."""
    from types import SimpleNamespace

    from newport_app.presentation.html_renderer import (
        _percentual_unico_membros,
        _rotulo_reajuste_cabecalho,
    )

    model = SimpleNamespace(
        grupos_familiares=[
            SimpleNamespace(
                membros=[
                    SimpleNamespace(subgrupo_id="plano-a"),
                    SimpleNamespace(subgrupo_id="plano-b"),
                ]
            )
        ]
    )
    iguais = {"plano-a": "+12%", "plano-b": "+12%"}
    assert _percentual_unico_membros(model, iguais) == "+12%"
    distintos = {"plano-a": "+12%", "plano-b": "+8%"}
    assert _percentual_unico_membros(model, distintos) is None
    assert _rotulo_reajuste_cabecalho(None) == "REAJUSTADO"


def test_reajuste_no_cabecalho_nao_nas_linhas(tmp_path: Path):
    html, _vm = _html_anistia_grupos(tmp_path)
    tabelas = re.findall(
        r"<table class='tabela-grupo-familiar[^']*'>(.*?)</table>", html, re.S
    )
    assert tabelas
    for tab in tabelas:
        assert "data-l='REAJUSTADO 12%'" in tab
        tbody = re.search(r"<tbody.*", tab, re.S)
        assert tbody, "tbody ausente"
        assert "class='ajuste'" not in tbody.group(0)
