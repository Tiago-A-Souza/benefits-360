"""Testes — famílias de template e caracterização de corpus (sintético)."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from newport_app.cotacao_pdf.corpus_analyze import caracterizar_pdf
from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from newport_app.cotacao_pdf.template_families import FAMILIAS_POR_ID, identificar_familia
from tests.fixtures.cotacao_pdf.build_pdfs import (
    build_porto_27_paginas,
    build_sulamerica_com_copart,
    build_sulamerica_sem_copart,
)


def _build_amil_texto_4p() -> bytes:
    doc = pymupdf.open()
    for i in range(4):
        p = doc.new_page()
        if i == 0:
            y = 50
            p.insert_text((36, y), "AMIL ONE Cotação Empresarial", fontsize=11)
            for n in range(25):
                y += 12
                p.insert_text((36, y), f"Bloco informativo {n} — condições comerciais e rede credenciada", fontsize=8)
        else:
            p.insert_text((36, 50), "AMIL ONE Cotação Empresarial", fontsize=11)
        if i == 1:
            p.insert_text(
                (36, 80),
                "0 a 18 19 a 23 24 a 28 29 a 33 34 a 38 39 a 43 44 a 48 49 a 53 54 a 58 59+",
                fontsize=8,
            )
            p.insert_text(
                (36, 100),
                "PlanoA R$ 100,00 R$ 110,00 R$ 120,00 R$ 130,00 R$ 140,00 "
                "R$ 150,00 R$ 160,00 R$ 170,00 R$ 180,00 R$ 190,00",
                fontsize=8,
            )
    out = doc.tobytes()
    doc.close()
    return out


def test_familia_porto_27_sintetico():
    with PdfDocumento.abrir(build_porto_27_paginas()) as doc:
        fam = identificar_familia(doc)
    assert fam is not None
    assert fam.id == "porto-demonstrativo-27"


def test_familia_sulamerica_dual_sintetico():
    with PdfDocumento.abrir(build_sulamerica_com_copart()) as doc:
        fam = identificar_familia(doc)
    assert fam is not None
    assert fam.id == "sulamerica-pme-ajustes-dual"


def test_familia_sulamerica_sem_sintetico():
    with PdfDocumento.abrir(build_sulamerica_sem_copart()) as doc:
        fam = identificar_familia(doc)
    assert fam is not None
    assert fam.id.startswith("sulamerica-pme-sem")


def test_familia_amil_texto_sintetico():
    with PdfDocumento.abrir(_build_amil_texto_4p()) as doc:
        fam = identificar_familia(doc)
    assert fam is not None
    assert fam.id == "amil-cotacao-texto-4p"


def test_template_nao_reconhecido_nao_extrai():
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
    assert ext.opcoes == []


def test_operadora_sem_familia_nao_usa_extrator_generico():
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text((36, 36), "SUL AMERICA SAUDE proposta atipica sem tabela tarifaria")
    conteudo = doc.tobytes()
    doc.close()
    ext = parse_cotacao_pdf(
        conteudo,
        estudo_id="t",
        documento_id="d",
        nome_arquivo="sul-atipico.pdf",
    )
    assert ext.estado == "nao_reconhecido"
    assert any(a.codigo == "PDF-TPL-001" for a in ext.alertas)


def test_caracterizacao_sanitizada_sem_nome_arquivo():
    car = caracterizar_pdf(build_porto_27_paginas())
    assert car.hash_sha256
    assert car.familia_id == "porto-demonstrativo-27"
    assert car.reconhecido
    assert "nome" not in str(car.assinatura).lower()
    assert all(isinstance(o.faixas, int) for o in car.opcoes)


def test_todas_familias_tem_extrator():
    for fid, fam in FAMILIAS_POR_ID.items():
        assert fam.extrator is not None, fid


@pytest.mark.private_corpus
def test_corpus_privado_todos_reconhecidos_ou_registrados():
    from newport_app.config.paths import diretorio_corpus_cotacoes
    from newport_app.cotacao_pdf.corpus_analyze import analisar_diretorio

    corpus = diretorio_corpus_cotacoes()
    if not corpus.is_dir():
        pytest.skip("Corpus privado indisponível")
    resumo = analisar_diretorio(corpus)
    assert resumo["total_documentos"] >= 1
    reconhecidos = sum(1 for d in resumo["documentos"] if d.get("reconhecido"))
    assert reconhecidos == resumo["total_documentos"]
