"""Parser SulAmérica — tabela por faixa etária."""

from __future__ import annotations

import re
import unicodedata
import uuid

from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.parsers.base import faixa_extraida, novo_campo
from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
from newport_app.cotacao_pdf.text_utils import (
    extrair_datas,
    extrair_primeiro_reais,
    extrair_valores_reais,
)
from newport_app.models.cotacao_pdf import AlertaExtracaoCotacao, OpcaoCotacaoCandidata
from newport_app.models.draft import PriceBasisRascunho

PARSER_VERSAO = "sulamerica@1.0.0"
OPERADORA = "SulAmérica"
TEMPLATE_ID = "sulamerica-pme-v1"


def _ascii_upper(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()


def identificar(doc: PdfDocumento) -> bool:
    amostra = _ascii_upper(doc.texto_todo()[:12000])
    return "SUL" in amostra and "AMERICA" in amostra


def _linha_valores_faixa(doc: PdfDocumento) -> tuple[list[int], str | None, int]:
    melhor: tuple[list[int], str | None, int] | None = None
    for pagina in range(doc.numero_paginas):
        texto = doc.texto(pagina)
        for linha in doc.linhas(pagina):
            if linha.count("R$") >= 8:
                valores = extrair_valores_reais(linha)
                if len(valores) >= 10:
                    return valores[:10], linha, pagina + 1
        valores = extrair_valores_reais(texto)
        for i in range(len(valores) - 9):
            bloco = valores[i : i + 10]
            if bloco[0] < 5000 or bloco[-1] <= bloco[0]:
                continue
            if all(bloco[j] <= bloco[j + 1] for j in range(9)):
                candidato = (bloco, texto[max(0, i - 1) : i + 80], pagina + 1)
                if melhor is None or bloco[0] > melhor[0][0]:
                    melhor = candidato
    if melhor:
        return melhor
    return [], None, 0


def _extrair_financeiro(texto: str) -> tuple[int | None, int | None, int | None]:
    from newport_app.siscor_importer.money import valor_para_centavos

    match_total = re.search(
        r"Total de Pr[eê]mio Sa[uú]de:\s*R\$\s*([\d.,]+)",
        texto,
        re.IGNORECASE,
    )
    total = valor_para_centavos(match_total.group(1)) if match_total else None

    idx = re.search(r"Pr[eê]mio\s*Sa[uú]de", texto, re.IGNORECASE)
    if idx:
        chunk = texto[idx.start() : idx.start() + 400]
        vals = extrair_valores_reais(chunk)
        if len(vals) >= 2:
            premio, iof = vals[0], vals[1]
            if total is None and len(vals) >= 3:
                total = vals[2]
            return premio, iof, total
    return None, None, total


def parse(
    doc: PdfDocumento,
    *,
    documento_hash: str,
) -> tuple[list[OpcaoCotacaoCandidata], list[AlertaExtracaoCotacao], dict]:
    alertas: list[AlertaExtracaoCotacao] = []
    meta: dict = {}
    valores, trecho, pagina = _linha_valores_faixa(doc)
    if not valores:
        alertas.append(
            AlertaExtracaoCotacao(
                codigo="PDF-SUL-001",
                mensagem="Tabela de valores por faixa não encontrada.",
                severidade="alerta",
            )
        )
        return [], alertas, meta

    plano_nome = "Direto SP (CAP1)"
    for pagina_i in range(doc.numero_paginas):
        for linha in doc.linhas(pagina_i):
            if "CAP" in linha.upper() or "DIRETO" in linha.upper():
                plano_nome = linha.strip()
                break

    texto_todo = doc.texto_todo()
    validade = None
    match_val = re.search(
        r"[Vv]alidade[^:]*:\s*(\d{2}/\d{2}/\d{4})",
        texto_todo,
    )
    if match_val:
        datas = extrair_datas(match_val.group(0))
        validade = datas[0] if datas else None

    premio, iof, total = _extrair_financeiro(texto_todo)

    com_copart = "coparticip" in texto_todo.lower()
    tabela = [
        faixa_extraida(
            idx,
            valor_centavos=centavos,
            quantidade=None,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            pagina=pagina,
            trecho_valor=trecho,
            trecho_qtd=None,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        )
        for idx, centavos in enumerate(valores)
    ]

    opcao = OpcaoCotacaoCandidata(
        id=str(uuid.uuid4()),
        operadora=novo_campo(
            "Operadora",
            texto=OPERADORA,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        plano_nome=novo_campo(
            "Nome do plano",
            texto=plano_nome,
            pagina=pagina,
            trecho=trecho,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        regime_copart=novo_campo(
            "Regime de coparticipação",
            texto="parcial" if com_copart else "sem",
            estado="revisar",
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        tabela=tabela,
        premio_saude=novo_campo(
            "Prêmio saúde",
            centavos=premio,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        iof=novo_campo(
            "IOF",
            centavos=iof,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        total_recorrente=novo_campo(
            "Total mensal",
            centavos=total,
            price_basis=PriceBasisRascunho.INCLUI_IOF,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        validade_oficial=novo_campo(
            "Validade",
            data=validade,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
    )
    reconciliar_opcao(opcao)
    meta["validade_oficial"] = validade
    return [opcao], alertas, meta
