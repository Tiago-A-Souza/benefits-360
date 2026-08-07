"""Parser Omint — OCR quando necessário."""

from __future__ import annotations

import uuid

from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.ocr import tentar_ocr_pagina
from newport_app.cotacao_pdf.parsers.base import novo_campo
from newport_app.models.cotacao_pdf import AlertaExtracaoCotacao, OpcaoCotacaoCandidata

PARSER_VERSAO = "omint@1.0.0"
OPERADORA = "Omint"
TEMPLATE_ID = "omint-ocr-v1"


def identificar(doc: PdfDocumento) -> bool:
    amostra = doc.texto_todo().upper()
    return "OMINT" in amostra


def _opcao_esqueleto(documento_hash: str) -> OpcaoCotacaoCandidata:
    return OpcaoCotacaoCandidata(
        id=str(uuid.uuid4()),
        operadora=novo_campo(
            "Operadora",
            texto=OPERADORA,
            estado="confirmar",
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        plano_nome=novo_campo(
            "Nome do plano",
            texto="Omint — revisão manual",
            estado="revisar",
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
    )


def parse(
    doc: PdfDocumento,
    *,
    documento_hash: str,
) -> tuple[list[OpcaoCotacaoCandidata], list[AlertaExtracaoCotacao], dict]:
    alertas: list[AlertaExtracaoCotacao] = []
    meta: dict = {"ocr_utilizado": False}

    chars_uteis = sum(len(t.strip()) for t in doc.paginas_texto)
    if chars_uteis < 100:
        for pagina in range(doc.numero_paginas):
            ocr_texto, ok = tentar_ocr_pagina(doc, pagina)
            if ok and ocr_texto:
                doc.paginas_texto[pagina] = ocr_texto
                meta["ocr_utilizado"] = True

    if not meta["ocr_utilizado"]:
        alertas.append(
            AlertaExtracaoCotacao(
                codigo="PDF-OMINT-OCR",
                mensagem=(
                    "Documento Omint requer OCR (Tesseract não disponível ou sem texto). "
                    "Campos financeiros devem ser informados manualmente após revisão."
                ),
                severidade="alerta",
            )
        )
        return [_opcao_esqueleto(documento_hash)], alertas, meta

    alertas.append(
        AlertaExtracaoCotacao(
            codigo="PDF-OMINT-PARCIAL",
            mensagem="Extração Omint parcial via OCR — confirme todos os valores.",
            severidade="alerta",
        )
    )
    return [_opcao_esqueleto(documento_hash)], alertas, meta
