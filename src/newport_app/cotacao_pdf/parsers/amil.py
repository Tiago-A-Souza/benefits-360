"""Parser Amil — extração por posicionamento (PyMuPDF)."""

from __future__ import annotations

import re
import uuid

from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.faixas import faixa_de_rotulo
from newport_app.cotacao_pdf.parsers.base import faixa_extraida, novo_campo
from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
from newport_app.models.cotacao_pdf import AlertaExtracaoCotacao, OpcaoCotacaoCandidata
from newport_app.models.draft import PriceBasisRascunho
from newport_app.siscor_importer.money import valor_para_centavos

PARSER_VERSAO = "amil@1.0.0"
OPERADORA = "Amil"
TEMPLATE_ID = "amil-visual-v1"


def identificar(doc: PdfDocumento) -> bool:
    amostra = doc.texto_todo().upper()
    return "AMIL" in amostra


def _linhas_por_y(words: list[tuple]) -> dict[int, list[tuple]]:
    rows: dict[int, list[tuple]] = {}
    for w in words:
        y = int(round(w[1], 0))
        rows.setdefault(y, []).append(w)
    return rows


def _valores_linha(words: list[tuple]) -> list[int]:
    texto = " ".join(w[4] for w in sorted(words, key=lambda x: x[0]))
    vals = []
    for match in re.finditer(r"R?\$?\s*([\d]{1,3}(?:\.\d{3})*,\d{2})", texto):
        v = valor_para_centavos(match.group(1))
        if v is not None:
            vals.append(v)
    return vals


def parse(
    doc: PdfDocumento,
    *,
    documento_hash: str,
) -> tuple[list[OpcaoCotacaoCandidata], list[AlertaExtracaoCotacao], dict]:
    alertas: list[AlertaExtracaoCotacao] = []
    meta: dict = {}
    pagina_tabela = None
    planos: list[tuple[str, list[int], int, str]] = []

    for pagina in range(doc.numero_paginas):
        words = doc.palavras_pymupdf(pagina)
        if not words:
            continue
        rows = _linhas_por_y(words)
        header_y = None
        for y, ws in rows.items():
            linha = " ".join(w[4] for w in sorted(ws, key=lambda x: x[0]))
            if faixa_de_rotulo("0 a 18") is not None and "18" in linha and "19" in linha:
                header_y = y
                pagina_tabela = pagina + 1
                break
        if header_y is None:
            continue
        for y, ws in sorted(rows.items()):
            if y <= header_y:
                continue
            linha = " ".join(w[4] for w in sorted(ws, key=lambda x: x[0]))
            vals = _valores_linha(ws)
            if len(vals) >= 10:
                nome = linha.split("R$")[0].strip() or f"Plano Amil {len(planos)+1}"
                planos.append((nome[:60], vals[:10], pagina + 1, linha))
            elif len(vals) == 1 and "total" in linha.lower():
                meta.setdefault("totais_pagina", []).append(vals[0])

    if not planos:
        alertas.append(
            AlertaExtracaoCotacao(
                codigo="PDF-AMIL-001",
                mensagem="Tabela visual de prêmios não localizada — use entrada manual.",
                severidade="alerta",
            )
        )
        return [], alertas, meta

    opcoes: list[OpcaoCotacaoCandidata] = []
    for nome, valores, pagina, trecho in planos[:4]:
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
        total = valores[-1] if len(valores) > 10 else None
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
                texto=nome,
                pagina=pagina,
                trecho=trecho,
                parser_versao=PARSER_VERSAO,
                documento_hash=documento_hash,
            ),
            regime_copart=novo_campo(
                "Regime de coparticipação",
                texto="parcial",
                estado="revisar",
                parser_versao=PARSER_VERSAO,
                documento_hash=documento_hash,
            ),
            tabela=tabela,
            total_recorrente=novo_campo(
                "Total mensal",
                centavos=total,
                price_basis=PriceBasisRascunho.EXCLUI_IOF,
                pagina=pagina,
                parser_versao=PARSER_VERSAO,
                documento_hash=documento_hash,
                estado="revisar" if total else "ausente",
            ),
        )
        reconciliar_opcao(opcao)
        opcoes.append(opcao)

    for pagina in range(doc.numero_paginas):
        texto = doc.texto(pagina)
        match = re.search(r"R\$\s*([\d.,]+)", texto)
        if match and "parcela" in texto.lower():
            meta["primeira_parcela"] = valor_para_centavos(match.group(1))

    return opcoes, alertas, meta
