"""Extração de tabelas tarifárias SulAmérica — layout com nomes quebrados e valores por coluna."""

from __future__ import annotations

import re
import unicodedata

from newport_app.cotacao_pdf.coords_extract import (
    LinhaPlanoExtraida,
    SecaoTabelaPagina,
    _ascii_lower,
    _coordenadas_linha,
    _linha_cabecalho_faixas,
    _regime_da_pagina,
    _texto_linha,
    classificar_regime_cabecalho,
    palavras_por_linha,
)
from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.text_utils import extrair_decimais, extrair_valores_reais, normalizar_espacos
from newport_app.siscor_importer.money import valor_para_centavos

NAME_X_MAX = 100.0
VALUE_X_MIN = 110.0
_RE_DECIMAL = re.compile(r"^\d{1,3}(?:\.\d{3})*,\d{2}$")
_RE_CELULA_VALOR = re.compile(r"^\d+(?:\.\d{3})*,\d{2}$")
_RE_DIGITO = re.compile(r"^\d+$")

_NOMES_GENERICOS = frozenset(
    {
        "nacional",
        "apartamento nacional",
        "direto apartamento",
        "direto nacional",
        "enfermaria",
        "apartamento",
    }
)

_FRAGMENTOS_CAUDA = frozenset({"nacional", "apartamento nacional"})

_CABECALHOS_NOME = frozenset(
    {
        "descricao do plano",
        "sem coparticipacao",
        "sem coparticip",
        "com coparticipacao",
        "30% de copart",
    }
)


def _norm_nome(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().strip()


def _eh_fragmento_cauda(texto: str) -> bool:
    return _norm_nome(texto).lower() in _FRAGMENTOS_CAUDA


def _eh_nome_generico(nome: str) -> bool:
    n = _norm_nome(nome)
    if len(n) < 5:
        return True
    return n.lower() in _NOMES_GENERICOS


def _eh_linha_nome(texto: str) -> bool:
    t = _norm_nome(texto)
    if t.lower() in _CABECALHOS_NOME:
        return False
    if len(t) < 3:
        return False
    tl = t.lower()
    if tl.startswith("tabela") or tl.startswith("*valores"):
        return False
    if "faixa et" in tl or "contrata" in tl:
        return False
    if re.fullmatch(r"[\d\s,\.%R\$]+", t, re.IGNORECASE):
        return False
    if _linha_cabecalho_faixas(t):
        return False
    return sum(1 for c in t if c.isalpha()) >= 3


def _merge_tokens_celula(tokens: list[str]) -> int | None:
    """Recompõe valor quando milhar veio partido (ex.: «1» + «111,15»)."""
    if not tokens:
        return None
    merged: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i].strip()
        if _RE_DIGITO.match(tok) and i + 1 < len(tokens) and _RE_DECIMAL.match(tokens[i + 1].strip()):
            combined = tok + tokens[i + 1].strip()
            v = valor_para_centavos(combined)
            if v is not None and v >= 10000:
                merged.append(tokens[i + 1].strip())
                i += 2
                continue
        merged.append(tok)
        i += 1
    texto = " ".join(merged)
    vals = extrair_valores_reais(texto)
    if vals:
        return vals[0]
    if _RE_DECIMAL.match(texto.strip()):
        return valor_para_centavos(texto.strip())
    return None


def _eh_nome_completo(texto: str) -> bool:
    if _eh_fragmento_cauda(texto) or _eh_nome_generico(texto):
        return False
    t = _norm_nome(texto).lower()
    return len(t.split()) >= 3 or "enfermaria" in t or "apartamento" in t


def _valores_de_linha(ws: list[tuple[float, float, float, float, str]]) -> tuple[list[int], list[str]]:
    """Extrai exatamente 10 valores monetários de uma linha de preços."""
    texto = _texto_linha(ws)
    flags: list[str] = []
    if _linha_cabecalho_faixas(texto):
        return [], flags

    tokens = [w[4].strip() for w in sorted(ws, key=lambda x: x[0]) if w[0] >= VALUE_X_MIN]
    col_vals: list[int] = []
    i = 0
    while i < len(tokens) and len(col_vals) < 10:
        tok = tokens[i]
        if _RE_DIGITO.match(tok) and i + 1 < len(tokens) and _RE_CELULA_VALOR.match(tokens[i + 1]):
            v = valor_para_centavos(tok + tokens[i + 1])
            if v is not None:
                col_vals.append(v)
                flags.append("valores_recompostos_por_token")
            i += 2
            continue
        if _RE_CELULA_VALOR.match(tok):
            v = valor_para_centavos(tok)
            if v is not None:
                col_vals.append(v)
        i += 1
    if len(col_vals) == 10:
        return col_vals, flags

    vals = extrair_valores_reais(texto)
    if len(vals) >= 10:
        return vals[:10], flags

    dec = extrair_decimais(texto)
    if len(dec) >= 10:
        return dec[:10], flags

    tokens = [w[4].strip() for w in sorted(ws, key=lambda x: x[0]) if w[0] >= VALUE_X_MIN]
    col_vals: list[int] = []
    for tok in tokens:
        if _RE_DECIMAL.match(tok):
            v = valor_para_centavos(tok)
            if v is not None:
                col_vals.append(v)
        elif _RE_DIGITO.match(tok):
            continue
    if len(col_vals) >= 10:
        return col_vals[:10], flags

    # tentativa por agrupamento de tokens adjacentes
    i = 0
    recomposed: list[int] = []
    while i < len(tokens) and len(recomposed) < 10:
        chunk = [tokens[i]]
        if _RE_DIGITO.match(tokens[i]) and i + 1 < len(tokens) and _RE_DECIMAL.match(tokens[i + 1]):
            chunk.append(tokens[i + 1])
            i += 2
        else:
            i += 1
        v = _merge_tokens_celula(chunk)
        if v is not None:
            recomposed.append(v)
    if len(recomposed) == 10:
        flags.append("valores_recompostos_por_token")
        return recomposed, flags

    if len(vals) > 0:
        flags.append("faixas_incompletas")
    return vals, flags


def _montar_nome_plano(
    y_valor: float,
    nomes: list[tuple[float, str]],
) -> tuple[str, list[str]]:
    """Associa fragmentos de nome à mesma linha de valores por proximidade vertical."""
    flags: list[str] = []
    candidatos = [(y, t) for y, t in nomes if t.lower() not in _CABECALHOS_NOME]

    depois_imediato = sorted(
        [(y, t) for y, t in candidatos if 0 < y - y_valor <= 10],
        key=lambda x: x[0],
    )
    for _, texto in depois_imediato:
        if _eh_nome_completo(texto):
            return _norm_nome(texto), flags

    antes = sorted([(y, t) for y, t in candidatos if y < y_valor], key=lambda x: x[0])
    depois = sorted([(y, t) for y, t in candidatos if y > y_valor], key=lambda x: x[0])
    antes_prox = [x for x in antes if y_valor - x[0] <= 28]
    depois_prox = [x for x in depois if x[0] - y_valor <= 12]

    if antes_prox and depois_prox:
        principal = antes_prox[-1][1]
        cauda = depois_prox[0][1]
        if _eh_fragmento_cauda(cauda):
            if principal.lower().endswith("apartamento") or "apartamento" in principal.lower():
                nome = normalizar_espacos(f"{principal} {cauda}")
            else:
                nome = principal
                flags.append("fragmento_cauda_ignorado")
        else:
            nome = principal
            flags.append("multiplos_nomes_proximos")
    elif antes_prox:
        nome = antes_prox[-1][1]
    elif depois_prox:
        nome = depois_prox[0][1]
    else:
        nome = ""

    nome = _norm_nome(nome)
    if _eh_nome_generico(nome):
        flags.append("nome_generico")
    return nome, flags


def detectar_sequencia_suspeita(valores: list[int]) -> list[int]:
    """Índices de faixas com queda abrupta (não corrige — só sinaliza)."""
    suspeitas: list[int] = []
    for i in range(len(valores) - 1):
        a, b = valores[i], valores[i + 1]
        if a is None or b is None:
            continue
        if a >= 80000 and b < a * 0.2:
            suspeitas.append(i + 1)
        elif a >= 50000 and b < 15000:
            suspeitas.append(i + 1)
    return suspeitas


def validar_linha_tarifaria(
    nome: str,
    valores: list[int],
    *,
    flags_extra: list[str] | None = None,
) -> tuple[bool, list[str]]:
    motivos: list[str] = list(flags_extra or [])
    if len(valores) != 10:
        motivos.append("faixas_incompletas")
    if _eh_nome_generico(nome):
        motivos.append("nome_generico")
    if "nome_ausente" in motivos or not nome:
        motivos.append("nome_possivelmente_fragmentado")
    suspeitas = detectar_sequencia_suspeita(valores)
    for idx in suspeitas:
        motivos.append(f"faixa_{idx}_valor_suspeito")
    return len(motivos) == 0, motivos


def extrair_tabelas_pagina_sulamerica(
    doc: PdfDocumento,
    pagina: int,
) -> SecaoTabelaPagina | None:
    rows = palavras_por_linha(doc, pagina)
    if not rows:
        return None

    linhas_ordenadas = sorted(rows.items())
    linhas_topo = [_texto_linha(ws) for _, ws in linhas_ordenadas[:15]]
    regime_tipo, copart_pct, regime_rotulo = _regime_da_pagina(linhas_topo)

    header_y: float | None = None
    cabecalho_faixas = ""
    for y, ws in linhas_ordenadas:
        texto = _texto_linha(ws)
        if _linha_cabecalho_faixas(texto):
            header_y = y
            cabecalho_faixas = texto
            break

    if header_y is None:
        return None

    nomes: list[tuple[float, str]] = []
    for y, ws in linhas_ordenadas:
        if y <= header_y:
            continue
        x0 = min(w[0] for w in ws)
        texto = _texto_linha(ws)
        if x0 < NAME_X_MAX and _eh_linha_nome(texto):
            nomes.append((y, _norm_nome(texto)))

    linhas_extraidas: list[LinhaPlanoExtraida] = []
    vistos: set[tuple[str, tuple[int, ...]]] = set()

    for y, ws in linhas_ordenadas:
        if y <= header_y:
            continue
        x0 = min(w[0] for w in ws)
        texto = _texto_linha(ws)
        if x0 < VALUE_X_MIN:
            continue

        valores, val_flags = _valores_de_linha(ws)
        if len(valores) != 10:
            continue

        nome, nome_flags = _montar_nome_plano(y, nomes)
        ok, motivos = validar_linha_tarifaria(nome, valores, flags_extra=nome_flags + val_flags)
        if not ok and "nome_generico" in motivos:
            continue

        chave = (nome, tuple(valores))
        if chave in vistos:
            continue
        vistos.add(chave)

        trecho = f"{nome} | {_texto_linha(ws)[:180]}"
        if motivos:
            trecho = f"{trecho} | alertas={','.join(motivos)}"

        linhas_extraidas.append(
            LinhaPlanoExtraida(
                plano_nome=nome,
                valores=valores,
                pagina=pagina + 1,
                trecho=trecho[:240],
                coordenadas=_coordenadas_linha(ws),
            )
        )

    if not linhas_extraidas:
        return None

    return SecaoTabelaPagina(
        pagina=pagina + 1,
        regime_tipo=regime_tipo,
        copart_percentual=copart_pct,
        regime_rotulo=regime_rotulo,
        linhas=linhas_extraidas,
        cabecalho=cabecalho_faixas or "\n".join(linhas_topo[:5]),
    )
