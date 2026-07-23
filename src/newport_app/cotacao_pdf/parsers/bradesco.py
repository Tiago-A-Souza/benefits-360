"""Parser Bradesco Saúde — layout denso com múltiplos planos."""

from __future__ import annotations

import re
import uuid

from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.faixas import faixa_de_rotulo
from newport_app.cotacao_pdf.parsers.base import faixa_extraida, novo_campo
from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
from newport_app.cotacao_pdf.text_utils import extrair_datas, extrair_valores_reais, valor_de_celula
from newport_app.models.cotacao_pdf import AlertaExtracaoCotacao, OpcaoCotacaoCandidata
from newport_app.models.draft import PriceBasisRascunho

PARSER_VERSAO = "bradesco@1.0.0"
OPERADORA = "Bradesco Saúde"
TEMPLATE_ID = "bradesco-cp-v1"


def identificar(doc: PdfDocumento) -> bool:
    amostra = doc.texto_todo()[:6000].upper()
    return "BRADESCO" in amostra or "TN3P" in amostra


def _parse_tabela(tabela: list[list], indice_plano: int) -> tuple[str, list[tuple], int | None]:
    plano_nome = f"Opção {indice_plano + 1}"
    tabela_faixas: list[tuple] = []
    subtotal = None
    if not tabela or len(tabela) < 4:
        return plano_nome, tabela_faixas, subtotal

    header = tabela[1] if len(tabela) > 1 else []
    if header:
        partes = [str(c).replace("\n", " ").strip() for c in header[:2] if c]
        if partes:
            plano_nome = " ".join(partes)[:80]

    for row in tabela[3:]:
        if not row or not row[0]:
            continue
        rotulo = str(row[0]).replace("\n", " ")
        faixa = faixa_de_rotulo(rotulo)
        if faixa is None:
            if "total" in rotulo.lower() or "subtotal" in rotulo.lower():
                vals = [valor_de_celula(str(c)) for c in row if c]
                vals = [v for v in vals if v]
                if vals:
                    subtotal = vals[-1]
            continue
        premio_txt = row[2] if len(row) > 2 else None
        qtd_txt = row[7] if len(row) > 7 else None
        premio = valor_de_celula(str(premio_txt) if premio_txt else None)
        qtd = None
        if qtd_txt is not None and str(qtd_txt).strip().isdigit():
            qtd = int(str(qtd_txt).strip())
        tabela_faixas.append((faixa, premio, qtd, rotulo))

    return plano_nome, tabela_faixas, subtotal


def parse(
    doc: PdfDocumento,
    *,
    documento_hash: str,
) -> tuple[list[OpcaoCotacaoCandidata], list[AlertaExtracaoCotacao], dict]:
    alertas: list[AlertaExtracaoCotacao] = []
    meta: dict = {}
    tabelas = doc.tabelas_pdfplumber(0)
    if not tabelas:
        alertas.append(
            AlertaExtracaoCotacao(
                codigo="PDF-BRA-001",
                mensagem="Tabelas de planos não encontradas na primeira página.",
                severidade="alerta",
            )
        )
        return [], alertas, meta

    opcoes: list[OpcaoCotacaoCandidata] = []
    for idx, tabela in enumerate(tabelas):
        plano_nome, linhas, subtotal = _parse_tabela(tabela, idx)
        tabela_faixas = [
            faixa_extraida(
                faixa,
                valor_centavos=centavos,
                quantidade=qtd,
                price_basis=PriceBasisRascunho.EXCLUI_IOF,
                pagina=1,
                trecho_valor=rotulo,
                trecho_qtd=str(qtd) if qtd is not None else None,
                parser_versao=PARSER_VERSAO,
                documento_hash=documento_hash,
            )
            for faixa, centavos, qtd, rotulo in linhas
            if centavos is not None
        ]
        if not tabela_faixas:
            continue
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
                pagina=1,
                parser_versao=PARSER_VERSAO,
                documento_hash=documento_hash,
            ),
            regime_copart=novo_campo(
                "Regime de coparticipação",
                texto="parcial",
                estado="revisar",
                pagina=1,
                parser_versao=PARSER_VERSAO,
                documento_hash=documento_hash,
            ),
            copart_percentual=novo_campo(
                "Percentual de coparticipação",
                inteiro=30,
                estado="revisar",
                pagina=1,
                parser_versao=PARSER_VERSAO,
                documento_hash=documento_hash,
            ),
            tabela=tabela_faixas,
            subtotal_impresso=novo_campo(
                "Subtotal do plano",
                centavos=subtotal,
                price_basis=PriceBasisRascunho.EXCLUI_IOF,
                pagina=1,
                parser_versao=PARSER_VERSAO,
                documento_hash=documento_hash,
            ),
        )
        reconciliar_opcao(opcao)
        opcoes.append(opcao)

    if doc.numero_paginas >= 2:
        texto_p2 = doc.texto(1)
        datas = extrair_datas(texto_p2)
        if datas:
            meta["validade_oficial"] = datas[0]
        iof = None
        premio = None
        total = None
        primeira = None
        match_iof = re.search(r"I\.?O\.?F\.?.*?R\$\s*([\d.,]+)", texto_p2, re.I)
        if match_iof:
            from newport_app.siscor_importer.money import valor_para_centavos

            iof = valor_para_centavos(match_iof.group(1))
        match_premio = re.search(r"Pr[eê]mio\s*Sa[uú]de\s*R\$\s*([\d.,]+)", texto_p2, re.I)
        if match_premio:
            from newport_app.siscor_importer.money import valor_para_centavos

            premio = valor_para_centavos(match_premio.group(1))
        match_parcela = re.search(r"Demais Parcelas\s*R\$\s*([\d.,]+)", texto_p2, re.I)
        if match_parcela:
            from newport_app.siscor_importer.money import valor_para_centavos

            total = valor_para_centavos(match_parcela.group(1))
        match_primeira = re.search(r"Total 1[ªa]\s*Parcela\s*R\$\s*([\d.,]+)", texto_p2, re.I)
        if match_primeira:
            from newport_app.siscor_importer.money import valor_para_centavos

            primeira = valor_para_centavos(match_primeira.group(1))
        if total is None:
            vals = extrair_valores_reais(texto_p2)
            if vals:
                total = vals[0]
        for op in opcoes:
            if premio and op.premio_saude is None:
                op.premio_saude = novo_campo(
                    "Prêmio saúde",
                    centavos=premio,
                    price_basis=PriceBasisRascunho.EXCLUI_IOF,
                    pagina=2,
                    parser_versao=PARSER_VERSAO,
                    documento_hash=documento_hash,
                )
            if iof and op.iof is None:
                op.iof = novo_campo(
                    "IOF",
                    centavos=iof,
                    price_basis=PriceBasisRascunho.EXCLUI_IOF,
                    pagina=2,
                    parser_versao=PARSER_VERSAO,
                    documento_hash=documento_hash,
                )
            if total and op.total_recorrente is None:
                op.total_recorrente = novo_campo(
                    "Total mensal",
                    centavos=total,
                    price_basis=PriceBasisRascunho.INCLUI_IOF,
                    pagina=2,
                    parser_versao=PARSER_VERSAO,
                    documento_hash=documento_hash,
                )
            if primeira and op.total_primeira_parcela is None:
                op.total_primeira_parcela = novo_campo(
                    "Primeira parcela",
                    centavos=primeira,
                    price_basis=PriceBasisRascunho.INCLUI_IOF,
                    pagina=2,
                    parser_versao=PARSER_VERSAO,
                    documento_hash=documento_hash,
                )
            reconciliar_opcao(op)

    return opcoes, alertas, meta
