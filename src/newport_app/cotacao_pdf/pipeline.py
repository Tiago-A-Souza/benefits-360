"""Pipeline principal de extração de cotações PDF."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.parsers import amil, bradesco, omint, porto, sulamerica
from newport_app.cotacao_pdf.parsers.base import novo_campo
from newport_app.models.cotacao_pdf import (
    AlertaExtracaoCotacao,
    DocumentoCotacaoPDF,
    ExtracaoCotacaoCandidata,
    OpcaoCotacaoCandidata,
    ValorExtraido,
)

_PARSERS = [
    (porto.identificar, porto.parse, porto.TEMPLATE_ID, porto.PARSER_VERSAO, porto.OPERADORA),
    (sulamerica.identificar, sulamerica.parse, sulamerica.TEMPLATE_ID, sulamerica.PARSER_VERSAO, sulamerica.OPERADORA),
    (omint.identificar, omint.parse, omint.TEMPLATE_ID, omint.PARSER_VERSAO, omint.OPERADORA),
    (amil.identificar, amil.parse, amil.TEMPLATE_ID, amil.PARSER_VERSAO, amil.OPERADORA),
    (bradesco.identificar, bradesco.parse, bradesco.TEMPLATE_ID, bradesco.PARSER_VERSAO, bradesco.OPERADORA),
]


def _hash_pdf(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def parse_cotacao_pdf(
    conteudo: bytes,
    *,
    estudo_id: str,
    documento_id: str,
    nome_arquivo: str,
    versao: int = 1,
    criado_por: str = "analista-local",
    versoes_anteriores: list[int] | None = None,
) -> ExtracaoCotacaoCandidata:
    doc_hash = _hash_pdf(conteudo)
    agora = datetime.now(timezone.utc)
    documento = DocumentoCotacaoPDF(
        id=documento_id,
        nome_arquivo=nome_arquivo,
        hash_sha256=doc_hash,
        numero_paginas=0,
    )

    if not conteudo.startswith(b"%PDF"):
        return ExtracaoCotacaoCandidata(
            id=str(uuid.uuid4()),
            estudo_id=estudo_id,
            versao=versao,
            documento=documento,
            estado="erro",
            alertas=[
                AlertaExtracaoCotacao(
                    codigo="PDF-F01",
                    mensagem="O arquivo não parece ser um PDF válido.",
                    severidade="bloqueio",
                )
            ],
            criado_em=agora,
            criado_por=criado_por,
            versoes_anteriores=versoes_anteriores or [],
        )

    try:
        with PdfDocumento.abrir(conteudo) as doc:
            documento.numero_paginas = doc.numero_paginas
            for identificar, parse_fn, template_id, parser_versao, operadora in _PARSERS:
                if not identificar(doc):
                    continue
                opcoes, alertas, meta = parse_fn(doc, documento_hash=doc_hash)
                documento.operadora_detectada = operadora
                documento.template_id = template_id
                documento.parser_versao = parser_versao
                estado = "extraido" if opcoes else "ocr_parcial"
                if template_id.startswith("omint") and (
                    not opcoes or meta.get("ocr_utilizado") is False
                ):
                    estado = "ocr_pendente"
                extracao = ExtracaoCotacaoCandidata(
                    id=str(uuid.uuid4()),
                    estudo_id=estudo_id,
                    versao=versao,
                    documento=documento,
                    estado=estado,  # type: ignore[arg-type]
                    opcoes=opcoes,
                    numero_cotacao=(
                        novo_campo(
                            "Número da cotação",
                            texto=str(meta["numero_cotacao"]),
                            parser_versao=parser_versao,
                            documento_hash=doc_hash,
                        )
                        if meta.get("numero_cotacao")
                        else None
                    ),
                    data_emissao=(
                        novo_campo(
                            "Data de emissão",
                            data=meta["data_emissao"],
                            parser_versao=parser_versao,
                            documento_hash=doc_hash,
                        )
                        if meta.get("data_emissao")
                        else None
                    ),
                    validade_oficial=(
                        novo_campo(
                            "Validade",
                            data=meta["validade_oficial"],
                            parser_versao=parser_versao,
                            documento_hash=doc_hash,
                        )
                        if meta.get("validade_oficial")
                        else None
                    ),
                    quantidade_vidas_total=(
                        novo_campo(
                            "Quantidade de vidas",
                            inteiro=meta["quantidade_vidas_total"],
                            parser_versao=parser_versao,
                            documento_hash=doc_hash,
                        )
                        if meta.get("quantidade_vidas_total") is not None
                        else None
                    ),
                    alertas=alertas,
                    criado_em=agora,
                    criado_por=criado_por,
                    versoes_anteriores=versoes_anteriores or [],
                )
                return extracao
    except Exception:
        return ExtracaoCotacaoCandidata(
            id=str(uuid.uuid4()),
            estudo_id=estudo_id,
            versao=versao,
            documento=documento,
            estado="erro",
            alertas=[
                AlertaExtracaoCotacao(
                    codigo="PDF-F03",
                    mensagem="Não foi possível ler o PDF.",
                    severidade="bloqueio",
                )
            ],
            criado_em=agora,
            criado_por=criado_por,
            versoes_anteriores=versoes_anteriores or [],
        )

    return ExtracaoCotacaoCandidata(
        id=str(uuid.uuid4()),
        estudo_id=estudo_id,
        versao=versao,
        documento=documento,
        estado="nao_reconhecido",
        alertas=[
            AlertaExtracaoCotacao(
                codigo="PDF-F02",
                mensagem="Documento não reconhecido — use entrada manual.",
                severidade="info",
            )
        ],
        criado_em=agora,
        criado_por=criado_por,
        versoes_anteriores=versoes_anteriores or [],
    )
