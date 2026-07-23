"""Parser Porto Seguro — template orçamento saúde."""

from __future__ import annotations

import re
import uuid

from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.faixas import faixa_de_rotulo
from newport_app.cotacao_pdf.parsers.base import faixa_extraida, novo_campo
from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
from newport_app.cotacao_pdf.text_utils import (
    extrair_datas,
    extrair_decimais,
    extrair_percentual,
    extrair_primeiro_reais,
    extrair_valores_reais,
    linha_contem_plano_porto,
)
from newport_app.models.cotacao_pdf import AlertaExtracaoCotacao, OpcaoCotacaoCandidata
from newport_app.models.draft import PriceBasisRascunho

PARSER_VERSAO = "porto@1.0.0"
OPERADORA = "Porto Seguro"
TEMPLATE_ID = "porto-orcamento-v1"


def identificar(doc: PdfDocumento) -> bool:
    amostra = doc.texto_todo()[:8000].upper()
    return (
        "PORTO" in amostra
        or "BX865J" in amostra
        or bool(re.search(r"P\d{3}\s*[QE]", amostra))
    )


def _plano_selecionado(doc: PdfDocumento) -> str | None:
    for pagina in range(min(3, doc.numero_paginas)):
        texto = doc.texto(pagina)
        match = re.search(r"(P\d{3}\s*[QE])", texto, re.IGNORECASE)
        if match and "R$" in texto:
            return match.group(1).upper().replace("  ", " ")
    return None


def _pagina_tabela_copart(texto: str, com_copart: bool) -> bool:
    t = texto.lower()
    sem = "sem copart" in t or "sem coparticip" in t
    com = ("coparticip" in t or " com copart" in t or "30%" in t) and not sem
    return com if com_copart else sem


def _coletar_valores_faixa(linhas: list[str], idx_inicio: int) -> tuple[list[int], str | None]:
    collected: list[int] = []
    trechos = [linhas[idx_inicio]]
    for j in range(idx_inicio + 1, min(idx_inicio + 14, len(linhas))):
        linha = linhas[j]
        if j > idx_inicio + 1 and re.search(r"P\d{3}\s*[QE]", linha, re.IGNORECASE):
            break
        nums = extrair_decimais(linha)
        if nums:
            collected.extend(nums)
            trechos.append(linha)
        if len(collected) >= 10:
            return collected[:10], " | ".join(trechos)
    return [], None


def _tabela_plano(doc: PdfDocumento, codigo: str, com_copart: bool) -> tuple[list[int], str | None]:
    for pagina in range(doc.numero_paginas):
        texto = doc.texto(pagina)
        if not _pagina_tabela_copart(texto, com_copart):
            continue
        linhas = doc.linhas(pagina)
        for idx, linha in enumerate(linhas):
            if not linha_contem_plano_porto(linha, codigo):
                continue
            nums = extrair_decimais(linha)
            if len(nums) >= 10:
                return nums[:10], linha
            nums, trecho = _coletar_valores_faixa(linhas, idx)
            if nums:
                return nums, trecho
    return [], None


def _quantidades_faixa(doc: PdfDocumento, codigo: str) -> dict[int, tuple[int, str]]:
    resultado: dict[int, tuple[int, str]] = {}
    for pagina in range(doc.numero_paginas - 1, -1, -1):
        if "faixa et" not in doc.texto(pagina).lower():
            continue
        if codigo.split()[0] not in doc.texto(pagina):
            continue
        linhas = doc.linhas(pagina)
        for idx, linha in enumerate(linhas):
            faixa = faixa_de_rotulo(linha)
            if faixa is None:
                continue
            qtd = None
            trecho = linha
            if idx + 1 < len(linhas) and re.fullmatch(r"\d+", linhas[idx + 1]):
                qtd = int(linhas[idx + 1])
                trecho = f"{linha} | {linhas[idx + 1]}"
            else:
                nums = re.findall(r"\b(\d+)\b", linha)
                if nums and int(nums[-1]) <= 99:
                    qtd = int(nums[-1])
            if qtd is not None and qtd > 0:
                resultado[faixa] = (qtd, trecho)
        if resultado:
            break
    return resultado


def parse(
    doc: PdfDocumento,
    *,
    documento_hash: str,
) -> tuple[list[OpcaoCotacaoCandidata], list[AlertaExtracaoCotacao], dict]:
    alertas: list[AlertaExtracaoCotacao] = []
    meta: dict = {}
    codigo = _plano_selecionado(doc)
    if not codigo:
        alertas.append(
            AlertaExtracaoCotacao(
                codigo="PDF-PORTO-001",
                mensagem="Plano selecionado não identificado no resumo.",
                severidade="alerta",
                pagina=2,
            )
        )
        return [], alertas, meta

    pagina_resumo = 1
    texto_resumo = doc.texto(pagina_resumo)
    datas = extrair_datas(texto_resumo)
    emissao = datas[0] if datas else None
    validade = datas[1] if len(datas) > 1 else None
    numero = None
    match_num = re.search(r"(\d{6,8})", texto_resumo)
    if match_num:
        numero = match_num.group(1)

    vidas = None
    match_vidas = re.search(r"(\d+)\s+vidas?", texto_resumo, re.IGNORECASE)
    if match_vidas:
        vidas = int(match_vidas.group(1))

    copart_pct = extrair_percentual(texto_resumo)
    com_copart = copart_pct is not None and copart_pct > 0
    premio = None
    match_sub = re.search(r"Subtotal\s*R\$\s*([\d.,]+)", texto_resumo, re.IGNORECASE)
    if match_sub:
        premio = extrair_primeiro_reais(match_sub.group(0))
    if premio is None:
        valores_resumo = extrair_valores_reais(texto_resumo)
        premio = valores_resumo[0] if valores_resumo else None
    iof = None
    match_iof = re.search(r"IOF\s*R\$\s*([\d.,]+)", texto_resumo, re.IGNORECASE)
    if match_iof:
        iof = extrair_primeiro_reais(match_iof.group(0))
    total = None
    match_total = re.search(
        r"Valor total mensal.*?R\$\s*([\d.,]+)",
        texto_resumo,
        re.IGNORECASE | re.DOTALL,
    )
    if match_total:
        total = extrair_primeiro_reais(match_total.group(0))

    valores_faixa, trecho_tabela = _tabela_plano(doc, codigo, com_copart)
    if not valores_faixa:
        valores_faixa, trecho_tabela = _tabela_plano(doc, codigo, not com_copart)
    qtds = _quantidades_faixa(doc, codigo)

    tabela = []
    for idx, centavos in enumerate(valores_faixa):
        qtd, trecho_qtd = qtds.get(idx, (None, None))
        tabela.append(
            faixa_extraida(
                idx,
                valor_centavos=centavos,
                quantidade=qtd,
                price_basis=PriceBasisRascunho.EXCLUI_IOF,
                pagina=15 if com_copart else 14,
                trecho_valor=trecho_tabela,
                trecho_qtd=trecho_qtd,
                parser_versao=PARSER_VERSAO,
                documento_hash=documento_hash,
            )
        )

    opcao = OpcaoCotacaoCandidata(
        id=str(uuid.uuid4()),
        operadora=novo_campo(
            "Operadora",
            texto=OPERADORA,
            pagina=1,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        plano_nome=novo_campo(
            "Nome do plano",
            texto=codigo,
            pagina=2,
            trecho=texto_resumo.splitlines()[0] if texto_resumo else None,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        regime_copart=novo_campo(
            "Regime de coparticipação",
            texto="parcial" if com_copart else "sem",
            pagina=2,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
            estado="revisar",
        ),
        copart_percentual=novo_campo(
            "Percentual de coparticipação",
            inteiro=int(copart_pct) if copart_pct is not None else None,
            pagina=2,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
            estado="confirmar" if copart_pct else "ausente",
        ),
        tabela=tabela,
        premio_saude=novo_campo(
            "Prêmio saúde",
            centavos=premio,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            pagina=2,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        iof=novo_campo(
            "IOF",
            centavos=iof,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            pagina=2,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        total_recorrente=novo_campo(
            "Total mensal",
            centavos=total or (premio and iof and premio + iof),
            price_basis=PriceBasisRascunho.INCLUI_IOF,
            pagina=2,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        validade_oficial=novo_campo(
            "Validade",
            data=validade,
            pagina=2,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
    )
    reconciliar_opcao(opcao)
    if opcao.reconciliacao and not opcao.reconciliacao.ok:
        alertas.append(
            AlertaExtracaoCotacao(
                codigo="PDF-REC",
                mensagem="Há divergências entre faixas e totais — revise antes de confirmar.",
                severidade="alerta",
            )
        )

    meta.update(
        {
            "numero_cotacao": numero,
            "data_emissao": emissao,
            "validade_oficial": validade,
            "quantidade_vidas_total": vidas,
        }
    )
    return [opcao], alertas, meta
