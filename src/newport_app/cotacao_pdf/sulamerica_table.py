"""Extração de tabelas tarifárias SulAmérica — layout com nomes quebrados e anotações «N vida»."""

from __future__ import annotations

import re
import unicodedata

from newport_app.cotacao_pdf.coords_extract import (
    LinhaPlanoExtraida,
    SecaoTabelaPagina,
    _coordenadas_linha,
    _linha_cabecalho_faixas,
    _regime_da_pagina,
    _texto_linha,
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
_RE_VIDA = re.compile(r"^(\d+)\s*vidas?$", re.IGNORECASE)
_RE_VIDA_TOKEN = re.compile(r"^vidas?$", re.IGNORECASE)

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
        "definicao do",
        "plano",
        "custo por faixa etaria",
    }
)

_ACOMODACOES = frozenset({"apartamento", "enfermaria"})


def _norm_nome(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().strip()


def _eh_fragmento_cauda(texto: str) -> bool:
    return _norm_nome(texto).lower() in _FRAGMENTOS_CAUDA


def _eh_nome_generico(nome: str) -> bool:
    n = _norm_nome(nome)
    if len(n) < 5:
        return True
    return n.lower() in _NOMES_GENERICOS


def _eh_anotacao_vida(texto: str) -> bool:
    t = _norm_nome(texto).lower()
    return bool(_RE_VIDA.match(t)) or t in {"vida", "vidas"}


def _eh_linha_nome(texto: str) -> bool:
    t = _norm_nome(texto)
    if t.lower() in _CABECALHOS_NOME:
        return False
    if _eh_anotacao_vida(t):
        return False
    if len(t) < 3:
        return False
    tl = t.lower()
    if tl.startswith("tabela") or tl.startswith("*valores"):
        return False
    if "faixa et" in tl or "contrata" in tl:
        return False
    if "premio" in tl or "iof" in tl or "validade" in tl or "proposta" in tl:
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


def _eh_token_vida(tok: str) -> bool:
    t = tok.strip()
    if _RE_VIDA.match(t):
        return True
    if _RE_VIDA_TOKEN.match(t):
        return True
    return False


def _valores_de_linha(ws: list[tuple[float, float, float, float, str]]) -> tuple[list[int], list[str]]:
    """Extrai até 10 valores monetários, ignorando anotações «N vida» intercaladas."""
    texto = _texto_linha(ws)
    flags: list[str] = []
    if _linha_cabecalho_faixas(texto):
        return [], flags

    tokens_pos = [
        (w[0], w[4].strip())
        for w in sorted(ws, key=lambda x: x[0])
        if w[0] >= VALUE_X_MIN and w[4].strip().upper() != "R$"
    ]
    # Remover «N vida» / «vida» (e o dígito órfão de «1»+«vida») antes de ler valores.
    tokens: list[str] = []
    i = 0
    while i < len(tokens_pos):
        tok = tokens_pos[i][1]
        if _RE_VIDA.match(tok):
            i += 1
            continue
        if _RE_DIGITO.match(tok) and i + 1 < len(tokens_pos) and _RE_VIDA_TOKEN.match(
            tokens_pos[i + 1][1]
        ):
            i += 2
            continue
        if _RE_VIDA_TOKEN.match(tok):
            i += 1
            continue
        tokens.append(tok)
        i += 1

    col_vals: list[int] = []
    i = 0
    while i < len(tokens) and len(col_vals) < 10:
        tok = tokens[i]
        if (
            _RE_DIGITO.match(tok)
            and i + 1 < len(tokens)
            and re.match(r"^\d{3},\d{2}$", tokens[i + 1])
            and len(tok) <= 3
        ):
            # «1» + «111,15» (milhar partido sem ponto). Evita «1»+«440,09» de anotação.
            # Só recompõe quando o prefixo forma milhar (>= R$ 1.000,00).
            v = valor_para_centavos(tok + tokens[i + 1])
            if v is not None and v >= 100000:
                col_vals.append(v)
                flags.append("valores_recompostos_por_token")
                i += 2
                continue
        if _RE_CELULA_VALOR.match(tok) or _RE_DECIMAL.match(tok):
            v = valor_para_centavos(tok)
            if v is not None:
                col_vals.append(v)
        i += 1
    if len(col_vals) == 10:
        return col_vals, flags

    # Fallback: valores reais no texto (extrair_valores_reais já ignora não-monetários)
    vals = extrair_valores_reais(texto)
    if len(vals) >= 10:
        return vals[:10], flags

    dec = extrair_decimais(texto)
    if len(dec) >= 10:
        return dec[:10], flags

    if len(col_vals) > 0:
        flags.append("faixas_incompletas")
    return col_vals if col_vals else vals, flags


def _centros_faixas_cabecalho(
    linhas_ordenadas: list[tuple[float, list[tuple[float, float, float, float, str]]]],
    header_y: float,
) -> list[float] | None:
    for y, ws in linhas_ordenadas:
        if abs(y - header_y) > 1:
            continue
        tokens = sorted(
            [(w[0], w[4]) for w in ws if w[0] >= 30],
            key=lambda x: x[0],
        )
        # Pares «0 a 18», «19 a 23», … ou token «59+»
        centros: list[float] = []
        i = 0
        while i < len(tokens) and len(centros) < 10:
            tok = tokens[i][1]
            if re.match(r"^\d+", tok) or tok.startswith("59"):
                x0 = tokens[i][0]
                x1 = x0
                j = i + 1
                while j < len(tokens) and j <= i + 2:
                    if tokens[j][1].lower() in {"a", "-", "–"} or re.match(
                        r"^\d+", tokens[j][1]
                    ):
                        x1 = tokens[j][0]
                        j += 1
                    else:
                        break
                centros.append((x0 + x1) / 2)
                i = j
            else:
                i += 1
        if len(centros) >= 10:
            return centros[:10]
    return None


def _quantidades_por_faixa(
    linhas_ordenadas: list[tuple[float, list[tuple[float, float, float, float, str]]]],
    y_valor: float,
    centros_faixa: list[float] | None,
) -> tuple[list[int | None], list[str]]:
    """Lê anotações «N vida» próximas da linha de valores e associa à faixa por X."""
    qtds: list[int | None] = [None] * 10
    trechos: list[str] = [""] * 10
    if not centros_faixa:
        return qtds, trechos

    for y, ws in linhas_ordenadas:
        if abs(y - y_valor) > 18:
            continue
        # Tokens na faixa de valores
        i = 0
        ordered = sorted(ws, key=lambda w: w[0])
        while i < len(ordered):
            w = ordered[i]
            if w[0] < VALUE_X_MIN - 30:
                i += 1
                continue
            tok = w[4].strip()
            qtd_val: int | None = None
            trecho = tok
            m = _RE_VIDA.match(tok)
            if m:
                qtd_val = int(m.group(1))
            elif _RE_DIGITO.match(tok) and i + 1 < len(ordered) and _RE_VIDA_TOKEN.match(
                ordered[i + 1][4].strip()
            ):
                qtd_val = int(tok)
                trecho = f"{tok} {ordered[i + 1][4].strip()}"
                i += 1
            if qtd_val is not None:
                # Centro aproximado da anotação
                x_ref = w[0]
                faixa = min(range(10), key=lambda fi: abs(centros_faixa[fi] - x_ref))
                if qtds[faixa] is None:
                    qtds[faixa] = qtd_val
                    trechos[faixa] = trecho
            i += 1
    return qtds, trechos


def _classificar_fragmento(texto: str) -> str:
    t = _norm_nome(texto).lower()
    if t in _ACOMODACOES:
        return "acomodacao"
    if re.search(r"\b(sp|rj|cap\d*|nacional)\b", t) and (
        len(t.split()) <= 3 or t.startswith("sp") or t.startswith("rj")
    ):
        if t in {"nacional"} or t.startswith("sp") or t.startswith("rj") or "cap" in t:
            return "abrangencia"
    if any(
        k in t
        for k in ("direto", "especial", "executivo", "classico", "clássico", "vital", "mais")
    ):
        return "produto"
    if t in _NOMES_GENERICOS:
        return "abrangencia" if t == "nacional" else "outro"
    return "produto" if len(t.split()) >= 2 else "outro"


def _janela_nome_plano(
    y_valor: float,
    nomes: list[tuple[float, str]],
    y_valores: list[float],
    header_y: float,
) -> list[tuple[float, str]]:
    """Fragmentos de nome entre a linha anterior e a seguinte (evita misturar planos)."""
    ys = sorted(y_valores)
    try:
        idx = ys.index(y_valor)
    except ValueError:
        idx = min(range(len(ys)), key=lambda i: abs(ys[i] - y_valor)) if ys else 0
    y_prev = ys[idx - 1] if idx > 0 else header_y
    y_next = ys[idx + 1] if idx + 1 < len(ys) else y_valor + 48.0
    lo = (y_prev + y_valor) / 2.0 if idx > 0 else header_y
    hi = (y_valor + y_next) / 2.0
    janela = [
        (y, t)
        for y, t in nomes
        if t.lower() not in _CABECALHOS_NOME and (lo < y < hi or abs(y - y_valor) <= 10)
    ]
    if janela:
        return sorted(janela, key=lambda x: x[0])
    # Fallback: proximidade simples (faixa única com nome bem acima)
    return sorted(
        [
            (y, t)
            for y, t in nomes
            if t.lower() not in _CABECALHOS_NOME and -70 <= (y - y_valor) <= 24
        ],
        key=lambda x: x[0],
    )


def _compor_nome_plano(
    y_valor: float,
    nomes: list[tuple[float, str]],
    *,
    y_valores: list[float] | None = None,
    header_y: float = 0.0,
) -> tuple[str, str | None, list[str]]:
    """Compõe nome a partir de fragmentos verticais da célula do plano."""
    flags: list[str] = []
    if y_valores:
        janela = _janela_nome_plano(y_valor, nomes, y_valores, header_y)
    else:
        janela = [
            (y, t)
            for y, t in nomes
            if t.lower() not in _CABECALHOS_NOME and -70 <= (y - y_valor) <= 24
        ]
        if not janela:
            janela = [
                (y, t)
                for y, t in nomes
                if t.lower() not in _CABECALHOS_NOME and abs(y - y_valor) <= 90
            ]

    produtos: list[str] = []
    acomodacoes: list[str] = []
    abrangencias: list[str] = []
    outros: list[str] = []

    for _, texto in sorted(janela, key=lambda x: x[0]):
        kind = _classificar_fragmento(texto)
        norm = _norm_nome(texto)
        if kind == "acomodacao":
            if norm not in acomodacoes:
                acomodacoes.append(norm)
        elif kind == "abrangencia":
            if norm not in abrangencias:
                abrangencias.append(norm)
        elif kind == "produto":
            if norm not in produtos:
                produtos.append(norm)
        else:
            if norm not in outros:
                outros.append(norm)

    acomodacao = acomodacoes[-1] if acomodacoes else None
    if produtos:
        principal = produtos[-1]
    elif outros:
        principal = max(outros, key=lambda s: len(s))
    elif acomodacao and abrangencias:
        principal = f"{outros[0] if outros else 'Plano'}"
        flags.append("nome_parcial")
        principal = abrangencias[0]
    else:
        principal = ""

    # Evitar duplicar acomodação já contida no principal
    partes_nome = [principal] if principal else []
    if acomodacao and acomodacao.lower() not in (principal or "").lower():
        partes_nome.append(acomodacao)

    if len(partes_nome) >= 2:
        nome = f"{partes_nome[0]} — {partes_nome[1]}"
    elif partes_nome:
        nome = partes_nome[0]
    else:
        nome = ""

    # Incluir Nacional / SP (CAP1) quando forem linhas distintas do produto
    abr_para_paren: list[str] = []
    for a in abrangencias:
        al = a.lower()
        if al in nome.lower() and al != "nacional":
            continue
        if al == "nacional" and "nacional" in (principal or "").lower():
            # «Direto Nacional» já traz Nacional; ainda assim o PDF mostra linha «Nacional» + «SP»
            continue
        abr_para_paren.append(a)
    # Se havia linha «Nacional» separada + SP/RJ, preferir ambas no parêntese
    if any(a.lower() == "nacional" for a in abrangencias) and any(
        "sp" in a.lower() or "rj" in a.lower() or "cap" in a.lower() or "int" in a.lower()
        for a in abrangencias
    ):
        abr_para_paren = []
        for a in abrangencias:
            if a not in abr_para_paren:
                abr_para_paren.append(a)

    if abr_para_paren and nome:
        nome = f"{nome} ({' / '.join(abr_para_paren)})"
        flags.append("nome_composto_fragmentos")
    elif not nome and abr_para_paren:
        nome = " / ".join(abr_para_paren)
        flags.append("nome_somente_abrangencia")

    nome = normalizar_espacos(nome)
    if _eh_nome_generico(nome):
        flags.append("nome_generico")
    return nome, acomodacao, flags


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

    centros_faixa = _centros_faixas_cabecalho(linhas_ordenadas, header_y)

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
    candidatas = 0

    candidatas_raw: list[tuple[float, list[tuple[float, float, float, float, str]], list[int], list[str]]] = []
    for y, ws in linhas_ordenadas:
        if y <= header_y:
            continue
        x0 = min(w[0] for w in ws)
        if x0 < VALUE_X_MIN:
            continue
        if _eh_anotacao_vida(_texto_linha(ws)):
            continue
        valores, val_flags = _valores_de_linha(ws)
        if len(valores) != 10:
            continue
        candidatas_raw.append((y, ws, valores, val_flags))

    candidatas = len(candidatas_raw)
    y_valores = [y for y, _, _, _ in candidatas_raw]

    for y, ws, valores, val_flags in candidatas_raw:
        nome, acomodacao, nome_flags = _compor_nome_plano(
            y, nomes, y_valores=y_valores, header_y=header_y
        )
        ok, motivos = validar_linha_tarifaria(nome, valores, flags_extra=nome_flags + val_flags)
        # Aceitar linha com nome genérico apenas se houver composição (— ou parênteses).
        if "nome_generico" in motivos and "—" not in nome and "(" not in nome:
            continue
        if not nome:
            continue

        qtds, trechos_qtd = _quantidades_por_faixa(linhas_ordenadas, y, centros_faixa)

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
                quantidades=qtds,
                acomodacao=acomodacao,
            )
        )
        if any(q is not None for q in qtds):
            qtd_txt = ",".join(
                trechos_qtd[i] or "-" for i in range(10) if qtds[i] is not None
            )
            linhas_extraidas[-1].trecho = f"{linhas_extraidas[-1].trecho} | qtds={qtd_txt}"[
                :240
            ]

    if candidatas == 0 and not linhas_extraidas:
        return None

    return SecaoTabelaPagina(
        pagina=pagina + 1,
        regime_tipo=regime_tipo,
        copart_percentual=copart_pct,
        regime_rotulo=regime_rotulo,
        linhas=linhas_extraidas,
        cabecalho=cabecalho_faixas or "\n".join(linhas_topo[:5]),
        contexto_pagina="\n".join(linhas_topo[:12]),
        linhas_tarifarias_detectadas=candidatas,
    )
