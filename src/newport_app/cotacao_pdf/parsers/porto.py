"""Parser Porto Seguro — template 27 pág., tabelas dinâmicas por coordenadas."""

from __future__ import annotations

import re
import uuid

from newport_app.cotacao_pdf.coords_extract import (
    classificar_regime_plano_porto,
    extrair_quantidades_faixa_porto,
    extrair_tabelas_pagina,
    localizar_paginas_tabela_geral,
    texto_pagina_enriquecido,
)
from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.parsers.base import faixa_extraida, novo_campo
from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
from newport_app.cotacao_pdf.text_utils import (
    extrair_datas,
    extrair_percentual,
    extrair_primeiro_reais,
    extrair_valores_reais,
)
from newport_app.models.cotacao_pdf import AlertaExtracaoCotacao, OpcaoCotacaoCandidata
from newport_app.models.draft import PriceBasisRascunho

PARSER_VERSAO = "porto@2.0.1"
OPERADORA = "Porto Seguro"
TEMPLATE_ID = "porto-orcamento-v2"


def identificar(doc: PdfDocumento) -> bool:
    amostra = doc.texto_todo()[:8000].upper()
    return (
        "PORTO" in amostra
        or "BX865J" in amostra
        or bool(re.search(r"P\d{3}\s*[QE]", amostra))
    )


def _plano_resumo(doc: PdfDocumento) -> tuple[str | None, int, str]:
    """Plano selecionado no resumo — prefere página 5 (índice 4)."""
    for pagina in (4, 1, 2, 0):
        if pagina >= doc.numero_paginas:
            continue
        texto, _ = texto_pagina_enriquecido(doc, pagina)
        match = re.search(r"(P\d{3}\s*[A-Z0-9]+)", texto, re.IGNORECASE)
        if match and "R$" in texto:
            return match.group(1).upper().replace("  ", " "), pagina + 1, texto
    return None, 0, ""


def _extrair_resumo_financeiro(doc: PdfDocumento) -> tuple[int | None, int | None, int | None, dict]:
    meta: dict = {}
    pagina_resumo = 4 if doc.numero_paginas > 4 else 1
    texto, _ = texto_pagina_enriquecido(doc, pagina_resumo)
    meta["pagina_resumo"] = pagina_resumo + 1

    datas = extrair_datas(texto)
    meta["data_emissao"] = datas[0] if datas else None
    meta["validade_oficial"] = datas[1] if len(datas) > 1 else None

    match_num = re.search(r"(\d{6,8})", texto)
    if match_num:
        meta["numero_cotacao"] = match_num.group(1)

    match_vidas = re.search(r"(\d+)\s+vidas?", texto, re.IGNORECASE)
    if match_vidas:
        meta["quantidade_vidas_total"] = int(match_vidas.group(1))

    premio = None
    match_sub = re.search(r"Subtotal\s*R\$\s*([\d.,]+)", texto, re.IGNORECASE)
    if match_sub:
        premio = extrair_primeiro_reais(match_sub.group(0))
    if premio is None:
        vals = extrair_valores_reais(texto)
        premio = vals[0] if vals else None

    iof = None
    match_iof = re.search(r"IOF\s*R\$\s*([\d.,]+)", texto, re.IGNORECASE)
    if match_iof:
        iof = extrair_primeiro_reais(match_iof.group(0))

    total = None
    match_total = re.search(
        r"Valor total mensal.*?R\$\s*([\d.,]+)",
        texto,
        re.IGNORECASE | re.DOTALL,
    )
    if match_total:
        total = extrair_primeiro_reais(match_total.group(0))

    return premio, iof, total, meta


def _inferir_acomodacao_porto(nome: str) -> str | None:
    n = nome.upper()
    if re.search(r"\bQ\b", n) or n.endswith(" Q"):
        return "Apartamento"
    if re.search(r"\bE\b", n) or n.endswith(" E"):
        return "Enfermaria"
    return None


def _montar_opcao(
    linha,
    secao,
    *,
    documento_hash: str,
    qtds: dict,
    premio: int | None,
    iof: int | None,
    total: int | None,
    validade,
    pagina_resumo: int,
    associacao_confirmada: bool,
) -> OpcaoCotacaoCandidata:
    regime_tipo, copart_pct, regime_rotulo = classificar_regime_plano_porto(
        linha.plano_nome,
        secao.contexto_pagina or secao.cabecalho,
    )
    if regime_tipo == "a_confirmar":
        regime_estado = "revisar"
        copart_estado = "ausente"
    else:
        regime_estado = "confirmar"
        copart_estado = "confirmar" if copart_pct is not None else "ausente"

    acomodacao = _inferir_acomodacao_porto(linha.plano_nome)

    tabela = []
    for idx, centavos in enumerate(linha.valores):
        qtd, trecho_qtd = qtds.get(idx, (None, None))
        tabela.append(
            faixa_extraida(
                idx,
                valor_centavos=centavos,
                quantidade=qtd,
                price_basis=PriceBasisRascunho.EXCLUI_IOF,
                pagina=linha.pagina,
                trecho_valor=linha.trecho,
                trecho_qtd=trecho_qtd,
                parser_versao=PARSER_VERSAO,
                documento_hash=documento_hash,
            )
        )

    estado_plano = "revisar" if not associacao_confirmada else "confirmar"
    opcao = OpcaoCotacaoCandidata(
        id=str(uuid.uuid4()),
        operadora=novo_campo(
            "Operadora",
            texto=OPERADORA,
            pagina=pagina_resumo,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        plano_nome=novo_campo(
            "Nome do plano",
            texto=linha.plano_nome,
            pagina=linha.pagina,
            trecho=linha.trecho,
            coordenadas=linha.coordenadas,
            estado=estado_plano,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        tipo_fiscal=novo_campo(
            "Tipo fiscal",
            texto="seguradora",
            pagina=pagina_resumo,
            trecho="Porto Seguro — seguradora (extraído do documento)",
            estado="confirmar",
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        acomodacao=novo_campo(
            "Acomodação",
            texto=acomodacao,
            pagina=linha.pagina,
            trecho=linha.trecho,
            estado="confirmar" if acomodacao else "revisar",
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ) if acomodacao else None,
        regime_copart=novo_campo(
            "Regime de coparticipação",
            texto=regime_tipo,
            pagina=secao.pagina,
            trecho=secao.cabecalho or regime_rotulo,
            estado=regime_estado,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        copart_percentual=novo_campo(
            "Percentual de coparticipação",
            inteiro=copart_pct,
            pagina=secao.pagina,
            trecho=secao.cabecalho or regime_rotulo,
            estado=copart_estado,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        tabela=tabela,
        premio_saude=novo_campo(
            "Prêmio saúde",
            centavos=premio if associacao_confirmada else None,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            pagina=pagina_resumo,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        iof=novo_campo(
            "IOF",
            centavos=iof if associacao_confirmada else None,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            pagina=pagina_resumo,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        total_recorrente=novo_campo(
            "Total mensal",
            centavos=total or (premio and iof and premio + iof if associacao_confirmada else None),
            price_basis=PriceBasisRascunho.INCLUI_IOF,
            pagina=pagina_resumo,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        validade_oficial=novo_campo(
            "Validade",
            data=validade,
            pagina=pagina_resumo,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
    )
    reconciliar_opcao(opcao)
    return opcao


def parse(
    doc: PdfDocumento,
    *,
    documento_hash: str,
) -> tuple[list[OpcaoCotacaoCandidata], list[AlertaExtracaoCotacao], dict]:
    alertas: list[AlertaExtracaoCotacao] = []
    meta: dict = {"ocr_utilizado": False}
    opcoes: list[OpcaoCotacaoCandidata] = []

    codigo_resumo, pagina_resumo, _ = _plano_resumo(doc)
    premio, iof, total, meta_fin = _extrair_resumo_financeiro(doc)
    meta.update(meta_fin)
    validade = meta_fin.get("validade_oficial")

    paginas_tabela = localizar_paginas_tabela_geral(doc)
    if not paginas_tabela:
        alertas.append(
            AlertaExtracaoCotacao(
                codigo="PDF-PORTO-004",
                mensagem=(
                    'Nenhuma página com título "Tabela Geral de Prêmios" localizada — '
                    "layout não reconhecido ou ilegível."
                ),
                severidade="alerta",
            )
        )
        return [], alertas, meta

    secoes = []
    for pagina in paginas_tabela:
        _, ocr = texto_pagina_enriquecido(doc, pagina)
        if ocr:
            meta["ocr_utilizado"] = True
        secao = extrair_tabelas_pagina(doc, pagina)
        if secao is None:
            alertas.append(
                AlertaExtracaoCotacao(
                    codigo="PDF-PORTO-002",
                    mensagem=(
                        f"Tabela tarifária ilegível na página {pagina + 1} — "
                        "cabeçalho de faixas ou valores não recuperados."
                    ),
                    severidade="alerta",
                    pagina=pagina + 1,
                )
            )
            continue
        if secao.regime_tipo == "ambíguo":
            alertas.append(
                AlertaExtracaoCotacao(
                    codigo="PDF-PORTO-003",
                    mensagem=(
                        f"Regime de coparticipação ambíguo na página {secao.pagina} — "
                        "confirme pelo título da tabela ou pelo nome do plano."
                    ),
                    severidade="alerta",
                    pagina=secao.pagina,
                )
            )
        secoes.append(secao)

    if not secoes:
        return [], alertas, meta

    if not codigo_resumo:
        alertas.append(
            AlertaExtracaoCotacao(
                codigo="PDF-PORTO-001",
                mensagem="Plano selecionado não identificado no resumo financeiro (pág. 5).",
                severidade="alerta",
                pagina=meta_fin.get("pagina_resumo"),
            )
        )

    codigo_base = codigo_resumo.split()[0].upper() if codigo_resumo else None
    qtds = extrair_quantidades_faixa_porto(doc, codigo_resumo) if codigo_resumo else {}
    alguma_associacao = False

    for secao in secoes:
        for linha in secao.linhas:
            associacao_ok = True
            if codigo_base:
                associacao_ok = codigo_base in linha.plano_nome.upper()
            if codigo_resumo and associacao_ok:
                alguma_associacao = True
            opcoes.append(
                _montar_opcao(
                    linha,
                    secao,
                    documento_hash=documento_hash,
                    qtds=qtds if associacao_ok else {},
                    premio=premio,
                    iof=iof,
                    total=total,
                    validade=validade,
                    pagina_resumo=pagina_resumo or meta_fin.get("pagina_resumo", 5),
                    associacao_confirmada=associacao_ok and codigo_resumo is not None,
                )
            )

    if codigo_resumo and not alguma_associacao and opcoes:
        alertas.append(
            AlertaExtracaoCotacao(
                codigo="PDF-PORTO-005",
                mensagem=(
                    f"Plano do resumo ({codigo_resumo}) não corresponde com segurança "
                    "a nenhuma linha tarifária — confirme manualmente antes de aplicar."
                ),
                severidade="alerta",
                pagina=pagina_resumo or meta_fin.get("pagina_resumo"),
            )
        )

    for op in opcoes:
        if op.reconciliacao and op.reconciliacao.status == "divergente":
            alertas.append(
                AlertaExtracaoCotacao(
                    codigo="PDF-REC",
                    mensagem=(
                        f"Divergência entre faixas e totais em «{op.plano_nome.texto}» — "
                        "revise antes de confirmar."
                    ),
                    severidade="alerta",
                )
            )
            break

    return opcoes, alertas, meta
