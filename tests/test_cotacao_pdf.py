"""Testes — extração de cotações PDF."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.parsers import porto, sulamerica
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from newport_app.repository.extracao_cotacao import ExtracaoCotacaoRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.extracao_cotacao import ExtracaoCotacaoService

CORPUS_PORTO = Path(r"C:\0-Projetos\0-Claude_Cowork\@Newport\Newport-Teste-ATEF\PORTO.pdf")
CORPUS_SUL = Path(r"C:\0-Projetos\0-Claude_Cowork\@Newport\Newport-Teste-ATEF\SULAMERICA.pdf")


def test_nenhum_valor_extraido_nasce_confirmado():
    paginas = ["PORTO SEGURO"] * 16
    paginas[1] = (
        "Orçamento:123\nEmissão: 01/01/2026 - Validade: 01/02/2026\n"
        "P320 Q Plano R$ 1.500,82\n3 vidas\n30% de coparticipação\n"
        "Total com IOF R$ 1.551,90\nR$ 1.500,82 R$ 15,00 R$ 36,08"
    )
    paginas[13] = (
        "Valores de Prêmio sem coparticipação\n00-18 19-23 24-28 29-33 34-38 "
        "39-43 44-48 49-53 54-58 +59\nP320 Q 303.17 367.66 443.53 507.76 550.16 "
        "568.18 678.70 730.65 902.77 1517.48"
    )
    paginas[14] = (
        "Valores de Prêmio com coparticipação 30%\n00-18 19-23 24-28 29-33 34-38 "
        "39-43 44-48 49-53 54-58 +59\nP320 Q x 227.38 275.75 332.64 380.82 412.62 "
        "426.13 509.02 547.99 677.08 1138.11"
    )
    paginas[15] = "Cotação por faixa etária\nP320 Q Total R$ 1.500,82\n19 a 23 Qtd 1\n49 a 53 Qtd 1\n54 a 58 Qtd 1"
    doc = PdfDocumento.from_paginas(paginas)
    opcoes, _, _ = porto.parse(doc, documento_hash="abc")
    assert opcoes
    for campo in opcoes[0].tabela:
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


@pytest.mark.private_corpus
def test_corpus_porto_integracao():
    if not CORPUS_PORTO.is_file():
        pytest.skip("Corpus privado indisponível")
    conteudo = CORPUS_PORTO.read_bytes()
    ext = parse_cotacao_pdf(
        conteudo,
        estudo_id="homolog",
        documento_id="doc-porto",
        nome_arquivo="PORTO.pdf",
    )
    assert ext.documento.operadora_detectada == "Porto Seguro"
    assert ext.opcoes
    assert len(ext.opcoes[0].tabela) >= 10
    assert not any(c.confirmado for c in ext.campos_extraidos)


@pytest.mark.private_corpus
def test_corpus_sulamerica_integracao():
    if not CORPUS_SUL.is_file():
        pytest.skip("Corpus privado indisponível")
    conteudo = CORPUS_SUL.read_bytes()
    ext = parse_cotacao_pdf(
        conteudo,
        estudo_id="homolog",
        documento_id="doc-sul",
        nome_arquivo="SULAMERICA.pdf",
    )
    assert ext.documento.operadora_detectada == "SulAmérica"
    assert ext.opcoes
    assert ext.opcoes[0].premio_saude and ext.opcoes[0].premio_saude.centavos
