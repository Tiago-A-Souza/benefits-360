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

PARSER_VERSAO = "sulamerica@2.2.0"
OPERADORA = "SulAmérica"
TEMPLATE_ID = "sulamerica-pme-v2"


def _ascii_upper(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()


def identificar(doc: PdfDocumento) -> bool:
    amostra = _ascii_upper(doc.texto_todo()[:12000])
    return "SUL" in amostra and "AMERICA" in amostra


def _extrair_financeiro(texto: str) -> tuple[int | None, int | None, int | None]:
    """Extrai Prêmio / IOF / Total. Valores podem vir em linhas abaixo dos rótulos."""
    from newport_app.siscor_importer.money import valor_para_centavos

    match_total = re.search(
        r"Total de Pr[eê]mio Sa[uú]de:\s*R\$\s*([\d.,]+)",
        texto,
        re.IGNORECASE,
    )
    total = valor_para_centavos(match_total.group(1)) if match_total else None

    # Evitar casar «Total de Prêmio Saúde» como se fosse a linha de prêmio.
    match_bloco = re.search(
        r"(?<!Total de )Pr[eê]mio\s*Sa[uú]de:",
        texto,
        re.IGNORECASE,
    )
    if match_bloco:
        chunk = texto[match_bloco.start() : match_bloco.start() + 400]
        vals = extrair_valores_reais(chunk)
        if len(vals) >= 2:
            premio, iof = vals[0], vals[1]
            if total is None and len(vals) >= 3:
                total = vals[2]
            return premio, iof, total

    match_premio = re.search(
        r"(?<!Total de )Pr[eê]mio\s*Sa[uú]de:\s*R\$\s*([\d.,]+)",
        texto,
        re.IGNORECASE,
    )
    match_iof = re.search(
        r"IOF\s*\([^)]*\):\s*R\$\s*([\d.,]+)",
        texto,
        re.IGNORECASE,
    )
    premio = valor_para_centavos(match_premio.group(1)) if match_premio else None
    iof = valor_para_centavos(match_iof.group(1)) if match_iof else None
    if premio is not None or iof is not None or total is not None:
        if total is None and premio is not None and iof is not None:
            total = premio + iof
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
    paginas_com_cabecalho_sem_linha = 0
    candidatas_descartadas = 0

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
        if not secao.linhas and secao.linhas_tarifarias_detectadas > 0:
            paginas_com_cabecalho_sem_linha += 1
            candidatas_descartadas += secao.linhas_tarifarias_detectadas
            alertas.append(
                AlertaExtracaoCotacao(
                    codigo="PDF-SUL-007",
                    mensagem=(
                        f"Página {secao.pagina}: cabeçalho de faixas encontrado, mas "
                        f"{secao.linhas_tarifarias_detectadas} linha(s) tarifária(s) "
                        "candidata(s) não puderam ser montadas (nome fragmentado ou "
                        "valores incompletos)."
                    ),
                    severidade="alerta",
                    pagina=secao.pagina,
                )
            )
            continue
        if not secao.linhas:
            continue
        descartadas = max(0, secao.linhas_tarifarias_detectadas - len(secao.linhas))
        if descartadas > 0:
            candidatas_descartadas += descartadas
            alertas.append(
                AlertaExtracaoCotacao(
                    codigo="PDF-SUL-007",
                    mensagem=(
                        f"Página {secao.pagina}: {descartadas} linha(s) tarifária(s) "
                        f"detectada(s) não entraram na extração "
                        f"({len(secao.linhas)} de {secao.linhas_tarifarias_detectadas} "
                        "recuperadas)."
                    ),
                    severidade="alerta",
                    pagina=secao.pagina,
                )
            )
        secoes_encontradas.append(secao)

    if not secoes_encontradas:
        if candidatas_descartadas > 0 or paginas_com_cabecalho_sem_linha > 0:
            alertas.append(
                AlertaExtracaoCotacao(
                    codigo="PDF-SUL-001",
                    mensagem=(
                        "Nenhuma opção montada a partir da tabela tarifária — "
                        f"{candidatas_descartadas} linha(s) candidata(s) vistas e "
                        "descartadas. Revise o PDF ou use entrada manual."
                    ),
                    severidade="alerta",
                )
            )
        else:
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
    total_linhas = sum(len(s.linhas) for s in secoes_encontradas)
    aplicar_financeiro = len(secoes_encontradas) == 1 and total_linhas == 1

    for secao in secoes_encontradas:
        for linha in secao.linhas:
            regime_tipo = secao.regime_tipo if secao.regime_tipo != "ambíguo" else "sem"
            qtds = linha.quantidades or [None] * 10
            tabela = []
            for idx, centavos in enumerate(linha.valores):
                qtd = qtds[idx] if idx < len(qtds) else None
                tabela.append(
                    faixa_extraida(
                        idx,
                        valor_centavos=centavos,
                        quantidade=qtd,
                        price_basis=PriceBasisRascunho.EXCLUI_IOF,
                        pagina=linha.pagina,
                        trecho_valor=linha.trecho,
                        trecho_qtd=f"{qtd} vida" if qtd is not None else None,
                        parser_versao=PARSER_VERSAO,
                        documento_hash=documento_hash,
                    )
                )
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
                acomodacao=novo_campo(
                    "Acomodação",
                    texto=linha.acomodacao,
                    pagina=linha.pagina,
                    trecho=linha.trecho,
                    estado="confirmar" if linha.acomodacao else "ausente",
                    parser_versao=PARSER_VERSAO,
                    documento_hash=documento_hash,
                )
                if linha.acomodacao
                else None,
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
                    centavos=premio if aplicar_financeiro else None,
                    price_basis=PriceBasisRascunho.EXCLUI_IOF,
                    parser_versao=PARSER_VERSAO,
                    documento_hash=documento_hash,
                ),
                iof=novo_campo(
                    "IOF",
                    centavos=iof if aplicar_financeiro else None,
                    price_basis=PriceBasisRascunho.EXCLUI_IOF,
                    parser_versao=PARSER_VERSAO,
                    documento_hash=documento_hash,
                ),
                total_recorrente=novo_campo(
                    "Total mensal",
                    centavos=total if aplicar_financeiro else None,
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
    meta["linhas_tarifarias_detectadas"] = sum(
        s.linhas_tarifarias_detectadas for s in secoes_encontradas
    ) + candidatas_descartadas
    meta["opcoes_montadas"] = len(opcoes)
    meta["planos_por_secao"] = [
        {
            "pagina": s.pagina,
            "regime": s.regime_rotulo,
            "planos": len(s.linhas),
        }
        for s in secoes_encontradas
    ]
    return opcoes, alertas, meta
