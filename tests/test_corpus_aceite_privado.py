"""Testes privados de aceite — corpus real identificado por hash (sem nomes de arquivo)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from newport_app.config.paths import diretorio_corpus_cotacoes
from newport_app.cotacao_pdf.maturidade import avaliar_maturidade
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf

_FIXTURE_HASHES = Path(__file__).resolve().parent / "fixtures" / "cotacao_pdf" / "corpus_aceite_hashes.json"
_CODIGOS_TABELA_AUSENTE = {"PDF-PORTO-004", "PDF-SUL-001"}


def _carregar_hashes() -> dict[str, str]:
    return json.loads(_FIXTURE_HASHES.read_text(encoding="utf-8"))


def _pdf_por_hash(esperado: str) -> bytes:
    corpus = diretorio_corpus_cotacoes()
    if not corpus.is_dir():
        pytest.skip("Corpus privado indisponível")
    for pdf in corpus.rglob("*.pdf"):
        conteudo = pdf.read_bytes()
        digest = hashlib.sha256(conteudo).hexdigest()
        if digest == esperado:
            return conteudo
    pytest.skip(f"PDF com hash {esperado[:12]}… não encontrado no corpus privado")


def _extrair(esperado_hash: str):
    conteudo = _pdf_por_hash(esperado_hash)
    ext = parse_cotacao_pdf(
        conteudo,
        estudo_id="aceite-corpus",
        documento_id="doc-aceite",
        nome_arquivo="sanitizado.pdf",
    )
    mat = avaliar_maturidade(ext)
    return ext, mat


@pytest.mark.private_corpus
def test_aceite_sulamerica_sem_coparticipacao():
    h = _carregar_hashes()["sulamerica_sem_cp"]
    ext, mat = _extrair(h)

    assert ext.documento.template_id == "sulamerica-pme-sem-cp-v2"
    assert mat["template_reconhecido"]
    assert mat["tabela_extraida"]
    assert not any(a.codigo in _CODIGOS_TABELA_AUSENTE for a in ext.alertas)

    assert ext.opcoes
    assert all(op.regime_copart and op.regime_copart.texto == "sem" for op in ext.opcoes)
    assert all(len(op.tabela) == 10 for op in ext.opcoes)
    assert all(op.reconciliacao and op.reconciliacao.ok for op in ext.opcoes)
    assert mat["valores_reconciliados"]


@pytest.mark.private_corpus
def test_aceite_sulamerica_ajustes_dual_regimes():
    h = _carregar_hashes()["sulamerica_ajustes_dual"]
    ext, mat = _extrair(h)

    assert ext.documento.template_id == "sulamerica-pme-ajustes-dual"
    assert mat["template_reconhecido"]
    assert mat["tabela_extraida"]

    sem = [op for op in ext.opcoes if op.regime_copart and op.regime_copart.texto == "sem"]
    parcial = [op for op in ext.opcoes if op.regime_copart and op.regime_copart.texto == "parcial"]

    assert len(sem) >= 1
    assert len(parcial) >= 1
    assert all(len(op.tabela) == 10 for op in ext.opcoes)
    assert all(op.reconciliacao and op.reconciliacao.ok for op in ext.opcoes)
    assert all(
        op.copart_percentual and op.copart_percentual.inteiro == 30 for op in parcial
    )


@pytest.mark.private_corpus
def test_aceite_porto_27_tabela_geral():
    h = _carregar_hashes()["porto_demonstrativo_27"]
    ext, mat = _extrair(h)

    assert ext.documento.template_id == "porto-demonstrativo-27"
    assert ext.documento.numero_paginas >= 25
    assert mat["template_reconhecido"]
    assert mat["tabela_extraida"]
    assert not any(a.codigo in _CODIGOS_TABELA_AUSENTE for a in ext.alertas)
    assert "Tabela não encontrada" not in " ".join(a.mensagem for a in ext.alertas)

    assert len(ext.opcoes) >= 1
    assert all(len(op.tabela) == 10 for op in ext.opcoes)
    assert mat["exige_selecao_consciente"]
    assert not mat["extracao_financeira_homologada"]


def test_maturidade_distingue_estagios_sintetico():
    from tests.fixtures.cotacao_pdf.build_pdfs import build_sulamerica_sem_copart

    ext = parse_cotacao_pdf(
        build_sulamerica_sem_copart(),
        estudo_id="t",
        documento_id="d",
        nome_arquivo="sint.pdf",
    )
    mat = avaliar_maturidade(ext)
    assert mat["template_reconhecido"]
    assert mat["tabela_extraida"]
    assert mat["valores_reconciliados"]
    assert not mat["proposta_pronta_aplicacao"]
    assert not mat["extracao_financeira_homologada"]
