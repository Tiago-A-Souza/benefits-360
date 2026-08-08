"""Parser Porto Seguro — template 27 pág., tabelas dinâmicas por coordenadas."""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import date, datetime

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
from newport_app.cotacao_pdf.text_utils import extrair_datas, extrair_valores_reais
from newport_app.models.cotacao_pdf import AlertaExtracaoCotacao, OpcaoCotacaoCandidata
from newport_app.models.draft import PriceBasisRascunho
from newport_app.siscor_importer.money import valor_para_centavos

PARSER_VERSAO = "porto@2.1.0"
OPERADORA = "Porto Seguro"
TEMPLATE_ID = "porto-orcamento-v2"

# Código completo do resumo (inclui COPAR / COPAR N). Só espaços horizontais —
# «\s» atravessaria a quebra de linha e engoliria o «3» de «3 vidas».
_RE_PLANO_RESUMO = re.compile(
    r"(P\d{3}[ \t]*[EQ](?:[ \t]+COPAR(?:[ \t]+\d{1,2})?)?)",
    re.IGNORECASE,
)
_RE_VALIDADE_ROTULO = re.compile(
    r"Validade\s*:\s*(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
_RE_VALIDADE_ESTUDO = re.compile(
    r"[Nn]umero e validade do estudo\s+(\d{5,10})\s*[-–]\s*(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
_RE_NUMERO_DATA = re.compile(
    r"(\d{5,10})\s*[-–]\s*(\d{2}/\d{2}/\d{4})",
)
_LOCAIS_VALIDADE = (
    "capa («Numero e validade do estudo / NNNNNN - DD/MM/AAAA»)",
    "cabeçalho («Validade: DD/MM/AAAA»)",
    "resumo financeiro",
)


def identificar(doc: PdfDocumento) -> bool:
    amostra = doc.texto_todo()[:8000].upper()
    return (
        "PORTO" in amostra
        or "BX865J" in amostra
        or bool(re.search(r"P\d{3}\s*[QE]", amostra))
    )


def _ascii_upper(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto)
        .encode("ascii", "ignore")
        .decode()
        .upper()
    )


def normalizar_nome_plano_porto(nome: str) -> str:
    n = _ascii_upper(nome)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def nomes_plano_equivalentes(resumo: str, tabela: str) -> bool:
    """Compara nomes do resumo e da tabela ignorando caixa/acentos/espaços."""
    a = normalizar_nome_plano_porto(resumo)
    b = normalizar_nome_plano_porto(tabela)
    if not a or not b:
        return False
    return a == b


def _parse_data_br(texto: str) -> date | None:
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError:
        return None


def _extrair_validade_porto(doc: PdfDocumento) -> tuple[date | None, str | None, int | None]:
    """Procura validade na capa, cabeçalho e resumo — nesta ordem."""
    paginas = min(doc.numero_paginas, 8)
    # 1) Rótulo explícito «Validade: DD/MM/AAAA»
    for pagina in range(paginas):
        texto, _ = texto_pagina_enriquecido(doc, pagina)
        m = _RE_VALIDADE_ROTULO.search(texto)
        if m:
            d = _parse_data_br(m.group(1))
            if d:
                return d, m.group(0), pagina + 1
    # 2) Capa «Numero e validade do estudo / NNNNN - DD/MM/AAAA»
    for pagina in range(min(3, paginas)):
        texto, _ = texto_pagina_enriquecido(doc, pagina)
        m = _RE_VALIDADE_ESTUDO.search(texto)
        if m:
            d = _parse_data_br(m.group(2))
            if d:
                return d, m.group(0).strip(), pagina + 1
        if re.search(r"validade do estudo", texto, re.IGNORECASE):
            m2 = _RE_NUMERO_DATA.search(texto)
            if m2:
                d = _parse_data_br(m2.group(2))
                if d:
                    return d, m2.group(0), pagina + 1
    # 3) Fallback: datas no bloco de resumo (Realizado + Validade)
    for pagina in range(paginas):
        texto, _ = texto_pagina_enriquecido(doc, pagina)
        if "Validade" not in texto and "validade" not in texto:
            continue
        datas = extrair_datas(texto)
        if len(datas) >= 2 and re.search(r"Realizado", texto, re.IGNORECASE):
            return datas[1], f"Validade (2ª data após Realizado): {datas[1].isoformat()}", pagina + 1
        if len(datas) == 1 and _RE_VALIDADE_ROTULO.search(texto) is None:
            # Uma única data perto da palavra validade
            if re.search(r"validade", texto, re.IGNORECASE):
                return datas[0], f"Validade: {datas[0].isoformat()}", pagina + 1
    return None, None, None


def _valor_apos_rotulo(texto: str, rotulo: str) -> int | None:
    """Aceita «Rótulo R$ X» ou «Rótulo\\nR$ X»."""
    m = re.search(
        rf"{rotulo}\s*(?:R\$\s*)?([\d.,]+)|{rotulo}\s*\n\s*R\$\s*([\d.,]+)",
        texto,
        re.IGNORECASE,
    )
    if m:
        bruto = m.group(1) or m.group(2)
        return valor_para_centavos(bruto)
    idx = re.search(rotulo, texto, re.IGNORECASE)
    if not idx:
        return None
    chunk = texto[idx.start() : idx.start() + 120]
    vals = extrair_valores_reais(chunk)
    return vals[0] if vals else None


def _localizar_pagina_resumo(doc: PdfDocumento) -> tuple[int, str]:
    """Página com bloco Resumo / Subtotal / Valor total mensal (costuma ser a 2)."""
    candidatos: list[tuple[int, int, str]] = []
    for pagina in range(min(doc.numero_paginas, 8)):
        texto, _ = texto_pagina_enriquecido(doc, pagina)
        score = 0
        if re.search(r"\bResumo\b", texto, re.IGNORECASE):
            score += 3
        if re.search(r"Subtotal", texto, re.IGNORECASE):
            score += 3
        if re.search(r"Valor total mensal", texto, re.IGNORECASE):
            score += 2
        if re.search(r"Taxa de inscri", texto, re.IGNORECASE):
            score += 1
        if _RE_PLANO_RESUMO.search(texto) and "R$" in texto:
            score += 2
        if score:
            candidatos.append((score, pagina, texto))
    if not candidatos:
        pagina = 4 if doc.numero_paginas > 4 else min(1, doc.numero_paginas - 1)
        texto, _ = texto_pagina_enriquecido(doc, pagina)
        return pagina, texto
    candidatos.sort(key=lambda x: (-x[0], x[1]))
    _, pagina, texto = candidatos[0]
    return pagina, texto


def _plano_resumo(doc: PdfDocumento) -> tuple[str | None, int, str]:
    """Plano destacado no resumo financeiro — nome completo (ex.: P320 Q COPAR)."""
    pagina, texto = _localizar_pagina_resumo(doc)
    # Preferir trecho após «Resumo»
    trecho = texto
    m_res = re.search(r"\bResumo\b", texto, re.IGNORECASE)
    if m_res:
        trecho = texto[m_res.start() : m_res.start() + 400]
    match = _RE_PLANO_RESUMO.search(trecho)
    if match:
        nome = normalizar_nome_plano_porto(match.group(1))
        return nome, pagina + 1, texto
    # Fallback: outras páginas iniciais
    for pagina in range(min(doc.numero_paginas, 6)):
        texto, _ = texto_pagina_enriquecido(doc, pagina)
        if "R$" not in texto:
            continue
        match = _RE_PLANO_RESUMO.search(texto)
        if match:
            return normalizar_nome_plano_porto(match.group(1)), pagina + 1, texto
    return None, 0, ""


def _extrair_resumo_financeiro(
    doc: PdfDocumento,
) -> tuple[int | None, int | None, int | None, dict]:
    meta: dict = {}
    pagina, texto = _localizar_pagina_resumo(doc)
    meta["pagina_resumo"] = pagina + 1

    datas = extrair_datas(texto)
    meta["data_emissao"] = datas[0] if datas else None

    match_num = re.search(r"Or[cç]amento\s*:\s*(\d{5,10})", texto, re.IGNORECASE)
    if not match_num:
        match_num = re.search(r"(\d{6,8})", texto)
    if match_num:
        meta["numero_cotacao"] = match_num.group(1)

    match_vidas = re.search(r"(\d+)\s+vidas?", texto, re.IGNORECASE)
    if match_vidas:
        meta["quantidade_vidas_total"] = int(match_vidas.group(1))

    premio = _valor_apos_rotulo(texto, r"Subtotal")
    iof = _valor_apos_rotulo(texto, r"IOF")
    taxa = _valor_apos_rotulo(texto, r"Taxa de inscri[cç][aã]o")
    if taxa is not None:
        meta["taxa_inscricao_centavos"] = taxa

    total = None
    m_total = re.search(
        r"Valor total mensal[^\n]*\n\s*R\$\s*([\d.,]+)|Valor total mensal.*?R\$\s*([\d.,]+)",
        texto,
        re.IGNORECASE | re.DOTALL,
    )
    if m_total:
        total = valor_para_centavos(m_total.group(1) or m_total.group(2))
    if total is not None:
        meta["total_mensal_impresso_centavos"] = total

    # Validade dedicada (pode estar nesta página)
    m_val = _RE_VALIDADE_ROTULO.search(texto)
    if m_val:
        meta["validade_oficial"] = _parse_data_br(m_val.group(1))

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
    trecho_validade: str | None,
    pagina_validade: int | None,
    pagina_resumo: int,
    associacao_confirmada: bool,
    codigo_resumo: str | None,
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
    # Total recorrente consistente com prêmio+IOF (sem taxa de inscrição — ver investigação).
    total_recorrente_centavos = None
    if associacao_confirmada:
        if premio is not None and iof is not None:
            total_recorrente_centavos = premio + iof
        elif total is not None and premio is not None and iof is None:
            total_recorrente_centavos = total

    trecho_val = trecho_validade
    if not validade:
        trecho_val = "Procurado em: " + "; ".join(_LOCAIS_VALIDADE) + "."

    opcao = OpcaoCotacaoCandidata(
        id=str(uuid.uuid4()),
        operadora=novo_campo(
            "Operadora",
            texto=OPERADORA,
            pagina=pagina_resumo,
            trecho=f"Operadora: {OPERADORA}",
            estado="confirmar",
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
        )
        if acomodacao
        else None,
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
        subtotal_impresso=novo_campo(
            "Subtotal impresso",
            centavos=premio if associacao_confirmada else None,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            pagina=pagina_resumo,
            trecho="Subtotal do resumo financeiro",
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        )
        if associacao_confirmada and premio is not None
        else None,
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
            centavos=total_recorrente_centavos,
            price_basis=PriceBasisRascunho.INCLUI_IOF,
            pagina=pagina_resumo,
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
        validade_oficial=novo_campo(
            "Validade",
            data=validade,
            pagina=pagina_validade or pagina_resumo,
            trecho=trecho_val,
            estado="confirmar" if validade else "ausente",
            parser_versao=PARSER_VERSAO,
            documento_hash=documento_hash,
        ),
    )
    reconciliar_opcao(opcao)
    if (
        not associacao_confirmada
        and codigo_resumo
        and opcao.reconciliacao
        and opcao.reconciliacao.status in {"nao_conferivel", "pendente"}
    ):
        opcao.reconciliacao.mensagem = (
            f"Estimativa pela população do SISCOR — o resumo do documento cita "
            f"«{codigo_resumo}», não este plano («{linha.plano_nome}»)."
        )
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

    validade, trecho_validade, pagina_validade = _extrair_validade_porto(doc)
    if validade is None:
        validade = meta_fin.get("validade_oficial")
    else:
        meta["validade_oficial"] = validade
    if validade is None:
        meta["validade_busca"] = list(_LOCAIS_VALIDADE)

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
                mensagem=(
                    "Plano selecionado não identificado no resumo financeiro "
                    f"(página {meta_fin.get('pagina_resumo', '?')})."
                ),
                severidade="alerta",
                pagina=meta_fin.get("pagina_resumo"),
            )
        )

    qtds = extrair_quantidades_faixa_porto(doc, codigo_resumo) if codigo_resumo else {}
    alguma_associacao = False
    nomes_tabela: list[str] = []
    linhas_detectadas = sum(s.linhas_tarifarias_detectadas for s in secoes)
    linhas_montadas = 0

    for secao in secoes:
        for linha in secao.linhas:
            linhas_montadas += 1
            nomes_tabela.append(linha.plano_nome)
            associacao_ok = False
            if codigo_resumo:
                associacao_ok = nomes_plano_equivalentes(codigo_resumo, linha.plano_nome)
            if associacao_ok:
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
                    trecho_validade=trecho_validade,
                    pagina_validade=pagina_validade,
                    pagina_resumo=pagina_resumo or meta_fin.get("pagina_resumo", 2),
                    associacao_confirmada=associacao_ok and codigo_resumo is not None,
                    codigo_resumo=codigo_resumo,
                )
            )

    ignoradas = max(0, linhas_detectadas - linhas_montadas)
    meta["linhas_tarifarias_detectadas"] = linhas_detectadas
    meta["opcoes_montadas"] = len(opcoes)
    meta["plano_resumo"] = codigo_resumo
    if ignoradas > 0:
        alertas.append(
            AlertaExtracaoCotacao(
                codigo="PDF-PORTO-006",
                mensagem=(
                    f"{ignoradas} plano(s) detectado(s) na tabela tarifária "
                    f"não puderam ser extraídos ({linhas_montadas} de "
                    f"{linhas_detectadas} linhas recuperadas). "
                    "Revise o PDF ou use entrada manual para os planos faltantes."
                ),
                severidade="alerta",
            )
        )

    if codigo_resumo and not alguma_associacao and opcoes:
        amostra = ", ".join(f"«{n}»" for n in nomes_tabela[:8])
        if len(nomes_tabela) > 8:
            amostra += f" … (+{len(nomes_tabela) - 8})"
        alertas.append(
            AlertaExtracaoCotacao(
                codigo="PDF-PORTO-005",
                mensagem=(
                    f'O resumo cita «{codigo_resumo}» e a tabela traz {amostra}. '
                    "Não foi possível casar o plano destacado com uma linha tarifária — "
                    "confirme manualmente antes de aplicar."
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
