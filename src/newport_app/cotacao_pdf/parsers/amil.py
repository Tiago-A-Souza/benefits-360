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

PARSER_VERSAO = "amil@1.2.0"
OPERADORA = "Amil"
TEMPLATE_ID = "amil-visual-v1"

_RE_LIXO_ROTULO = re.compile(
    r"^(subtotal|total|valor\s+por\s+vida|valor\s+unit[aá]rio.*|plano\s+dental|"
    r"total\s+subtotal.*|\d[\d\s]*)$",
    re.IGNORECASE,
)
_RE_CONTAGEM_FINAL = re.compile(r"(?:\s+\d+){3,}\s*$")
# Produto Amil na vizinhança da tabela (nunca capa institucional).
_RE_PRODUTO_AMIL = re.compile(
    r"(?i)\b(?:AMIL\s+)?(?:BRONZE|PRATA|OURO|PLATINUM|BLACK|S\d{2,5})\b"
)
_RE_INSTITUCIONAL = re.compile(
    r"(?i)\b(marca|empresas?|queridas|valiosa|benef[ií]cios|redes\s+sociais|"
    r"mais\s+valiosa|mais\s+queridas)\b"
)
_RE_SUFIXO_CONTINUACAO = re.compile(
    r"(?i)^(COPART(?:ICIPA[CÇ][AÃ]O)?(?:\s+PJ)?|TP|CP|NAC|PJ)$"
)
_RE_QC_QP = re.compile(r"\b(QC|QP)\b", re.IGNORECASE)


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
    t = _RE_CONTAGEM_FINAL.sub("", t).strip()
    return t[:80]


def _eh_nome_plano_amil(texto: str) -> bool:
    """Aceita só nomenclatura de produto Amil; rejeita fragmentos institucionais."""
    t = _limpar_nome_plano(texto)
    if len(t) < 5:
        return False
    if not _RE_PRODUTO_AMIL.search(t):
        return False
    if _RE_INSTITUCIONAL.search(t):
        return False
    return True


def _inferir_acomodacao_amil(nome: str) -> str | None:
    match = _RE_QC_QP.search(nome or "")
    if not match:
        return None
    return "Enfermaria" if match.group(1).upper() == "QC" else "Apartamento"


def _nome_plano_acima(
    rows: dict[int, list[tuple]],
    y_atual: int,
    header_y: int,
) -> str | None:
    """Nome na vizinhança imediatamente acima da linha de valores da tabela."""
    itens: list[tuple[int, str]] = []
    for y, ws in sorted(rows.items()):
        if y <= header_y or y >= y_atual:
            continue
        linha = normalizar_espacos(" ".join(w[4] for w in sorted(ws, key=lambda x: x[0])))
        if "R$" in linha:
            continue
        if re.match(r"(?i)^(subtotal|valor\s+por\s+vida|valor\s+unit)", linha):
            continue
        limpo = _limpar_nome_plano(linha)
        if not limpo:
            continue
        # Contagens puras sem produto
        if _eh_rotulo_lixo(linha) and not _eh_nome_plano_amil(limpo):
            continue
        itens.append((y, limpo))

    nome_idx: int | None = None
    for i in range(len(itens) - 1, -1, -1):
        if _eh_nome_plano_amil(itens[i][1]):
            nome_idx = i
            break
    if nome_idx is None:
        return None

    partes = [itens[nome_idx][1]]
    for j in range(nome_idx + 1, len(itens)):
        cand = itens[j][1]
        if _eh_nome_plano_amil(cand):
            break
        if _RE_SUFIXO_CONTINUACAO.match(cand):
            if cand.upper() not in partes[0].upper():
                partes.append(cand)
            continue
        break
    return normalizar_espacos(" ".join(partes))


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

            inline = _limpar_nome_plano(linha.split("R$")[0])
            if _eh_nome_plano_amil(inline):
                nome = inline
            else:
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
            if not _eh_nome_plano_amil(nome):
                nome = ""

            planos.append((nome, vals[:10], pagina + 1, linha))

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
        chave = ((nome or "").upper(), tuple(valores))
        if chave in vistos:
            continue
        vistos.add(chave)
        planos_unicos.append((nome, valores, pagina, trecho))

    opcoes: list[OpcaoCotacaoCandidata] = []
    plano_neutro = 0
    for nome, valores, pagina, trecho in planos_unicos[:6]:
        if not nome:
            plano_neutro += 1
            nome = f"Plano {plano_neutro}"
            alertas.append(
                AlertaExtracaoCotacao(
                    codigo="PDF-AMIL-004",
                    mensagem=(
                        f"Nome do plano não determinado com segurança na tabela "
                        f"(pág. {pagina}) — usando rótulo neutro «{nome}»."
                    ),
                    severidade="alerta",
                    pagina=pagina,
                )
            )
        acomodacao = _inferir_acomodacao_amil(nome)
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
            acomodacao=(
                novo_campo(
                    "Acomodação",
                    texto=acomodacao,
                    pagina=pagina,
                    trecho=nome,
                    estado="confirmar",
                    parser_versao=PARSER_VERSAO,
                    documento_hash=documento_hash,
                )
                if acomodacao
                else None
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
