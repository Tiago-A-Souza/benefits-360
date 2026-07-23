"""PDFs sintéticos com layout equivalente ao corpus Anistia — somente para testes."""

from __future__ import annotations

import pymupdf

_VALORES_SEM = [
    "283,94",
    "354,92",
    "440,09",
    "488,51",
    "522,71",
    "606,34",
    "724,83",
    "849,51",
    "1011,33",
    "1703,59",
]
_VALORES_COM = [
    "212,96",
    "266,19",
    "330,07",
    "366,38",
    "392,03",
    "454,76",
    "543,62",
    "637,13",
    "758,50",
    "1277,69",
]
_FAIXAS = "0 a 18  19 a 23  24 a 28  29 a 33  34 a 38  39 a 43  44 a 48  49 a 53  54 a 58  59+"


def _paginas_cabecalho_sulamerica(doc: pymupdf.Document, total: int) -> None:
    for _ in range(total):
        doc.new_page(width=595, height=842).insert_text((36, 36), "SUL AMERICA SAUDE", fontsize=10)


def _pagina_sulamerica_tabela(
    page: pymupdf.Page,
    *,
    titulo_regime: str,
    plano: str,
    valores: list[str],
) -> None:
    page.insert_text((36, 40), "TABELA DE PREÇOS", fontsize=11)
    page.insert_text((36, 58), titulo_regime, fontsize=10)
    page.insert_text((36, 70), _FAIXAS, fontsize=8)
    page.insert_text((36, 95), plano, fontsize=9)
    x = 150
    for v in valores:
        page.insert_text((x, 95), f"R$ {v}", fontsize=7)
        x += 38


def build_sulamerica_sem_copart() -> bytes:
    doc = pymupdf.open()
    _paginas_cabecalho_sulamerica(doc, 4)
    p4 = doc.new_page(width=595, height=842)
    p4.insert_text(
        (36, 120),
        "Prêmio Saúde: R$ 2.215,76 + IOF (2,38%): R$ 52,74 Total de Prêmio Saúde: R$ 2.268,50",
        fontsize=9,
    )
    p4.insert_text((36, 140), "Validade da cotação: 14/08/2026", fontsize=9)
    p4.insert_text(
        (36, 180),
        "A coparticipação é aplicada somente em procedimentos eletivos conforme contrato.",
        fontsize=8,
    )
    for _ in range(4):
        doc.new_page(width=595, height=842).insert_text((36, 36), "SUL AMERICA SAUDE", fontsize=9)
    p9 = doc.new_page(width=595, height=842)
    _pagina_sulamerica_tabela(
        p9,
        titulo_regime="SEM COPARTICIP",
        plano="Direto SP CAP1",
        valores=_VALORES_SEM,
    )
    out = doc.tobytes()
    doc.close()
    return out


def build_sulamerica_com_copart() -> bytes:
    doc = pymupdf.open()
    _paginas_cabecalho_sulamerica(doc, 4)
    p4 = doc.new_page(width=595, height=842)
    p4.insert_text((36, 120), "Total de Prêmio Saúde: R$ 1.701,38", fontsize=9)
    for _ in range(7):
        doc.new_page(width=595, height=842).insert_text((36, 36), "SUL AMERICA SAUDE", fontsize=9)
    p12 = doc.new_page(width=595, height=842)
    _pagina_sulamerica_tabela(
        p12,
        titulo_regime="SEM COPART",
        plano="Direto SP CAP1",
        valores=_VALORES_SEM,
    )
    p13 = doc.new_page(width=595, height=842)
    _pagina_sulamerica_tabela(
        p13,
        titulo_regime="30% DE COPART",
        plano="Direto SP CAP1",
        valores=_VALORES_COM,
    )
    out = doc.tobytes()
    doc.close()
    return out


def build_porto_27_paginas() -> bytes:
    doc = pymupdf.open()
    for i in range(27):
        page = doc.new_page(width=595, height=842)
        page.insert_text((36, 36), f"PORTO SEGURO — página {i + 1}", fontsize=10)
        if i == 4:
            page.insert_text((36, 80), "Demonstrativo Total", fontsize=10)
            page.insert_text((36, 100), "Orçamento:3129336", fontsize=9)
            page.insert_text(
                (36, 120),
                "Realizado: 30/06/2026 - Validade: 30/07/2026",
                fontsize=9,
            )
            page.insert_text((36, 140), "P320 Q COPAR", fontsize=10)
            page.insert_text((36, 160), "3 vidas", fontsize=9)
            page.insert_text((36, 180), "30% de coparticipação", fontsize=9)
            page.insert_text((36, 210), "Subtotal R$ 1.500,82", fontsize=9)
            page.insert_text((36, 230), "IOF R$ 36,08", fontsize=9)
            page.insert_text((36, 250), "Valor total mensal para 3 vidas: R$ 1.551,90", fontsize=9)
        if i == 24:
            page.insert_text((36, 50), "Tabela Geral de Prêmios sem coparticipação", fontsize=10)
            page.insert_text((36, 75), "Plano " + _FAIXAS, fontsize=8)
            page.insert_text((36, 100), "P320 Q COPAR", fontsize=9)
            vals = [
                "303,17",
                "367,66",
                "443,53",
                "507,76",
                "550,16",
                "568,18",
                "678,70",
                "730,65",
                "902,77",
                "1517,48",
            ]
            x = 150
            for v in vals:
                page.insert_text((x, 100), v, fontsize=7)
                x += 38
        if i == 25:
            page.insert_text((36, 50), "Tabela Geral de Prêmios com coparticipação 30%", fontsize=10)
            page.insert_text((36, 75), "Plano " + _FAIXAS, fontsize=8)
            page.insert_text((36, 100), "P320 Q COPAR", fontsize=9)
            vals = [
                "227,38",
                "275,75",
                "332,64",
                "380,82",
                "412,62",
                "426,13",
                "509,02",
                "547,99",
                "677,08",
                "1138,11",
            ]
            x = 150
            for v in vals:
                page.insert_text((x, 100), v, fontsize=7)
                x += 38
        if i == 26:
            page.insert_text((36, 50), "Cotação por faixa etária", fontsize=10)
            page.insert_text((36, 70), "P320 Q COPAR Total R$ 1.500,82", fontsize=9)
            page.insert_text((36, 90), "19 a 23 anos 1", fontsize=8)
            page.insert_text((36, 105), "49 a 53 anos 1", fontsize=8)
            page.insert_text((36, 120), "54 a 58 anos 1", fontsize=8)
    out = doc.tobytes()
    doc.close()
    return out
