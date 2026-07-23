"""Regressão — nomes de plano sem preço da primeira faixa."""

from __future__ import annotations

from newport_app.cotacao_pdf.coords_extract import _limpar_sufixo_preco_nome, _nome_plano_de_texto
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from tests.fixtures.cotacao_pdf.build_pdfs import build_porto_27_paginas


def test_nome_plano_porto_sem_primeiro_valor_na_linha():
    valores = [31655, 36766, 44353, 50776, 55016, 56818, 67870, 73065, 90277, 151748]
    texto = "BRONZE BRASIL I E 316,55 367,66 443,53 507,76 550,16 568,18 678,70 730,65 902,77 1517,48"
    assert _nome_plano_de_texto(texto, valores) == "BRONZE BRASIL I E"


def test_nome_plano_porto_sem_decimal_colado():
    valores = [31655, 36766, 44353, 50776, 55016, 56818, 67870, 73065, 90277, 151748]
    assert _limpar_sufixo_preco_nome("BRONZE BRASIL I E 316", valores) == "BRONZE BRASIL I E"


def test_nome_plano_porto_codigo_p320():
    valores = [30317] * 10
    texto = "P320 Q COPAR 303,17 367,66 443,53 507,76 550,16 568,18 678,70 730,65 902,77 1517,48"
    assert _nome_plano_de_texto(texto, valores) == "P320 Q COPAR"


def test_regressao_porto_sintetico_nomes_limpos():
    ext = parse_cotacao_pdf(
        build_porto_27_paginas(),
        estudo_id="t",
        documento_id="d",
        nome_arquivo="sint.pdf",
    )
    for op in ext.opcoes:
        nome = op.plano_nome.texto or ""
        assert not nome.endswith(("316", "303", "227"))
        if op.tabela and op.tabela[0].valor.centavos is not None:
            parte = str(op.tabela[0].valor.centavos // 100)
            assert not nome.endswith(parte)
