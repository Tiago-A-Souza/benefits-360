"""Testes — extração de cotações PDF."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.cotacao_pdf.extract import PdfDocumento
from tests.fixtures.cotacao_pdf.build_pdfs import build_porto_27_paginas, build_sulamerica_sem_copart
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from newport_app.repository.extracao_cotacao import ExtracaoCotacaoRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.extracao_cotacao import ExtracaoCotacaoService

from newport_app.config.paths import diretorio_corpus_anistia


def test_nenhum_valor_extraido_nasce_confirmado():
    ext = parse_cotacao_pdf(
        build_porto_27_paginas(),
        estudo_id="t",
        documento_id="d",
        nome_arquivo="porto-sint.pdf",
    )
    assert ext.opcoes
    for op in ext.opcoes:
        for campo in op.tabela:
            assert not campo.valor.confirmado
            assert not campo.quantidade.confirmado


def test_documento_nao_reconhecido():
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Documento generico sem operadora.")
    conteudo = doc.tobytes()
    doc.close()
    ext = parse_cotacao_pdf(
        conteudo,
        estudo_id="t",
        documento_id="d",
        nome_arquivo="x.pdf",
    )
    assert ext.estado == "nao_reconhecido"


def test_api_importar_pdf_sintetico(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "e.db")
    cot_repo = ExtracaoCotacaoRepository(tmp_path / "c.db")
    app = create_app(
        repo=repo,
        cotacao_repo=cot_repo,
        uploads_cotacao_dir=tmp_path / "pdfs",
        seed_demos=True,
    )
    client = TestClient(app)
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Texto qualquer.")
    pdf_bytes = doc.tobytes()
    doc.close()
    res = client.post(
        "/api/estudos/demo-12/importar-cotacao-pdf",
        files={"arquivo": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 200
    data = res.json()
    assert "extracao_id" in data


def _corpus_anistia(*nomes: str) -> Path | None:
    base = diretorio_corpus_anistia()
    if not base.is_dir():
        return None
    for nome in nomes:
        hits = list(base.rglob(nome))
        if hits:
            return hits[0]
    return None


@pytest.mark.private_corpus
def test_corpus_porto_integracao():
    path = _corpus_anistia("PORTO.pdf")
    if path is None:
        pytest.skip("Corpus privado indisponível")
    conteudo = path.read_bytes()
    ext = parse_cotacao_pdf(
        conteudo,
        estudo_id="homolog",
        documento_id="doc-porto",
        nome_arquivo="PORTO.pdf",
    )
    assert ext.documento.operadora_detectada == "Porto Seguro"
    assert ext.opcoes
    assert all(len(op.tabela) >= 10 for op in ext.opcoes)
    assert not any(c.confirmado for c in ext.campos_extraidos)


@pytest.mark.private_corpus
def test_corpus_sulamerica_integracao():
    path = _corpus_anistia("SULAMÉRICA SEM CP.pdf", "SULAMERICA SEM CP.pdf")
    if path is None:
        pytest.skip("Corpus privado indisponível")
    conteudo = path.read_bytes()
    ext = parse_cotacao_pdf(
        conteudo,
        estudo_id="homolog",
        documento_id="doc-sul",
        nome_arquivo=path.name,
    )
    assert ext.documento.operadora_detectada == "SulAmérica"
    assert ext.opcoes
    assert all(op.regime_copart.texto == "sem" for op in ext.opcoes)
    assert not any(c.confirmado for c in ext.campos_extraidos)
