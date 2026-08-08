"""Parser Amil — extração por posicionamento (PyMuPDF)."""

from __future__ import annotations

import re
import uuid

from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.faixas import faixa_de_rotulo
from newport_app.cotacao_pdf.parsers.base import faixa_extraida, novo_campo
from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
from newport_app.cotacao_pdf.text_utils import extrair_valor_token, normalizar_espacos
from newport_app.models.cotacao_pdf import AlertaExtracaoCotacao, OpcaoCotacaoCandidata
from newport_app.models.draft import PriceBasisRascunho
from newport_app.siscor_importer.money import valor_para_centavos

PARSER_VERSAO = "amil@1.1.0"
OPERADORA = "Amil"
TEMPLATE_ID = "amil-visual-v1"

_RE_LIXO_ROTULO = re.compile(
    r"^(subtotal|total|valor\s+por\s+vida|valor\s+unit[aá]rio.*|plano\s+dental|"
    r"total\s+subtotal.*|\d[\d\s]*)$",
    re.IGNORECASE,
)


def identificar(doc: PdfDocumento) -> bool:
    amostra = doc.texto_todo().upper()
    return "AMIL" in amostra


def _linhas_por_y(words: list[tuple]) -> dict[int, list[tuple]]:
    rows: dict[int, list[tuple]] = {}
    for w in words:
        y = int(round(w[1], 0))
        rows.setdefault(y, []).append(w)
    return rows


def _valores_linha(words: list[tuple]) -> list[int]:
    """Lê valores por token — evita regex que captura «073,96» de «R$1073,96»."""
    vals: list[int] = []
    for w in sorted(words, key=lambda x: x[0]):
        v = extrair_valor_token(w[4])
        if v is not None:
            vals.append(v)
    return vals


def _eh_rotulo_lixo(texto: str) -> bool:
    t = normalizar_espacos(texto)
    if not t:
        return True
    if _RE_LIXO_ROTULO.match(t):
        return True
    # Linha de quantitativos por faixa («4 2 4 0 0 1 …»)
    tokens = t.split()
    digitos = sum(1 for tok in tokens if tok.isdigit())
    if digitos >= 5 and digitos >= len(tokens) * 0.7:
        return True
    return False


def _limpar_nome_plano(texto: str) -> str:
    t = normalizar_espacos(texto)
    # Remove contagens coladas ao nome («… COPART 1 0 0 0 0 0 2»)
    t = re.sub(r"(?:\s+\d+){3,}\s*$", "", t).strip()
    return t[:80]


def _nome_plano_acima(
    rows: dict[int, list[tuple]],
    y_atual: int,
    header_y: int,
) -> str | None:
    candidatos: list[str] = []
    for y, ws in sorted(rows.items()):
        if y <= header_y or y >= y_atual:
            continue
        linha = normalizar_espacos(" ".join(w[4] for w in sorted(ws, key=lambda x: x[0])))
        if "R$" in linha:
            continue
        if _eh_rotulo_lixo(linha):
            continue
        if not re.search(r"[A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]{3,}", linha):
            continue
        limpo = _limpar_nome_plano(linha)
        if limpo:
            candidatos.append(limpo)
    if not candidatos:
        return None
    # Prefere o rótulo mais informativo logo acima da tabela de valores.
    return max(candidatos[-3:], key=lambda s: (len(re.findall(r"[A-Za-zÁ-ú]{2,}", s)), len(s)))


def _eh_linha_artefato(nome: str, valores: list[int], trecho: str) -> str | None:
    """Retorna motivo se a linha não for tabela de plano (ex.: subtotal por faixa)."""
    faixa_vals = valores[:10]
    zeros = sum(1 for v in faixa_vals if v == 0)
    if "subtotal" in trecho.lower():
        return "linha_subtotal"
    if len(valores) > 10:
        return "coluna_total_agregado"
    if zeros >= 3:
        return "valores_esparsos"
    return None


def parse(
    doc: PdfDocumento,
    *,
    documento_hash: str,
) -> tuple[list[OpcaoCotacaoCandidata], list[AlertaExtracaoCotacao], dict]:
    alertas: list[AlertaExtracaoCotacao] = []
    meta: dict = {}
    planos: list[tuple[str, list[int], int, str]] = []

    for pagina in range(doc.numero_paginas):
        words = doc.palavras_pymupdf(pagina)
        if not words:
            continue
        rows = _linhas_por_y(words)
        header_y = None
        for y, ws in rows.items():
            linha = " ".join(w[4] for w in sorted(ws, key=lambda x: x[0]))
            if faixa_de_rotulo("0 a 18") is not None and "18" in linha and "19" in linha:
                header_y = y
                break
        if header_y is None:
            continue
        for y, ws in sorted(rows.items()):
            if y <= header_y:
                continue
            linha = " ".join(w[4] for w in sorted(ws, key=lambda x: x[0]))
            vals = _valores_linha(ws)
            if len(vals) < 10:
                if len(vals) == 1 and "total" in linha.lower():
                    meta.setdefault("totais_pagina", []).append(vals[0])
                continue

            nome = linha.split("R$")[0].strip()
            if not nome:
                nome = _nome_plano_acima(rows, y, header_y) or ""
            motivo = _eh_linha_artefato(nome, vals, linha)
            if motivo:
                alertas.append(
                    AlertaExtracaoCotacao(
                        codigo="PDF-AMIL-003",
                        mensagem=(
                            f"Linha ignorada ({motivo}): parece subtotal ou resumo, "
                            "não uma tabela de plano."
                        ),
                        severidade="info",
                        pagina=pagina + 1,
                    )
                )
                continue
            if not nome:
                nome = f"Plano Amil (pág. {pagina + 1})"
                alertas.append(
                    AlertaExtracaoCotacao(
                        codigo="PDF-AMIL-004",
                        mensagem="Nome do plano não encontrado na linha — confira no PDF.",
                        severidade="alerta",
                        pagina=pagina + 1,
                    )
                )

            planos.append((nome[:80], vals[:10], pagina + 1, linha))

    if not planos:
        alertas.append(
            AlertaExtracaoCotacao(
                codigo="PDF-AMIL-001",
                mensagem="Tabela visual de prêmios não localizada — use entrada manual.",
                severidade="alerta",
            )
        )
        return [], alertas, meta

    # Deduplicar linhas idênticas (mesmo nome + mesmos valores)
    vistos: set[tuple[str, tuple[int, ...]]] = set()
    planos_unicos: list[tuple[str, list[int], int, str]] = []
    for nome, valores, pagina, trecho in planos:
        chave = (nome.upper(), tuple(valores))
        if chave in vistos:
            continue
        vistos.add(chave)
        planos_unicos.append((nome, valores, pagina, trecho))

    opcoes: list[OpcaoCotacaoCandidata] = []
    for nome, valores, pagina, trecho in planos_unicos[:6]:
        tabela = [
            faixa_extraida(
                idx,
                valor_centavos=centavos,
                quantidade=None,
                price_basis=PriceBasisRascunho.EXCLUI_IOF,
                pagina=pagina,
                trecho_valor=trecho,
                trecho_qtd=None,
                parser_versao=PARSER_VERSAO,
                documento_hash=documento_hash,
            )
            for idx, centavos in enumerate(valores)
        ]
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
                texto=nome,
                pagina=pagina,
                trecho=trecho,
                parser_versao=PARSER_VERSAO,
                documento_hash=documento_hash,
            ),
            regime_copart=novo_campo(
                "Regime de coparticipação",
                texto="parcial",
                estado="revisar",
                parser_versao=PARSER_VERSAO,
                documento_hash=documento_hash,
            ),
            tabela=tabela,
        )
        reconciliar_opcao(opcao)
        opcoes.append(opcao)

    for pagina in range(doc.numero_paginas):
        texto = doc.texto(pagina)
        match = re.search(r"R\$\s*([\d.,]+)", texto)
        if match and "parcela" in texto.lower():
            meta["primeira_parcela"] = valor_para_centavos(match.group(1))

    return opcoes, alertas, meta
