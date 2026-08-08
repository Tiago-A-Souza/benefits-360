"""Porto — validade do estudo e reconciliação contra o subtotal do resumo."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from newport_app.cotacao_pdf.coords_extract import extrair_quantidades_faixa_porto
from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.parsers.porto import (
    _extrair_validade_porto,
    nomes_plano_equivalentes,
    normalizar_nome_plano_porto,
)
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from newport_app.config.paths import diretorio_corpus_cotacoes


def _corpus_porto(*nomes: str) -> Path | None:
    base = diretorio_corpus_cotacoes()
    if not base.is_dir():
        return None
    for nome in nomes:
        hits = list(base.rglob(nome))
        if hits:
            return hits[0]
    return None


def test_normalizar_e_casar_nomes_porto():
    assert normalizar_nome_plano_porto("p320  q  copar") == "P320 Q COPAR"
    assert nomes_plano_equivalentes("P320 Q COPAR", "P320 Q COPAR")
    assert nomes_plano_equivalentes("p320 q copar", "P320 Q COPAR")
    assert not nomes_plano_equivalentes("P320 Q COPAR", "P320 Q")
    assert not nomes_plano_equivalentes("P320 Q", "P320 E")


def test_quantidades_faixa_nao_confundem_idade_com_vidas():
    path = _corpus_porto("PORTO3.pdf")
    if path is None:
        pytest.skip("PORTO3.pdf indisponível")
    with PdfDocumento.abrir(path.read_bytes()) as doc:
        qtds = extrair_quantidades_faixa_porto(doc, "P320 Q COPAR")
    assert qtds.get(1) == (1, qtds[1][1])
    assert qtds[1][0] == 1
    assert qtds[7][0] == 1
    assert qtds[8][0] == 1
    assert set(qtds) == {1, 7, 8}


@pytest.mark.private_corpus
def test_porto3_validade_e_reconciliacao_p320_q_copar():
    path = _corpus_porto("PORTO3.pdf")
    if path is None:
        pytest.skip("PORTO3.pdf indisponível")
    raw = path.read_bytes()
    with PdfDocumento.abrir(raw) as doc:
        validade, trecho, pagina = _extrair_validade_porto(doc)
    assert validade == date(2026, 7, 30)
    assert trecho
    assert pagina in {1, 2}

    ext = parse_cotacao_pdf(
        raw,
        estudo_id="porto3",
        documento_id="doc",
        nome_arquivo="PORTO3.pdf",
    )
    assert len(ext.opcoes) == 36
    assert all(
        op.validade_oficial and op.validade_oficial.data == date(2026, 7, 30)
        for op in ext.opcoes
    )
    assert "PDF-PORTO-005" not in {a.codigo for a in ext.alertas}

    p320 = next(
        op
        for op in ext.opcoes
        if (op.plano_nome.texto or "").upper() == "P320 Q COPAR"
    )
    assert p320.premio_saude and p320.premio_saude.centavos == 150_082
    assert p320.reconciliacao
    assert p320.reconciliacao.status == "reconciliado"
    assert p320.reconciliacao.subtotal_calculado_centavos == 150_082
    assert "1.500,82" in (p320.reconciliacao.mensagem or "")
    assert "Confere com o total do documento" in (p320.reconciliacao.mensagem or "")

    outros = [
        op
        for op in ext.opcoes
        if (op.plano_nome.texto or "").upper() != "P320 Q COPAR"
    ]
    assert all(
        op.premio_saude is None or op.premio_saude.centavos is None for op in outros
    )
    assert any(
        op.reconciliacao
        and op.reconciliacao.mensagem
        and "P320 Q COPAR" in op.reconciliacao.mensagem
        and "não este plano" in op.reconciliacao.mensagem
        for op in outros
    )


@pytest.mark.private_corpus
def test_porto_anistia_relata_validade(capsys):
    path = _corpus_porto("PORTO.pdf")
    if path is None:
        pytest.skip("PORTO.pdf indisponível")
    with PdfDocumento.abrir(path.read_bytes()) as doc:
        validade, trecho, _ = _extrair_validade_porto(doc)
    ext = parse_cotacao_pdf(
        path.read_bytes(),
        estudo_id="anistia",
        documento_id="porto",
        nome_arquivo="PORTO.pdf",
    )
    com_val = sum(
        1 for op in ext.opcoes if op.validade_oficial and op.validade_oficial.data
    )
    print(
        f"PORTO.pdf Anistia: validade_extraida={validade} trecho={trecho!r} "
        f"opcoes_com_validade={com_val}/{len(ext.opcoes)}"
    )


@pytest.mark.private_corpus
def test_corpus_porto_validade_e_reconciliacao_relatorio(capsys):
    base = diretorio_corpus_cotacoes()
    if not base.is_dir():
        pytest.skip("Corpus privado indisponível")
    pdfs = sorted({p.resolve() for p in base.rglob("PORTO*.pdf")})
    if not pdfs:
        pytest.skip("Nenhum PORTO*.pdf")
    for pdf in pdfs:
        ext = parse_cotacao_pdf(
            pdf.read_bytes(),
            estudo_id="rel",
            documento_id="d",
            nome_arquivo=pdf.name,
        )
        com_val = sum(
            1 for op in ext.opcoes if op.validade_oficial and op.validade_oficial.data
        )
        reconciliados = sum(
            1
            for op in ext.opcoes
            if op.reconciliacao and op.reconciliacao.status == "reconciliado"
        )
        print(
            f"{pdf.name}: {len(ext.opcoes)} planos, "
            f"{com_val} com validade, {reconciliados} reconciliados"
        )
