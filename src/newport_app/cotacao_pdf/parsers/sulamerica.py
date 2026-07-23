"""Parser SulAmérica — extração por coordenadas (págs. 5–6, regimes separados)."""

from __future__ import annotations

import re
import unicodedata
import uuid

from newport_app.cotacao_pdf.coords_extract import (
    localizar_paginas_tabela_sulamerica,
    texto_pagina_enriquecido,
)
from newport_app.cotacao_pdf.sulamerica_table import extrair_tabelas_pagina_sulamerica
from newport_app.cotacao_pdf.tarifa_validation import aplicar_validacao_estrutural_opcao
from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.parsers.base import faixa_extraida, novo_campo
from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
from newport_app.cotacao_pdf.text_utils import extrair_datas, extrair_valores_reais
from newport_app.models.cotacao_pdf import AlertaExtracaoCotacao, OpcaoCotacaoCandidata
from newport_app.models.draft import PriceBasisRascunho

PARSER_VERSAO = "sulamerica@2.1.0"
OPERADORA = "SulAmérica"
TEMPLATE_ID = "sulamerica-pme-v2"


def _ascii_upper(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()


def identificar(doc: PdfDocumento) -> bool:
    amostra = _ascii_upper(doc.texto_todo()[:12000])
    return "SUL" in amostra and "AMERICA" in amostra


def _extrair_financeiro(texto: str) -> tuple[int | None, int | None, int | None]:
    match_total = re.search(
        r"Total de Pr[eê]mio Sa[uú]de:\s*R\$\s*([\d.,]+)",
        texto,
        re.IGNORECASE,
    )
    total = None
    if match_total:
        from newport_app.siscor_importer.money import valor_para_centavos

        total = valor_para_centavos(match_total.group(1))

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


def _paginas_tabela_sulamerica(doc: PdfDocumento) -> list[int]:
    return localizar_paginas_tabela_sulamerica(doc)


def parse(
    doc: PdfDocumento,
    *,
    documento_hash: str,
) -> tuple[list[OpcaoCotacaoCandidata], list[AlertaExtracaoCotacao], dict]:
    alertas: list[AlertaExtracaoCotacao] = []
    meta: dict = {"ocr_utilizado": False}
    opcoes: list[OpcaoCotacaoCandidata] = []

    paginas_alvo = _paginas_tabela_sulamerica(doc)
    secoes_encontradas = []

    for pagina in paginas_alvo:
        _, ocr = texto_pagina_enriquecido(doc, pagina)
        if ocr:
            meta["ocr_utilizado"] = True
        secao = extrair_tabelas_pagina_sulamerica(doc, pagina)
        if secao is None:
            continue
        if secao.regime_tipo == "ambíguo":
            alertas.append(
                AlertaExtracaoCotacao(
                    codigo="PDF-SUL-003",
                    mensagem=(
                        f"Regime de coparticipação ambíguo na página {secao.pagina} — "
                        "confirme pelo cabeçalho da tabela."
                    ),
                    severidade="alerta",
                    pagina=secao.pagina,
                )
            )
            continue
        secoes_encontradas.append(secao)

    if not secoes_encontradas:
        alertas.append(
            AlertaExtracaoCotacao(
                codigo="PDF-SUL-001",
                mensagem=(
                    "Nenhuma tabela tarifária localizada (esperado nas págs. 5–6 "
                    "com cabeçalho de faixas etárias)."
                ),
                severidade="alerta",
            )
        )
        return [], alertas, meta

    texto_todo = doc.texto_todo()
    validade = None
    match_val = re.search(r"[Vv]alidade[^:]*:\s*(\d{2}/\d{2}/\d{4})", texto_todo)
    if match_val:
        datas = extrair_datas(match_val.group(0))
        validade = datas[0] if datas else None

    premio, iof, total = _extrair_financeiro(texto_todo)

    for secao in secoes_encontradas:
        for linha in secao.linhas:
            regime_tipo = secao.regime_tipo if secao.regime_tipo != "ambíguo" else "sem"
            tabela = [
                faixa_extraida(
                    idx,
                    valor_centavos=centavos,
                    quantidade=None,
                    price_basis=PriceBasisRascunho.EXCLUI_IOF,
                    pagina=linha.pagina,
                    trecho_valor=linha.trecho,
                    trecho_qtd=None,
                    parser_versao=PARSER_VERSAO,
                    documento_hash=documento_hash,
                )
                for idx, centavos in enumerate(linha.valores)
            ]
            rotulo_regime = secao.regime_rotulo
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
                    texto=linha.plano_nome,
                    pagina=linha.pagina,
                    trecho=linha.trecho,
                    coordenadas=linha.coordenadas,
                    parser_versao=PARSER_VERSAO,
                    documento_hash=documento_hash,
                ),
                regime_copart=novo_campo(
                    "Regime de coparticipação",
                    texto=regime_tipo,
                    pagina=secao.pagina,
                    trecho=secao.cabecalho,
                    estado="revisar",
                    parser_versao=PARSER_VERSAO,
                    documento_hash=documento_hash,
                ),
                copart_percentual=novo_campo(
                    "Percentual de coparticipação",
                    inteiro=secao.copart_percentual,
                    pagina=secao.pagina,
                    trecho=secao.cabecalho,
                    estado="confirmar" if secao.copart_percentual else "ausente",
                    parser_versao=PARSER_VERSAO,
                    documento_hash=documento_hash,
                ),
                tabela=tabela,
                premio_saude=novo_campo(
                    "Prêmio saúde",
                    centavos=premio if len(secoes_encontradas) == 1 and len(secao.linhas) == 1 else None,
                    price_basis=PriceBasisRascunho.EXCLUI_IOF,
                    parser_versao=PARSER_VERSAO,
                    documento_hash=documento_hash,
                ),
                iof=novo_campo(
                    "IOF",
                    centavos=iof if len(secoes_encontradas) == 1 and len(secao.linhas) == 1 else None,
                    price_basis=PriceBasisRascunho.EXCLUI_IOF,
                    parser_versao=PARSER_VERSAO,
                    documento_hash=documento_hash,
                ),
                total_recorrente=novo_campo(
                    "Total mensal",
                    centavos=total if len(secoes_encontradas) == 1 and len(secao.linhas) == 1 else None,
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
            alertas.extend(aplicar_validacao_estrutural_opcao(opcao))
            reconciliar_opcao(opcao)
            opcoes.append(opcao)

    meta["validade_oficial"] = validade
    meta["planos_por_secao"] = [
        {
            "pagina": s.pagina,
            "regime": s.regime_rotulo,
            "planos": len(s.linhas),
        }
        for s in secoes_encontradas
    ]
    return opcoes, alertas, meta
