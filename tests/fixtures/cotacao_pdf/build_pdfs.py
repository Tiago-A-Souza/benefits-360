"""PDFs sintéticos com layout equivalente ao corpus Anistia — somente para testes."""

from __future__ import annotations

from dataclasses import dataclass, field

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


_FAIXAS_COLS_SUL = [
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


def _paginas_amil_institucional(doc: pymupdf.Document, n: int = 3) -> None:
    for idx in range(n):
        p = doc.new_page(width=595, height=842)
        p.insert_text((36, 36), "AMIL ONE Cotação Empresarial", fontsize=11)
        y = 60
        for bloco in range(8):
            p.insert_text((36, y), f"Condições comerciais bloco {bloco} rede credenciada", fontsize=8)
            y += 10
        if idx == 0:
            # Família amil-cotacao-texto-4p exige ≥80 palavras na 1ª página.
            y_denso = y + 10
            for par in range(12):
                p.insert_text(
                    (36, y_denso),
                    (
                        f"Parágrafo institucional {par} com rede credenciada, carências, "
                        f"reajuste e condições comerciais do plano empresarial Amil ONE."
                    ),
                    fontsize=7,
                )
                y_denso += 22


def _pagina_amil_tabela(
    page: pymupdf.Page,
    *,
    produto: str,
    valores_centavos: list[int],
) -> None:
    page.insert_text(
        (36, 80),
        "0 a 18 19 a 23 24 a 28 29 a 33 34 a 38 39 a 43 44 a 48 49 a 53 54 a 58 59+",
        fontsize=8,
    )
    parts = []
    for v in valores_centavos:
        if v >= 100_000:
            inteiro = v // 100
            cent = v % 100
            parts.append(
                f"R$ {inteiro // 1000}.{(inteiro // 100) % 10}{(inteiro // 10) % 10}{inteiro % 10},{cent:02d}"
            )
        else:
            parts.append(f"R$ {v // 100},{v % 100:02d}")
    page.insert_text((36, 100), f"{produto} " + " ".join(parts), fontsize=8)


def build_amil_prata_qc_milhar() -> bytes:
    """Caso feliz Amil — PRATA QC com valor acima de mil sem separador de milhar."""
    doc = pymupdf.open()
    _paginas_amil_institucional(doc, 3)
    _pagina_amil_tabela(
        doc.new_page(width=595, height=842),
        produto="PRATA QC COPART",
        valores_centavos=[107_396, 120_000, 130_000, 140_000, 150_000, 160_000, 170_000, 180_000, 190_000, 200_000],
    )
    out = doc.tobytes()
    doc.close()
    return out


def build_amil_bronze_sem_acomodacao() -> bytes:
    """BRONZE sem QC/QP — acomodação ausente na extração."""
    doc = pymupdf.open()
    _paginas_amil_institucional(doc, 2)
    _pagina_amil_tabela(
        doc.new_page(width=595, height=842),
        produto="BRONZE BRASIL I COPART",
        valores_centavos=[17_938, 24_360, 28_595, 31_941, 35_742, 42_176, 51_032, 61_239, 73_487, 88_184],
    )
    out = doc.tobytes()
    doc.close()
    return out


def build_amil_sem_tabela() -> bytes:
    """Âncora Amil sem cabeçalho de faixas — tabela não localizada."""
    doc = pymupdf.open()
    _paginas_amil_institucional(doc, 4)
    out = doc.tobytes()
    doc.close()
    return out


def build_porto_27_serie_p220() -> bytes:
    """Porto 27p com plano série P220 Q (não descartado)."""
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
            page.insert_text((36, 140), "P220 Q COPAR", fontsize=10)
            page.insert_text((36, 160), "3 vidas", fontsize=9)
            page.insert_text((36, 180), "30% de coparticipação", fontsize=9)
            page.insert_text((36, 210), "Subtotal R$ 1.500,82", fontsize=9)
            page.insert_text((36, 230), "IOF R$ 36,08", fontsize=9)
            page.insert_text((36, 250), "Valor total mensal para 3 vidas: R$ 1.551,90", fontsize=9)
        if i == 24:
            page.insert_text((36, 50), "Tabela Geral de Prêmios sem coparticipação", fontsize=10)
            page.insert_text((36, 75), "Plano " + _FAIXAS, fontsize=8)
            page.insert_text((36, 100), "P220 Q COPAR", fontsize=9)
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
            page.insert_text((36, 100), "P220 Q COPAR", fontsize=9)
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
            page.insert_text((36, 70), "P220 Q COPAR Total R$ 1.500,82", fontsize=9)
    out = doc.tobytes()
    doc.close()
    return out


def build_porto_sem_validade() -> bytes:
    """Demonstrativo Porto sem data de validade explícita."""
    doc = pymupdf.open()
    for i in range(27):
        page = doc.new_page(width=595, height=842)
        page.insert_text((36, 36), f"PORTO SEGURO — página {i + 1}", fontsize=10)
        if i == 4:
            page.insert_text((36, 80), "Demonstrativo Total", fontsize=10)
            page.insert_text((36, 100), "Orçamento:3129336", fontsize=9)
            page.insert_text((36, 120), "Realizado: 30/06/2026", fontsize=9)
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
    out = doc.tobytes()
    doc.close()
    return out


def build_porto_sem_tabela_geral() -> bytes:
    """Âncoras Porto com Tabela Geral vazia — planos não extraídos."""
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
        if i == 24:
            page.insert_text((36, 50), "Tabela Geral de Prêmios sem coparticipação", fontsize=10)
            page.insert_text((36, 75), "Plano " + _FAIXAS, fontsize=8)
        if i == 25:
            page.insert_text((36, 50), "Tabela Geral de Prêmios com coparticipação 30%", fontsize=10)
    out = doc.tobytes()
    doc.close()
    return out


def build_sulamerica_faixa_unica_com_vidas() -> bytes:
    """Layout ATEF: nome em 4 linhas, «1 vida» acima das faixas cotadas, acomodação explícita."""
    doc = pymupdf.open()
    _paginas_cabecalho_sulamerica(doc, 4)
    for _ in range(5):
        doc.new_page(width=595, height=842).insert_text((36, 36), "SUL AMERICA SAUDE", fontsize=9)
    page = doc.new_page(width=595, height=842)
    page.insert_text((36, 40), "TABELA DE PREÇOS", fontsize=11)
    page.insert_text((36, 58), "COM COPARTICIPACAO 30%", fontsize=10)
    for rotulo, x in _FAIXAS_COLS_SUL:
        page.insert_text((x, 70), rotulo, fontsize=7)
    page.insert_text((36, 120), "Nacional", fontsize=9)
    page.insert_text((36, 132), "SP (CAP1)", fontsize=9)
    page.insert_text((36, 144), "Direto Nacional", fontsize=9)
    page.insert_text((36, 156), "Apartamento", fontsize=9)
    for idx in (1, 7, 8):
        page.insert_text((_FAIXAS_COLS_SUL[idx][1], 168), "1 vida", fontsize=7)
    for v, (_, x) in zip(_VALORES_SEM, _FAIXAS_COLS_SUL):
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


def build_sulamerica_sem_tabela() -> bytes:
    """Cabeçalho SulAmérica com âncoras mas sem linhas de plano na tabela."""
    doc = pymupdf.open()
    _paginas_cabecalho_sulamerica(doc, 4)
    p4 = doc.new_page(width=595, height=842)
    p4.insert_text(
        (36, 120),
        "Prêmio Saúde: R$ 2.215,76 + IOF (2,38%): R$ 52,74 Total de Prêmio Saúde: R$ 2.268,50",
        fontsize=9,
    )
    p4.insert_text((36, 140), "Validade da cotação: 14/08/2026", fontsize=9)
    for _ in range(4):
        doc.new_page(width=595, height=842).insert_text((36, 36), "SUL AMERICA SAUDE", fontsize=9)
    p9 = doc.new_page(width=595, height=842)
    p9.insert_text((36, 40), "TABELA DE PREÇOS", fontsize=11)
    p9.insert_text((36, 58), "SEM COPARTICIP", fontsize=10)
    p9.insert_text((36, 70), _FAIXAS, fontsize=8)
    out = doc.tobytes()
    doc.close()
    return out


def tabela_bradesco_sintetica() -> list[list]:
    linhas: list[list] = []
    faixas = [
        "Até 18 anos",
        "19 a 23",
        "24 a 28",
        "29 a 33",
        "34 a 38",
        "39 a 43",
        "44 a 48",
        "49 a 53",
        "54 a 58",
        "59 adiante",
    ]
    valores = [35742, 42176, 51032, 61239, 73487, 88184, 87551, 102978, 122543, 214438]
    for rotulo, val in zip(faixas, valores):
        bruto = f"{val // 100},{val % 100:02d}"
        linhas.append([rotulo, None, f"R$ {bruto}", None, None, None, "R$ 22,13", "0", None, "R$ 0,00"])
    linhas.insert(0, ["Perfil 1", None, None])
    linhas.insert(1, ["Plano Saúde", "Nacional III", None, "TN3P"])
    linhas.insert(2, [None, None, "Valores Unitários"])
    linhas.insert(3, ["Faixa Etária", None, "Saúde(R$)", None, None, None, "Dental", "Qtd"])
    return linhas


@dataclass
class BradescoDocSintetico:
    """PdfDocumento mínimo para o parser Bradesco em testes sem PDF real."""

    paginas_texto: list[str] = field(default_factory=list)
    tabelas_p0: list[list[list]] = field(default_factory=list)

    @property
    def numero_paginas(self) -> int:
        return len(self.paginas_texto)

    def texto(self, pagina: int) -> str:
        if pagina < 0 or pagina >= self.numero_paginas:
            return ""
        return self.paginas_texto[pagina]

    def texto_todo(self) -> str:
        return "\n".join(self.paginas_texto)

    def tabelas_pdfplumber(self, pagina: int) -> list[list[list]]:
        if pagina == 0:
            return self.tabelas_p0
        return []


def build_bradesco_doc_caso_feliz() -> BradescoDocSintetico:
    return BradescoDocSintetico(
        paginas_texto=[
            "BRADESCO SAÚDE TN3P",
            (
                "Validade: 15/09/2026\n"
                "Prêmio Saúde R$ 3.574,20\n"
                "I.O.F. R$ 85,07\n"
                "Demais Parcelas R$ 3.659,27"
            ),
        ],
        tabelas_p0=[tabela_bradesco_sintetica()],
    )


def build_bradesco_doc_sem_tabelas() -> BradescoDocSintetico:
    return BradescoDocSintetico(
        paginas_texto=["BRADESCO SAÚDE TN3P", "Resumo sem tabelas."],
        tabelas_p0=[],
    )
