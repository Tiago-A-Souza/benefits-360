"""Helpers compartilhados pelos parsers de operadora."""

from __future__ import annotations

import uuid
from datetime import date

from newport_app.models.cotacao_pdf import (
    EvidenciaExtracao,
    FaixaExtraida,
    ValorExtraido,
)
from newport_app.models.draft import PriceBasisRascunho


def novo_campo(
    rotulo: str,
    *,
    centavos: int | None = None,
    texto: str | None = None,
    data: date | None = None,
    inteiro: int | None = None,
    price_basis: PriceBasisRascunho | None = None,
    pagina: int | None = None,
    trecho: str | None = None,
    coordenadas: str | None = None,
    estado: str = "confirmar",
    parser_versao: str | None = None,
    documento_hash: str | None = None,
) -> ValorExtraido:
    if centavos is None and texto is None and data is None and inteiro is None:
        estado = "ausente"
    elif estado == "confirmar" and trecho and ("?" in trecho or "..." in trecho):
        estado = "revisar"
    return ValorExtraido(
        id=str(uuid.uuid4()),
        rotulo=rotulo,
        centavos=centavos,
        texto=texto,
        data=data,
        inteiro=inteiro,
        price_basis=price_basis,
        evidencia=EvidenciaExtracao(
            pagina=pagina,
            trecho=(trecho[:240] if trecho else None),
            coordenadas=coordenadas,
        ),
        estado=estado,  # type: ignore[arg-type]
        confirmado=False,
        parser_versao=parser_versao,
        documento_hash=documento_hash,
    )


def faixa_extraida(
    faixa: int,
    *,
    valor_centavos: int | None,
    quantidade: int | None,
    price_basis: PriceBasisRascunho,
    pagina: int | None,
    trecho_valor: str | None,
    trecho_qtd: str | None,
    parser_versao: str,
    documento_hash: str,
) -> FaixaExtraida:
    return FaixaExtraida(
        faixa=faixa,
        valor=novo_campo(
            f"Valor faixa {faixa}",
            centavos=valor_centavos,
            price_basis=price_basis,
            pagina=pagina,
            trecho=trecho_valor,
            parser_versao=parser_versao,
            documento_hash=documento_hash,
            estado="confirmar" if valor_centavos is not None else "ausente",
        ),
        quantidade=novo_campo(
            f"Quantidade faixa {faixa}",
            inteiro=quantidade,
            pagina=pagina,
            trecho=trecho_qtd,
            parser_versao=parser_versao,
            documento_hash=documento_hash,
            estado="confirmar" if quantidade is not None else "ausente",
        ),
    )
