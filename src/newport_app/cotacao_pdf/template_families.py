"""Famílias de template PDF — identificação por âncoras estruturais (ETAPA corpus)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Callable

from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.models.cotacao_pdf import AlertaExtracaoCotacao, OpcaoCotacaoCandidata

ParseFn = Callable[[PdfDocumento, str], tuple[list[OpcaoCotacaoCandidata], list[AlertaExtracaoCotacao], dict]]


def _norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()


@dataclass(frozen=True)
class FamiliaTemplate:
    id: str
    operadora: str
    rotulo: str
    parser_versao: str
    ancora_obrigatorias: tuple[str, ...]
    ancora_proibidas: tuple[str, ...] = ()
    paginas_min: int = 1
    paginas_max: int = 999
    paginas_com_ancora: tuple[str, ...] = ()
    extrator: ParseFn | None = field(default=None, compare=False, repr=False)

    def pontuar(self, doc: PdfDocumento, texto_norm: str) -> int:
        n = doc.numero_paginas
        if n < self.paginas_min or n > self.paginas_max:
            return -1
        for proibida in self.ancora_proibidas:
            if proibida in texto_norm:
                return -1
        score = 0
        for ancora in self.ancora_obrigatorias:
            if ancora in texto_norm:
                score += 10
            else:
                return -1
        for ancora_pag in self.paginas_com_ancora:
            if any(ancora_pag in _norm(doc.texto(i)) for i in range(n)):
                score += 5
            else:
                return -1
        return score


def _contar_paginas_tabela_precos(doc: PdfDocumento) -> int:
    count = 0
    for i in range(doc.numero_paginas):
        t = _norm(doc.texto(i))
        if "TABELA DE PRECOS" in t and re.search(r"0\s*A\s*18", t):
            count += 1
    return count


def _tem_regime_duplo_tabela(doc: PdfDocumento) -> bool:
    sem = parcial = False
    for i in range(doc.numero_paginas):
        t = _norm(doc.texto(i))
        if "TABELA DE PRECOS" not in t:
            continue
        if "SEM COPART" in t:
            sem = True
        if re.search(r"\d{1,2}%\s*DE\s*COPART", t) or (
            "COPARTICIP" in t and "SEM COPART" not in t and "TABELA DE PRECOS" in t
        ):
            parcial = True
    return sem and parcial


def _registrar_familias() -> list[FamiliaTemplate]:
    from newport_app.cotacao_pdf.parsers import amil, omint, porto, sulamerica

    return [
        FamiliaTemplate(
            id="porto-demonstrativo-27",
            operadora="Porto Seguro",
            rotulo="Porto — orçamento longo (Demonstrativo Total + Tabela Geral 27 pág.)",
            parser_versao=porto.PARSER_VERSAO,
            ancora_obrigatorias=("PORTO", "TABELA GERAL DE PREM", "DEMONSTRATIVO TOTAL"),
            ancora_proibidas=(),
            paginas_min=25,
            paginas_max=30,
            extrator=porto.parse,
        ),
        FamiliaTemplate(
            id="porto-tabela-geral-15",
            operadora="Porto Seguro",
            rotulo="Porto — orçamento médio (Tabela Geral ~15–16 pág.)",
            parser_versao=porto.PARSER_VERSAO,
            ancora_obrigatorias=("PORTO", "TABELA GERAL DE PREM", "BX865J"),
            ancora_proibidas=("DEMONSTRATIVO TOTAL",),
            paginas_min=14,
            paginas_max=18,
            extrator=porto.parse,
        ),
        FamiliaTemplate(
            id="sulamerica-pme-sem-cp-13",
            operadora="SulAmérica",
            rotulo="SulAmérica PME — sem copart (layout 12–14 pág.)",
            parser_versao=sulamerica.PARSER_VERSAO,
            ancora_obrigatorias=("SUL", "AMERICA", "TABELA DE PRECOS", "SEM COPART"),
            ancora_proibidas=("COM COPARTICIP", "30% DE COPART"),
            paginas_min=12,
            paginas_max=14,
            extrator=sulamerica.parse,
        ),
        FamiliaTemplate(
            id="sulamerica-pme-copart-13",
            operadora="SulAmérica",
            rotulo="SulAmérica PME — com copart (layout 12–14 pág.)",
            parser_versao=sulamerica.PARSER_VERSAO,
            ancora_obrigatorias=("SUL", "AMERICA", "TABELA DE PRECOS"),
            ancora_proibidas=("SEM COPARTICIP",),
            paginas_min=12,
            paginas_max=14,
            extrator=sulamerica.parse,
        ),
        FamiliaTemplate(
            id="sulamerica-pme-ajustes-dual",
            operadora="SulAmérica",
            rotulo="SulAmérica PME — tabelas duplas (sem + % copart em págs. separadas)",
            parser_versao=sulamerica.PARSER_VERSAO,
            ancora_obrigatorias=("SUL", "AMERICA", "TABELA DE PRECOS"),
            paginas_min=12,
            paginas_max=14,
            extrator=sulamerica.parse,
        ),
        FamiliaTemplate(
            id="sulamerica-pme-sem-cp-v2",
            operadora="SulAmérica",
            rotulo="SulAmérica PME — sem coparticipação (cabeçalho explícito)",
            parser_versao=sulamerica.PARSER_VERSAO,
            ancora_obrigatorias=("SUL", "AMERICA", "TABELA DE PRECOS", "SEM COPARTICIP"),
            ancora_proibidas=("30% DE COPART", "COM COPARTICIP"),
            paginas_min=10,
            paginas_max=12,
            extrator=sulamerica.parse,
        ),
        FamiliaTemplate(
            id="sulamerica-pme-copart-v1",
            operadora="SulAmérica",
            rotulo="SulAmérica PME — com coparticipação (cabeçalho único)",
            parser_versao=sulamerica.PARSER_VERSAO,
            ancora_obrigatorias=("SUL", "AMERICA", "TABELA DE PRECOS", "COM COPARTICIP"),
            ancora_proibidas=("SEM COPARTICIP",),
            paginas_min=10,
            paginas_max=11,
            extrator=sulamerica.parse,
        ),
        FamiliaTemplate(
            id="sulamerica-pme-sem-cp-v1",
            operadora="SulAmérica",
            rotulo="SulAmérica PME — sem copart (layout 9–10 pág., rótulo curto «SEM COPART»)",
            parser_versao=sulamerica.PARSER_VERSAO,
            ancora_obrigatorias=("SUL", "AMERICA", "TABELA DE PRECOS", "SEM COPART"),
            ancora_proibidas=("COM COPARTICIP", "30% DE COPART", "PROPOSTA COMERCIAL PME MAIS", "SEM COPARTICIP"),
            paginas_min=9,
            paginas_max=10,
            extrator=sulamerica.parse,
        ),
        FamiliaTemplate(
            id="sulamerica-pme-copart-pct-11",
            operadora="SulAmérica",
            rotulo="SulAmérica PME — copart por percentual (30% DE COPART, 10–11 pág.)",
            parser_versao=sulamerica.PARSER_VERSAO,
            ancora_obrigatorias=("SUL", "AMERICA", "TABELA DE PRECOS", "30% DE COPART"),
            ancora_proibidas=("SEM COPARTICIP", "COM COPARTICIP"),
            paginas_min=10,
            paginas_max=11,
            extrator=sulamerica.parse,
        ),
        FamiliaTemplate(
            id="amil-cotacao-texto-4p",
            operadora="Amil",
            rotulo="Amil — cotação textual (4 pág., texto selecionável)",
            parser_versao=amil.PARSER_VERSAO,
            ancora_obrigatorias=("AMIL", "COTAC"),
            paginas_min=3,
            paginas_max=5,
            extrator=amil.parse,
        ),
        FamiliaTemplate(
            id="amil-cotacao-visual-8p",
            operadora="Amil",
            rotulo="Amil — cotação visual (8 pág., layout escaneado/OCR)",
            parser_versao=amil.PARSER_VERSAO,
            ancora_obrigatorias=("AMIL", "COTAC"),
            paginas_min=7,
            paginas_max=9,
            extrator=amil.parse,
        ),
        FamiliaTemplate(
            id="omint-ocr-v1",
            operadora="Omint",
            rotulo="Omint — documento escaneado (OCR necessário)",
            parser_versao=omint.PARSER_VERSAO,
            ancora_obrigatorias=("OMINT",),
            paginas_min=1,
            paginas_max=999,
            extrator=omint.parse,
        ),
    ]


FAMILIAS: list[FamiliaTemplate] = _registrar_familias()
FAMILIAS_POR_ID: dict[str, FamiliaTemplate] = {f.id: f for f in FAMILIAS}


def identificar_familia(doc: PdfDocumento) -> FamiliaTemplate | None:
    """Identifica família de template antes da extração. Retorna None se ambíguo/ausente."""
    texto_norm = _norm(doc.texto_todo())
    candidatas: list[tuple[int, FamiliaTemplate]] = []

    for familia in FAMILIAS:
        score = familia.pontuar(doc, texto_norm)
        if score < 0:
            continue
        if familia.id == "sulamerica-pme-ajustes-dual" and not _tem_regime_duplo_tabela(doc):
            continue
        if familia.id in {
            "sulamerica-pme-sem-cp-v1",
            "sulamerica-pme-sem-cp-v2",
            "sulamerica-pme-sem-cp-13",
        } and _tem_regime_duplo_tabela(doc):
            continue
        if familia.id == "sulamerica-pme-copart-13":
            t = _norm(doc.texto_todo())
            if not ("30% DE COPART" in t or "COM COPARTICIP" in t):
                continue
            if _tem_regime_duplo_tabela(doc):
                continue
        if familia.id == "sulamerica-pme-copart-v1" and _tem_regime_duplo_tabela(doc):
            continue
        if familia.id == "sulamerica-pme-copart-pct-11" and _tem_regime_duplo_tabela(doc):
            continue
        if familia.id == "amil-cotacao-texto-4p":
            words0 = doc.palavras_pymupdf(0)
            if len(words0) < 80:
                continue
        if familia.id == "amil-cotacao-visual-8p":
            words0 = doc.palavras_pymupdf(0)
            if len(words0) >= 80:
                continue
        candidatas.append((score, familia))

    if not candidatas:
        return None
    candidatas.sort(
        key=lambda x: (
            -x[0],
            -len(x[1].ancora_obrigatorias),
            -sum(len(a) for a in x[1].ancora_obrigatorias),
            x[1].id,
        )
    )
    melhor_score = candidatas[0][0]

    def _especificidade(f: FamiliaTemplate) -> tuple[int, int]:
        return len(f.ancora_obrigatorias), sum(len(a) for a in f.ancora_obrigatorias)

    ref = _especificidade(candidatas[0][1])
    empate = [
        f for s, f in candidatas if s == melhor_score and _especificidade(f) == ref
    ]
    if len(empate) > 1:
        return None
    return candidatas[0][1]


def operadora_candidata(doc: PdfDocumento) -> str | None:
    t = _norm(doc.texto_todo()[:8000])
    if "PORTO" in t or "BX865J" in t:
        return "Porto Seguro"
    if "SUL" in t and "AMERICA" in t:
        return "SulAmérica"
    if "AMIL" in t:
        return "Amil"
    if "OMINT" in t:
        return "Omint"
    return None
