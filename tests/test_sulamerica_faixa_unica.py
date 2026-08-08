"""SulAmérica — tabela de faixa única com anotações «N vida» e nome fragmentado."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pymupdf
import pytest

from newport_app.cotacao_pdf.coords_extract import localizar_paginas_tabela_sulamerica
from newport_app.cotacao_pdf.extract import PdfDocumento
import hashlib

from newport_app.cotacao_pdf.parsers.sulamerica import _extrair_financeiro, parse as parse_sulamerica
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from newport_app.cotacao_pdf.sulamerica_table import extrair_tabelas_pagina_sulamerica

_FAIXAS_COLS = [
    ("0 a 18", 121),
    ("19 a 23", 159),
    ("24 a 28", 197),
    ("29 a 33", 235),
    ("34 a 38", 273),
    ("39 a 43", 311),
    ("44 a 48", 349),
    ("49 a 53", 387),
    ("54 a 58", 425),
    ("59+", 463),
]
_VALORES = [
    "283,94",
    "354,92",
    "440,09",
    "488,51",
    "522,71",
    "606,34",
    "724,83",
    "849,51",
    "1.011,33",
    "1.703,59",
]


def _atef_dir() -> Path | None:
    candidatos = [
        Path(r"C:\Users\tiago\Downloads\ATEF-20260807T152847Z-1-001\ATEF"),
        Path(__file__).resolve().parents[1] / ".private" / "corpus" / "ATEF",
    ]
    for base in candidatos:
        if base.is_dir():
            return base
    return None


def _atef_pdf(nome: str) -> Path | None:
    base = _atef_dir()
    if base is None:
        return None
    hits = list(base.rglob(nome))
    return hits[0] if hits else None


def _paginas_cabecalho(doc: pymupdf.Document, n: int = 4) -> None:
    for _ in range(n):
        doc.new_page(width=595, height=842).insert_text((36, 36), "SUL AMERICA SAUDE", fontsize=10)


def build_sulamerica_faixa_unica_com_vidas() -> bytes:
    """Layout ATEF: nome em 4 linhas, «1 vida» acima das faixas cotadas."""
    doc = pymupdf.open()
    _paginas_cabecalho(doc, 4)
    page = doc.new_page(width=595, height=842)
    page.insert_text((36, 40), "TABELA DE PREÇOS", fontsize=11)
    page.insert_text((36, 58), "COM COPARTICIPACAO 30%", fontsize=10)
    for rotulo, x in _FAIXAS_COLS:
        page.insert_text((x, 70), rotulo, fontsize=7)
    page.insert_text((36, 120), "Nacional", fontsize=9)
    page.insert_text((36, 132), "SP (CAP1)", fontsize=9)
    page.insert_text((36, 144), "Direto Nacional", fontsize=9)
    page.insert_text((36, 156), "Apartamento", fontsize=9)
    for idx in (1, 7, 8):
        page.insert_text((_FAIXAS_COLS[idx][1], 168), "1 vida", fontsize=7)
    for v, (_, x) in zip(_VALORES, _FAIXAS_COLS):
        page.insert_text((x, 180), v, fontsize=7)
    page.insert_text(
        (36, 220),
        "Prêmio Saúde: R$ 2.215,76 + IOF (2,38%): R$ 52,74 = Total de Prêmio Saúde: R$ 2.268,50",
        fontsize=8,
    )
    page.insert_text((36, 240), "Validade da cotação: 14/08/2026", fontsize=8)
    out = doc.tobytes()
    doc.close()
    return out


def test_valores_ignoram_anotacoes_vida_intercaladas():
    """Tokens «N vida» entre valores não interrompem a sequência de 10 faixas."""
    from newport_app.cotacao_pdf.sulamerica_table import _valores_de_linha

    xs = [c[1] for c in _FAIXAS_COLS]
    words: list[tuple[float, float, float, float, str]] = []
    # Simula leitura intercalada: valor, anotação, valor…
    seq = [
        (xs[0], "283,94"),
        (xs[1], "354,92"),
        (xs[1] + 8, "1"),
        (xs[1] + 14, "vida"),
        (xs[2], "440,09"),
        (xs[3], "488,51"),
        (xs[4], "522,71"),
        (xs[5], "606,34"),
        (xs[6], "724,83"),
        (xs[7], "849,51"),
        (xs[7] + 8, "1 vida"),
        (xs[8], "1.011,33"),
        (xs[8] + 8, "1"),
        (xs[8] + 14, "vida"),
        (xs[9], "1.703,59"),
    ]
    for x, tok in seq:
        words.append((x, 150.0, x + 20, 160.0, tok))
    vals, _flags = _valores_de_linha(words)
    assert vals == [
        28394,
        35492,
        44009,
        48851,
        52271,
        60634,
        72483,
        84951,
        101133,
        170359,
    ]


def test_sintetico_nome_quatro_linhas_e_financeiro():
    pdf = build_sulamerica_faixa_unica_com_vidas()
    with PdfDocumento.abrir(pdf) as doc:
        paginas = localizar_paginas_tabela_sulamerica(doc)
        assert paginas
        sec = extrair_tabelas_pagina_sulamerica(doc, paginas[-1])
        assert sec is not None
        assert len(sec.linhas) == 1
        nome = sec.linhas[0].plano_nome
        assert "Direto Nacional" in nome
        assert "Apartamento" in nome
        assert sec.linhas[0].acomodacao == "Apartamento"
        qtds = sec.linhas[0].quantidades or []
        assert qtds[1] == 1 and qtds[7] == 1 and qtds[8] == 1
        opcoes, alertas, _meta = parse_sulamerica(
            doc, documento_hash=hashlib.sha256(pdf).hexdigest()
        )
    assert len(opcoes) == 1
    op = opcoes[0]
    assert op.premio_saude and op.premio_saude.centavos == 221576
    assert op.iof and op.iof.centavos == 5274
    assert op.total_recorrente and op.total_recorrente.centavos == 226850
    assert op.validade_oficial and op.validade_oficial.data == date(2026, 8, 14)
    assert not any(a.codigo == "PDF-SUL-001" for a in alertas)


def test_extrair_financeiro_valores_em_linhas_seguintes():
    texto = (
        "Prêmio Saúde: \n + IOF (2,38%): \n = \n"
        "R$ 2.215,76\nR$ 52,74\nTotal de Prêmio Saúde: R$ 2.268,50\n"
    )
    premio, iof, total = _extrair_financeiro(texto)
    assert premio == 221576
    assert iof == 5274
    assert total == 226850


@pytest.mark.private_corpus
def test_atef_7969363_com_copart():
    path = _atef_pdf("SULAMERICA.pdf")
    if path is None:
        pytest.skip("Cotação ATEF SulAmérica indisponível")
    ext = parse_cotacao_pdf(
        path.read_bytes(),
        estudo_id="atef",
        documento_id="7969363",
        nome_arquivo=path.name,
    )
    assert ext.documento.template_id == "sulamerica-pme-copart-v1"
    assert len(ext.opcoes) == 1
    op = ext.opcoes[0]
    vals = [fx.valor.centavos for fx in op.tabela]
    assert vals[1] == 35492
    assert vals[7] == 84951
    assert vals[8] == 101133
    qtds = [
        fx.quantidade.inteiro if fx.quantidade and fx.quantidade.inteiro is not None else None
        for fx in op.tabela
    ]
    assert qtds[1] == 1 and qtds[7] == 1 and qtds[8] == 1
    assert op.premio_saude and op.premio_saude.centavos == 221576
    assert op.iof and op.iof.centavos == 5274
    assert op.total_recorrente and op.total_recorrente.centavos == 226850
    assert op.validade_oficial and op.validade_oficial.data == date(2026, 8, 14)
    assert "Direto Nacional" in (op.plano_nome.texto or "")
    assert "Apartamento" in (op.plano_nome.texto or "")


@pytest.mark.private_corpus
def test_atef_7969408_sem_copart():
    path = _atef_pdf("SULAMERICA SEM CP.pdf")
    if path is None:
        pytest.skip("Cotação ATEF SulAmérica SEM CP indisponível")
    ext = parse_cotacao_pdf(
        path.read_bytes(),
        estudo_id="atef",
        documento_id="7969408",
        nome_arquivo=path.name,
    )
    assert ext.documento.template_id == "sulamerica-pme-sem-cp-v2"
    assert len(ext.opcoes) == 1
    op = ext.opcoes[0]
    vals = [fx.valor.centavos for fx in op.tabela]
    assert vals[1] == 50703
    assert vals[7] == 121357
    assert vals[8] == 144476
    assert op.premio_saude and op.premio_saude.centavos == 316536
    assert op.iof and op.iof.centavos == 7534
    assert op.total_recorrente and op.total_recorrente.centavos == 324070
