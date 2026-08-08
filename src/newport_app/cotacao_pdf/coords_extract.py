"""Extração por coordenadas — tabelas tarifárias em PDF."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.faixas import faixa_de_rotulo
from newport_app.cotacao_pdf.ocr import tentar_ocr_pagina
from newport_app.cotacao_pdf.text_utils import extrair_decimais, extrair_valores_reais, normalizar_espacos
from newport_app.siscor_importer.money import valor_para_centavos

_RE_FAIXA_HEADER = re.compile(
    r"0\s*[-–a]\s*18",
    re.IGNORECASE,
)
_RE_PLANO_PORTO = re.compile(
    r"(P\d{3}\s*[EQ](?:\s+COPAR(?:\s+\d{1,2})?)?|"
    r"(?:BRONZE|PRATA|OURO|DIAMANTE)"
    r"(?:\s+(?:RIO|BRASIL))?(?:\s+(?:PRO|MAIS|MAX))?(?:\s+I)?\s*[EQ]"
    r"(?:\s+COPAR(?:\s+\d{1,2})?)?)",
    re.IGNORECASE,
)
_RE_PCT_COPART = re.compile(r"(\d{1,2})\s*%\s*de\s+copart", re.IGNORECASE)
_RE_DECIMAL_LINHA = re.compile(r"(?<!\d)([\d]{1,3}(?:\.\d{3})*,\d{2})(?!\d)")
_RE_PRECO_TOKEN = re.compile(r"^[\d.,]+$")
_RE_COPAR_NOME = re.compile(r"COPAR(?:\s*(\d{1,2}))?", re.IGNORECASE)
_RE_PCODE = re.compile(r"^P\d{3}\s*[EQ](?:\s+COPAR(?:\s+\d{1,2})?)?$", re.IGNORECASE)


@dataclass
class LinhaPlanoExtraida:
    plano_nome: str
    valores: list[int]
    pagina: int
    trecho: str
    coordenadas: str | None = None
    quantidades: list[int | None] | None = None
    acomodacao: str | None = None


@dataclass
class SecaoTabelaPagina:
    pagina: int
    regime_tipo: str
    copart_percentual: int | None
    regime_rotulo: str
    linhas: list[LinhaPlanoExtraida]
    cabecalho: str
    contexto_pagina: str = ""
    linhas_tarifarias_detectadas: int = 0


def _ascii_lower(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def texto_pagina_enriquecido(doc: PdfDocumento, pagina: int) -> tuple[str, bool]:
    texto = doc.texto(pagina)
    if len(texto.strip()) >= 80 and (
        len(extrair_decimais(texto)) >= 3 or "copart" in _ascii_lower(texto) or "tabela" in _ascii_lower(texto)
    ):
        return texto, False
    ocr, ok = tentar_ocr_pagina(doc, pagina)
    if ok and len(ocr.strip()) > len(texto.strip()):
        return ocr, True
    return texto, False


def palavras_por_linha(doc: PdfDocumento, pagina: int) -> dict[float, list[tuple[float, float, float, float, str]]]:
    words = doc.palavras_pymupdf(pagina)
    rows: dict[float, list[tuple[float, float, float, float, str]]] = {}
    for w in words:
        y = round(w[1], 0)
        rows.setdefault(y, []).append(w)
    return {y: sorted(ws, key=lambda x: x[0]) for y, ws in rows.items()}


def _texto_linha(words: list[tuple[float, float, float, float, str]]) -> str:
    return normalizar_espacos(" ".join(w[4] for w in words))


def _coordenadas_linha(words: list[tuple[float, float, float, float, str]]) -> str:
    if not words:
        return ""
    x0 = min(w[0] for w in words)
    y0 = min(w[1] for w in words)
    x1 = max(w[2] for w in words)
    y1 = max(w[3] for w in words)
    return f"{x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f}"


def _x_limite_nome_colunas(header_ws: list[tuple[float, float, float, float, str]]) -> float | None:
    for w in header_ws:
        if re.search(r"0\s*[-–]?\s*18|00-18", w[4], re.IGNORECASE):
            return w[0] - 5
    return None


def _valores_coluna_preco(words: list[tuple[float, float, float, float, str]], x_limite: float) -> list[int]:
    tokens = [w[4] for w in words if w[0] >= x_limite and _RE_PRECO_TOKEN.match(w[4])]
    if not tokens:
        return []
    texto = " ".join(tokens)
    vals = extrair_decimais(texto)
    if len(vals) >= 10:
        return vals[:10]
    vals = extrair_valores_reais(texto)
    return vals[:10] if len(vals) >= 10 else vals


def _nome_coluna_plano(words: list[tuple[float, float, float, float, str]], x_limite: float) -> str:
    return normalizar_espacos(" ".join(w[4] for w in words if w[0] < x_limite)).strip()


def classificar_regime_plano_porto(nome_plano: str, cabecalho: str) -> tuple[str, int | None, str]:
    """Classifica regime pelo nome do plano (COPAR 30) e, se necessário, pelo cabeçalho."""
    nome_u = nome_plano.upper()
    match = _RE_COPAR_NOME.search(nome_u)
    if match:
        pct = int(match.group(1)) if match.group(1) else 30
        return "percentual", pct, f"Coparticipação {pct}%"

    regime_tipo, copart_pct, rotulo = classificar_regime_cabecalho(cabecalho)
    if regime_tipo == "ambíguo":
        return "a_confirmar", None, "A confirmar"
    return regime_tipo, copart_pct, rotulo


def _valores_monetarios(texto: str) -> list[int]:
    vals = extrair_valores_reais(texto)
    if len(vals) >= 10:
        return vals[:10]
    dec = extrair_decimais(texto)
    if len(dec) >= 10:
        return dec[:10]
    collected: list[int] = []
    for match in _RE_DECIMAL_LINHA.finditer(texto):
        v = valor_para_centavos(match.group(1))
        if v is not None and v >= 1000:
            collected.append(v)
    return collected[:10] if len(collected) >= 10 else collected


def _linha_cabecalho_faixas(texto: str) -> bool:
    if not _RE_FAIXA_HEADER.search(texto):
        return False
    return bool(re.search(r"59", texto))


def _eh_secao_acomodacao(texto: str) -> bool:
    t = _ascii_lower(texto.strip())
    return t in {"enfermaria", "apartamento", "plano"}


def _eh_codigo_plano_porto(texto: str) -> bool:
    """Aceita códigos alfanuméricos Porto: P220 Q, P320 E COPAR, etc."""
    t = texto.strip()
    if _RE_PCODE.match(t):
        return True
    if _RE_PLANO_PORTO.fullmatch(t):
        return True
    return bool(re.fullmatch(r"P\d{3}\s*[EQ](?:\s+COPAR(?:\s+\d{1,2})?)?", t, re.IGNORECASE))


def _eh_nome_plano_valido(texto: str) -> bool:
    t = texto.strip()
    if len(t) < 4:
        return False
    if _linha_cabecalho_faixas(t):
        return False
    if re.fullmatch(r"[\d\s,\.%R\$]+", t, re.IGNORECASE):
        return False
    if re.search(r"\bvida[s]?\b", t, re.IGNORECASE) and len(t) < 35:
        return False
    if _eh_secao_acomodacao(t):
        return False
    if t.lower().startswith("tabela"):
        return False
    if "ans" in t.lower() and "proposta" in t.lower():
        return False
    if _eh_codigo_plano_porto(t):
        return True
    letras = sum(1 for c in t if c.isalpha())
    return letras >= 4


def _limpar_sufixo_preco_nome(nome: str, valores: list[int]) -> str:
    """Remove tokens de preço/faixa acidentalmente colados ao nome do plano."""
    nome = re.sub(r"\s+", " ", nome.strip())
    if not nome:
        return nome
    tokens = nome.split()
    primeiro = valores[0] if valores else None

    def _token_e_preco(tok: str) -> bool:
        if re.fullmatch(r"[\d.,]+", tok):
            v = valor_para_centavos(tok)
            if v is not None and primeiro is not None and v == primeiro:
                return True
            if re.fullmatch(r"\d{1,3},\d{2}", tok):
                return True
        if primeiro is not None and re.fullmatch(r"\d{2,4}", tok):
            n = int(tok)
            if primeiro // 100 == n:
                return True
        return False

    while tokens and _token_e_preco(tokens[-1]):
        tokens.pop()
    return " ".join(tokens).strip()


def _nome_plano_de_texto(texto: str, valores: list[int]) -> str:
    antes = _RE_DECIMAL_LINHA.split(texto)[0].strip()
    match = _RE_PLANO_PORTO.search(antes or texto)
    if match:
        return _limpar_sufixo_preco_nome(match.group(1).upper().replace("  ", " ").strip(), valores)
    if _eh_nome_plano_valido(antes):
        return _limpar_sufixo_preco_nome(antes[:80], valores)
    return ""


def classificar_regime_cabecalho(texto_cabecalho: str) -> tuple[str, int | None, str]:
    t = _ascii_lower(texto_cabecalho)
    if re.search(r"sem\s+copart", t):
        return "sem", None, "Sem coparticipação"
    match = _RE_PCT_COPART.search(texto_cabecalho)
    if match:
        return "percentual", int(match.group(1)), f"Coparticipação {match.group(1)}%"
    if re.search(r"com\s+copart", t) and not re.search(r"sem\s+copart", t):
        pct = 30
        m2 = re.search(r"(\d{1,2})\s*%", texto_cabecalho)
        if m2:
            pct = int(m2.group(1))
        return "percentual", pct, f"Coparticipação {pct}%"
    if "coparticip" in t and "sem" not in t and "valores apresentados com" not in t:
        return "ambíguo", None, "Regime de coparticipação ambíguo"
    return "a_confirmar", None, "A confirmar"


def _regime_da_pagina(linhas_topo: list[str]) -> tuple[str, int | None, str]:
    bloco = "\n".join(linhas_topo[:12])
    return classificar_regime_cabecalho(bloco)


def _parear_linhas_plano(
    linhas_ordenadas: list[tuple[float, list[tuple[float, float, float, float, str]]]],
    header_y: float,
    header_ws: list[tuple[float, float, float, float, str]] | None,
    pagina: int,
) -> tuple[list[LinhaPlanoExtraida], int]:
    """Retorna (linhas montadas, candidatas tarifárias detectadas com ≥10 valores)."""
    resultado: list[LinhaPlanoExtraida] = []
    vistos: set[tuple[str, tuple[int, ...]]] = set()
    items = [(y, ws) for y, ws in linhas_ordenadas if y > header_y]
    acomodacao = ""
    x_limite = _x_limite_nome_colunas(header_ws) if header_ws else None
    candidatas = 0

    for idx, (y, ws) in enumerate(items):
        texto = _texto_linha(ws)
        if _eh_secao_acomodacao(texto):
            acomodacao = texto.strip().title()
            continue
        if _linha_cabecalho_faixas(texto):
            continue

        if x_limite is not None:
            nome = _nome_coluna_plano(ws, x_limite)
            vals = _valores_coluna_preco(ws, x_limite)
            trecho = texto[:240]
        else:
            vals = _valores_monetarios(texto)
            nome = _nome_plano_de_texto(texto, vals)
            trecho = texto[:240]

            if 8 <= len(vals) < 10 and idx + 1 < len(items):
                _, ws_next = items[idx + 1]
                vals = (vals + _valores_monetarios(_texto_linha(ws_next)))[:10]

            if len(vals) >= 10:
                vals = vals[:10]
                if not _eh_nome_plano_valido(nome):
                    if idx + 1 < len(items):
                        _, ws_next = items[idx + 1]
                        candidato = _texto_linha(ws_next).strip()
                        if _eh_nome_plano_valido(candidato) and len(_valores_monetarios(candidato)) < 10:
                            nome = candidato
                            trecho = f"{_texto_linha(ws)} | {candidato}"
                    if not _eh_nome_plano_valido(nome) and idx > 0:
                        _, ws_prev = items[idx - 1]
                        candidato = _texto_linha(ws_prev).strip()
                        if _eh_nome_plano_valido(candidato) and len(_valores_monetarios(candidato)) < 10:
                            nome = candidato
                            trecho = f"{candidato} | {_texto_linha(ws)}"
            elif len(vals) < 10:
                if _eh_nome_plano_valido(texto):
                    prox_vals: list[int] = []
                    prox_ws = None
                    if idx + 1 < len(items):
                        _, prox_ws = items[idx + 1]
                        prox_vals = _valores_monetarios(_texto_linha(prox_ws))
                    if len(prox_vals) >= 10:
                        vals = prox_vals[:10]
                        nome = texto.strip()
                        ws = prox_ws or ws
                        trecho = f"{nome} | {_texto_linha(ws)}"
                    else:
                        continue
                else:
                    continue

        if len(vals) < 10:
            continue

        candidatas += 1
        nome = normalizar_espacos(nome.upper().replace("  ", " ")).strip()
        if not _eh_nome_plano_valido(nome):
            continue

        if acomodacao and acomodacao.lower() not in nome.lower() and not re.search(r"\b[EQ]\b", nome):
            if "Apartamento" in acomodacao or "Enfermaria" in acomodacao:
                nome = f"{nome} {acomodacao}"

        chave = (nome, tuple(vals))
        if chave in vistos:
            continue
        vistos.add(chave)

        resultado.append(
            LinhaPlanoExtraida(
                plano_nome=nome,
                valores=vals,
                pagina=pagina + 1,
                trecho=trecho,
                coordenadas=_coordenadas_linha(ws),
            )
        )
    return resultado, candidatas


def extrair_tabelas_pagina(
    doc: PdfDocumento,
    pagina: int,
    *,
    codigo_plano_filtro: str | None = None,
) -> SecaoTabelaPagina | None:
    rows = palavras_por_linha(doc, pagina)
    if not rows:
        return None

    linhas_ordenadas = sorted(rows.items())
    linhas_topo = [_texto_linha(ws) for _, ws in linhas_ordenadas[:15]]
    regime_tipo, copart_pct, regime_rotulo = _regime_da_pagina(linhas_topo)

    header_y: float | None = None
    header_ws: list[tuple[float, float, float, float, str]] | None = None
    cabecalho_faixas = ""
    for y, ws in linhas_ordenadas:
        texto = _texto_linha(ws)
        if _linha_cabecalho_faixas(texto):
            header_y = y
            header_ws = ws
            cabecalho_faixas = texto
            break

    if header_y is None:
        return None

    linhas_extraidas, candidatas = _parear_linhas_plano(
        linhas_ordenadas, header_y, header_ws, pagina
    )
    if codigo_plano_filtro:
        base = codigo_plano_filtro.split()[0].upper()
        filtradas = [ln for ln in linhas_extraidas if base in ln.plano_nome.upper()]
        if filtradas:
            linhas_extraidas = filtradas

    if not linhas_extraidas and candidatas == 0:
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


def localizar_paginas_tabela_geral(doc: PdfDocumento) -> list[int]:
    indices: list[int] = []
    for pagina in range(doc.numero_paginas):
        texto, _ = texto_pagina_enriquecido(doc, pagina)
        t = _ascii_lower(texto)
        if "tabela geral de premios" in t or "tabela geral de prêmios" in t:
            indices.append(pagina)
    return indices


def localizar_paginas_tabela_sulamerica(doc: PdfDocumento) -> list[int]:
    indices: list[int] = []
    for pagina in range(doc.numero_paginas):
        texto, _ = texto_pagina_enriquecido(doc, pagina)
        tl = _ascii_lower(texto)
        rows = palavras_por_linha(doc, pagina)
        tem_cabecalho_faixas = any(
            _linha_cabecalho_faixas(_texto_linha(ws)) for ws in rows.values()
        )
        if not tem_cabecalho_faixas:
            continue
        if (
            "tabela de precos" in tl
            or "tabela de preços" in texto.lower()
            or "sem copart" in tl
            or re.search(r"\d{1,2}\s*%\s*de\s+copart", texto, re.IGNORECASE)
        ):
            indices.append(pagina)
    return indices


def extrair_quantidades_faixa_porto(
    doc: PdfDocumento,
    codigo: str,
) -> dict[int, tuple[int, str]]:
    """Lê «Cotação por faixa etária»: rótulo da faixa e quantidade (às vezes na linha seguinte)."""
    resultado: dict[int, tuple[int, str]] = {}
    codigo_norm = re.sub(r"\s+", " ", codigo.upper()).strip()
    codigo_base = codigo_norm.split()[0] if codigo_norm else ""

    def _qtd_da_linha_faixa(linha: str, proxima: str | None) -> tuple[int | None, str]:
        # Remove limites etários («19 a 23», «59+», «anos») — sobram só quantidades.
        resto = re.sub(
            r"\d{1,2}\s*[-–a]\s*\d{1,2}|\d{2}\s*\+|\banos?\b",
            " ",
            linha,
            flags=re.IGNORECASE,
        )
        nums = [int(n) for n in re.findall(r"\b(\d+)\b", resto) if 0 < int(n) <= 99]
        if nums:
            return nums[-1], linha.strip()
        if proxima is not None:
            m = re.fullmatch(r"\s*(\d{1,2})\s*", proxima)
            if m:
                q = int(m.group(1))
                if 0 < q <= 99:
                    return q, f"{linha.strip()} | qtd={proxima.strip()}"
        return None, linha.strip()

    melhores: list[tuple[int, dict[int, tuple[int, str]]]] = []
    for pagina in range(doc.numero_paginas - 1, max(-1, doc.numero_paginas - 10), -1):
        texto, _ = texto_pagina_enriquecido(doc, pagina)
        tl = _ascii_lower(texto)
        if "faixa et" not in tl and "distribui" not in tl and "cotacao por faixa" not in tl:
            continue
        tu = texto.upper()
        if codigo_base and codigo_base not in tu and "TOTAL" not in tu:
            continue
        parcial: dict[int, tuple[int, str]] = {}
        linhas = texto.splitlines()
        for i, linha in enumerate(linhas):
            faixa = faixa_de_rotulo(linha)
            if faixa is None:
                continue
            prox = linhas[i + 1] if i + 1 < len(linhas) else None
            qtd, trecho = _qtd_da_linha_faixa(linha, prox)
            if qtd is not None:
                parcial[faixa] = (qtd, trecho)
        if not parcial:
            continue
        score = 0
        if codigo_norm and codigo_norm in re.sub(r"\s+", " ", tu):
            score += 5
        elif codigo_base and codigo_base in tu:
            score += 2
        score += min(len(parcial), 5)
        melhores.append((score, parcial))

    if not melhores:
        return resultado
    melhores.sort(key=lambda x: -x[0])
    return melhores[0][1]
