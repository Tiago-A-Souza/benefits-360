"""Bloco 2 — modalidade no cabeçalho; campo opcional na conferência PDF."""

from __future__ import annotations

from pathlib import Path

from newport_app.cotacao_pdf.apply import aplicar_extracao_confirmada
from newport_app.models.draft import ModalidadeRascunho
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.colisao_coluna import chave_de_coluna
from newport_app.presentation.html_renderer import render_html
from newport_app.presentation.nome_plano_exibicao import nome_plano_cabecalho
from newport_app.presentation.tabela_densa import html_linhas_nome_plano_documento
from newport_app.siscor_mapper.apply import rascunho_vazio
from tests.test_acomodacao_dedupe import _extracao, _opcao_pronta
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_paridade_matriz_html import _aprovar, _calcular_matriz


def test_cabecalho_sem_modalidade_quando_ausente():
    curto, _, mod = nome_plano_cabecalho("OURO MAIS I Q", modalidade=None)
    assert curto == "OURO MAIS I Q"
    assert mod is None
    assert html_linhas_nome_plano_documento("OURO MAIS I Q") == "OURO MAIS I Q"
    assert "(Compulsório)" not in html_linhas_nome_plano_documento("OURO MAIS I Q")
    assert html_linhas_nome_plano_documento(
        "OURO MAIS I Q", modalidade="Compulsório"
    ) == "OURO MAIS I Q (Compulsório)"


def test_modalidade_confirmada_grava_rascunho():
    rascunho = rascunho_vazio("est-mod", "Cliente")
    op = _opcao_pronta(
        opcao_id="op-mod",
        nome="PRATA QC",
        valores=[10000] * 10,
        acomodacao="Enfermaria",
    )
    assert op.modalidade is not None
    op.modalidade.texto = "compulsorio"
    op.modalidade.confirmado = True
    aplicar_extracao_confirmada(rascunho, _extracao("doc-mod", "ext-mod", [op]))
    assert len(rascunho.opcoes_proposta) == 1
    assert rascunho.opcoes_proposta[0].modalidade == ModalidadeRascunho.COMPULSORIO


def test_modalidade_vazia_nao_grava_rascunho():
    rascunho = rascunho_vazio("est-sem-mod", "Cliente")
    op = _opcao_pronta(
        opcao_id="op-sem",
        nome="PRATA QC",
        valores=[10000] * 10,
        acomodacao="Enfermaria",
    )
    assert op.modalidade is not None
    op.modalidade.texto = None
    op.modalidade.confirmado = False
    aplicar_extracao_confirmada(rascunho, _extracao("doc-sem", "ext-sem", [op]))
    assert rascunho.opcoes_proposta[0].modalidade is None


def test_proposta_com_modalidade_declarada_aparece_no_cabecalho(tmp_path: Path):
    rascunho = _rascunho_anistia_seis()
    op = next(o for o in rascunho.opcoes_proposta if o.id == "op-ouro")
    op.modalidade = ModalidadeRascunho.ADESAO
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [chave_de_coluna(p) for p in matriz.propostas if p.calculo_realizado]
    html = render_html(construir_view_model(snap, modo="resumo", propostas_selecionadas=ids))
    assert "OURO MAIS I Q (Adesão)" in html
