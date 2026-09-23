"""Bloco 2 — tabela geral de planos consultados."""

from __future__ import annotations

from pathlib import Path

from newport_app.models.draft import SelecaoPlanosGrupoRascunho
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.colisao_coluna import chave_de_coluna
from newport_app.presentation.formatacao import formatar_reais
from newport_app.presentation.html_renderer import render_html_completo
from newport_app.presentation.nome_plano_exibicao import nome_plano_documento
from newport_app.presentation.tabela_planos_consultados import montar_tabela_planos_consultados
from newport_app.rascunho.selecao_grupo import definir_selecao_do_subgrupo
from newport_app.services.matriz_estimativa import montar_matriz_estimativa
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_frente2_grupo_familiar import _GABARITO
from tests.test_paridade_matriz_html import _aprovar, _calcular_matriz


def test_tabela_tem_contrato_atual_e_catalogo():
    rascunho = _rascunho_anistia_seis()
    tab = montar_tabela_planos_consultados(rascunho)
    assert tab is not None
    assert len(tab.colunas) == 2
    assert tab.linhas[0].eh_contrato_atual
    assert tab.linhas[0].plano == "Contrato atual"
    assert tab.linhas[0].total_centavos == _GABARITO["consolidado_proposta"]
    assert len(tab.linhas) == 1 + len(rascunho.opcoes_proposta)


def test_valores_batem_com_matriz_estimativa():
    rascunho = _rascunho_anistia_seis()
    matriz = montar_matriz_estimativa(rascunho, restrita=False)
    tab = montar_tabela_planos_consultados(rascunho)
    assert tab is not None
    por_par = {
        (c.opcao_id, c.subgrupo_id): c.estimado_centavos for c in matriz.celulas
    }
    for op in rascunho.opcoes_proposta:
        rotulo = nome_plano_documento(op.plano_nome or op.id)
        lin = next(l for l in tab.linhas[1:] if l.plano == rotulo)
        for col in tab.colunas:
            assert lin.celulas[col.subgrupo_id] == por_par.get((op.id, col.subgrupo_id))


def test_plano_fora_da_selecao_do_grupo_celula_vazia():
    rascunho = _rascunho_anistia_seis()
    definir_selecao_do_subgrupo(rascunho, "sg-a", ["op-prata"])
    tab = montar_tabela_planos_consultados(rascunho)
    assert tab is not None
    lin_bronze = next(
        lin for lin in tab.linhas if "BRONZE" in lin.plano.upper()
    )
    assert lin_bronze.celulas["sg-a"] is None
    assert lin_bronze.celulas["sg-b"] is not None


def test_ordenacao_por_total_crescente():
    rascunho = _rascunho_anistia_seis()
    tab = montar_tabela_planos_consultados(rascunho)
    assert tab is not None
    totais = [lin.total_centavos for lin in tab.linhas[1:] if lin.total_centavos]
    assert totais == sorted(totais)


def _secao(html: str, secao_id: str) -> str:
    start = html.find(f'id="{secao_id}"')
    assert start >= 0
    nxt = len(html)
    for other in ("visao-resumo", "visao-faixas", "visao-benef", "visao-regras"):
        if other == secao_id:
            continue
        pos = html.find(f'id="{other}"', start + 1)
        if pos != -1:
            nxt = min(nxt, pos)
    return html[start:nxt]


def test_tabela_somente_na_aba_resumo(tmp_path: Path):
    rascunho = _rascunho_anistia_seis()
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [chave_de_coluna(p) for p in matriz.propostas if p.calculo_realizado]
    kwargs = dict(propostas_selecionadas=ids)
    vm_r = construir_view_model(snap, modo="resumo", **kwargs)
    vm_f = construir_view_model(snap, modo="faixas", **kwargs)
    vm_g = construir_view_model(snap, modo="grupo_familiar", **kwargs)
    html = render_html_completo(vm_r, vm_f, vm_g)

    resumo = _secao(html, "visao-resumo")
    faixas = _secao(html, "visao-faixas")
    grupos = _secao(html, "visao-benef")

    assert "secao-planos-consultados" in resumo
    assert "Contrato atual" in resumo
    assert formatar_reais(_GABARITO["consolidado_proposta"]).replace("R$ ", "") in resumo
    assert "secao-planos-consultados" not in faixas
    assert "secao-planos-consultados" not in grupos
    assert "<span class='n1'>00</span>" not in html
