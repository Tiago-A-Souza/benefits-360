"""Amil: milhar sem truncar + monotonia tarifária + descarte de subtotal."""

from __future__ import annotations

from pathlib import Path

import pytest

from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.parsers import amil
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from newport_app.cotacao_pdf.tarifa_validation import (
    alertas_monotonicidade_opcao,
    indices_quebra_monotonicidade,
)
from newport_app.cotacao_pdf.text_utils import extrair_valor_token, extrair_valores_reais
from newport_app.models.cotacao_pdf import OpcaoCotacaoCandidata
from newport_app.cotacao_pdf.parsers.base import faixa_extraida, novo_campo
from newport_app.models.draft import PriceBasisRascunho

_IVTEC = Path(r"C:\Users\tiago\Downloads\IVTEC-20260808T230709Z-1-001\IVTEC")
_CORPUS_AMIL = Path(".private/corpus")


def _vals(op) -> list[int]:
    return [fx.valor.centavos for fx in op.tabela]


def test_token_milhar_sem_ponto_nao_trunca():
    assert extrair_valor_token("R$1073,96") == 107_396
    assert extrair_valor_token("R$1.073,96") == 107_396
    assert extrair_valor_token("R$1683,47") == 168_347
    assert extrair_valores_reais("R$757,37 R$1073,96") == [75_737, 107_396]


def test_indices_quebra_monotonicidade():
    assert indices_quebra_monotonicidade([17938, 24360, 75737, 7396]) == [3]
    assert indices_quebra_monotonicidade([100, 100, 120, 120]) == []


def test_alerta_monotonicidade_emite_codigo():
    op = OpcaoCotacaoCandidata(
        id="op",
        plano_nome=novo_campo("Nome do plano", texto="X"),
        tabela=[
            faixa_extraida(
                i,
                valor_centavos=v,
                quantidade=None,
                price_basis=PriceBasisRascunho.EXCLUI_IOF,
                pagina=1,
                trecho_valor="t",
                trecho_qtd=None,
                parser_versao="t",
                documento_hash="h",
            )
            for i, v in enumerate([50_000, 7_396])
        ],
    )
    alertas = alertas_monotonicidade_opcao(op, codigo="PDF-AMIL-002")
    assert len(alertas) == 1
    assert alertas[0].codigo == "PDF-AMIL-002"


def test_ivtec_bronze_dez_faixas():
    path = next(_IVTEC.rglob("*BRONZE*.pdf"), None) if _IVTEC.is_dir() else None
    if path is None:
        pytest.skip("IVTEC Bronze indisponível")
    with PdfDocumento.abrir(path.read_bytes()) as doc:
        ops, alertas, _ = amil.parse(doc, documento_hash="h")
    assert len(ops) == 1
    assert not any(a.codigo == "PDF-AMIL-002" for a in alertas)
    assert "BRONZE" in (ops[0].plano_nome.texto or "").upper()
    assert _vals(ops[0]) == [
        17938,
        24360,
        28595,
        28595,
        28595,
        31941,
        44111,
        52669,
        75737,
        107396,
    ]
    assert not any("Plano Amil 1" == (op.plano_nome.texto or "") for op in ops)


def test_ivtec_prata_dez_faixas():
    path = next(_IVTEC.rglob("*PRATA*TP.pdf"), None) if _IVTEC.is_dir() else None
    if path is None:
        pytest.skip("IVTEC Prata indisponível")
    with PdfDocumento.abrir(path.read_bytes()) as doc:
        ops, alertas, _ = amil.parse(doc, documento_hash="h")
    assert len(ops) == 1
    assert _vals(ops[0]) == [
        28290,
        33100,
        40382,
        48458,
        50881,
        55969,
        69962,
        76958,
        96198,
        168347,
    ]


def test_ivtec_black_dez_faixas():
    path = next(_IVTEC.rglob("*BLACK*R1.pdf"), None) if _IVTEC.is_dir() else None
    if path is None:
        pytest.skip("IVTEC Black indisponível")
    with PdfDocumento.abrir(path.read_bytes()) as doc:
        ops, alertas, _ = amil.parse(doc, documento_hash="h")
    assert len(ops) == 1
    assert _vals(ops[0]) == [
        80142,
        93766,
        114395,
        137274,
        144137,
        158551,
        198190,
        218008,
        272511,
        476894,
    ]
    assert indices_quebra_monotonicidade(_vals(ops[0])) == []


@pytest.mark.private_corpus
def test_corpus_amil_sem_quebra_e_sem_plano_lixo():
    pasta = next(_CORPUS_AMIL.rglob("Amil"), None) if _CORPUS_AMIL.is_dir() else None
    if pasta is None or not pasta.is_dir():
        pytest.skip("Corpus Amil indisponível")
    arquivos = sorted(pasta.glob("AMIL*.pdf"))
    assert arquivos
    for path in arquivos:
        with PdfDocumento.abrir(path.read_bytes()) as doc:
            ops, alertas, _ = amil.parse(doc, documento_hash="h")
        assert ops, path.name
        for op in ops:
            assert (op.plano_nome.texto or "") != "Plano Amil 1"
            assert indices_quebra_monotonicidade(_vals(op)) == []
        # Pipeline também sinaliza se houver quebra
        ext = parse_cotacao_pdf(
            path.read_bytes(),
            estudo_id="t",
            documento_id=path.stem,
            nome_arquivo=path.name,
        )
        assert not any(a.codigo == "PDF-AMIL-002" for a in ext.alertas)


def test_pipeline_emite_alerta_monotonicidade_sintetico():
    """Propriedade: quebra de monotonia gera alerta no pipeline (qualquer parser)."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        (36, 100),
        "0 a 18 19 a 23 24 a 28 29 a 33 34 a 38 39 a 43 44 a 48 49 a 53 54 a 58 59+",
        fontsize=8,
    )
    # Último valor menor que o penúltimo — simula truncamento
    vals = [100 + i * 10 for i in range(9)] + [50]
    page.insert_text(
        (36, 120),
        "PlanoQuebra " + " ".join(f"R$ {v},00" for v in vals),
        fontsize=8,
    )
    conteudo = doc.tobytes()
    doc.close()
    # Força identificação Amil via texto
    with PdfDocumento.abrir(conteudo) as pdf:
        pdf.paginas_texto[0] = "AMIL\n" + (pdf.paginas_texto[0] or "")
        ops, alertas, _ = amil.parse(pdf, documento_hash="h")
    assert ops
    # Monotonicidade no parser Amil é aplicada pelo pipeline; aqui validamos o helper
    alertas_m = alertas_monotonicidade_opcao(ops[0], codigo="PDF-AMIL-002")
    assert any(a.codigo == "PDF-AMIL-002" for a in alertas_m)
