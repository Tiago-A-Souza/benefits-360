"""Pipeline principal de extração de cotações PDF — identificação de família antes da extração."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from newport_app.cotacao_pdf.conferencia import normalizar_extracao
from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.parsers.base import novo_campo
from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
from newport_app.cotacao_pdf.template_families import identificar_familia, operadora_candidata
from newport_app.models.cotacao_pdf import (
    AlertaExtracaoCotacao,
    DocumentoCotacaoPDF,
    ExtracaoCotacaoCandidata,
)


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
            familia = identificar_familia(doc)

            if familia is None or familia.extrator is None:
                operadora = operadora_candidata(doc)
                if operadora:
                    msg = (
                        f"Operadora «{operadora}» detectada, mas família de template "
                        "não reconhecida — aguarda revisão manual."
                    )
                    codigo = "PDF-TPL-001"
                else:
                    msg = "Documento não reconhecido — use entrada manual."
                    codigo = "PDF-F02"
                return ExtracaoCotacaoCandidata(
                    id=str(uuid.uuid4()),
                    estudo_id=estudo_id,
                    versao=versao,
                    documento=documento,
                    estado="nao_reconhecido",
                    alertas=[
                        AlertaExtracaoCotacao(
                            codigo=codigo,
                            mensagem=msg,
                            severidade="info" if codigo == "PDF-F02" else "alerta",
                        )
                    ],
                    criado_em=agora,
                    criado_por=criado_por,
                    versoes_anteriores=versoes_anteriores or [],
                )

            opcoes, alertas, meta = familia.extrator(doc, documento_hash=doc_hash)
            for op in opcoes:
                reconciliar_opcao(op)

            documento.operadora_detectada = familia.operadora
            documento.template_id = familia.id
            documento.parser_versao = familia.parser_versao

            estado = "extraido" if opcoes else "ocr_parcial"
            if familia.id.startswith("amil-cotacao-visual") and not opcoes:
                estado = "ocr_pendente"
            if familia.id == "omint-ocr-v1" and not meta.get("ocr_utilizado"):
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
                        parser_versao=familia.parser_versao,
                        documento_hash=doc_hash,
                    )
                    if meta.get("numero_cotacao")
                    else None
                ),
                data_emissao=(
                    novo_campo(
                        "Data de emissão",
                        data=meta["data_emissao"],
                        parser_versao=familia.parser_versao,
                        documento_hash=doc_hash,
                    )
                    if meta.get("data_emissao")
                    else None
                ),
                validade_oficial=(
                    novo_campo(
                        "Validade",
                        data=meta["validade_oficial"],
                        parser_versao=familia.parser_versao,
                        documento_hash=doc_hash,
                    )
                    if meta.get("validade_oficial")
                    else None
                ),
                quantidade_vidas_total=(
                    novo_campo(
                        "Quantidade de vidas",
                        inteiro=meta["quantidade_vidas_total"],
                        parser_versao=familia.parser_versao,
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
            return normalizar_extracao(extracao)
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
