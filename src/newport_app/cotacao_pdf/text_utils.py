"""Utilitários de texto para parsers PDF."""

from __future__ import annotations

import re
from datetime import date, datetime

from newport_app.siscor_importer.money import valor_para_centavos

# Ordem importa: milhar com ponto antes de \d+,\d{2} (senão 1.073,96 vira 073,96).
_RE_VALOR_BR = (
    r"(?:"
    r"\d{1,3}(?:\.\d{3})+,\d{2}"  # 1.073,96 / 12.345,67
    r"|\d{1,3}(?:\.\d{3})+\.\d{2}"  # 1.073.96 (ponto decimal atípico)
    r"|\d+,\d{2}"  # 1073,96 / 73,96
    r"|\d+\.\d{2}"  # 1073.96 / 73.96
    r")"
)
_RE_DINHEIRO = re.compile(rf"R\$\s*({_RE_VALOR_BR})", re.IGNORECASE)
_RE_DINHEIRO_SOLTO = re.compile(rf"(?<![\d.])({_RE_VALOR_BR})(?!\d)")
_RE_DINHEIRO_TOKEN = re.compile(rf"^R?\$?\s*({_RE_VALOR_BR})$", re.IGNORECASE)
_RE_DECIMAL = re.compile(rf"({_RE_VALOR_BR})")
_RE_DATA = re.compile(r"(\d{2}/\d{2}/\d{4})")
_RE_PLANO_PORTO = re.compile(r"(P\d{3}\s*[QE])", re.IGNORECASE)


def normalizar_espacos(texto: str) -> str:
    return re.sub(r"\s+", " ", texto.replace("\u00a0", " ")).strip()


def extrair_datas(texto: str) -> list[date]:
    datas: list[date] = []
    for match in _RE_DATA.finditer(texto):
        try:
            datas.append(datetime.strptime(match.group(1), "%d/%m/%Y").date())
        except ValueError:
            continue
    return datas


def _centavos_de_bruto(bruto: str) -> int | None:
    """Converte string monetária BR/US sem perda de dígitos de milhar."""
    t = bruto.strip().replace("\u00a0", "").replace(" ", "")
    if not t:
        return None
    if "," in t:
        # 1.073,96 ou 1073,96
        return valor_para_centavos(t)
    if t.count(".") >= 2:
        partes = t.split(".")
        if len(partes[-1]) == 2 and all(p.isdigit() for p in partes):
            inteiro = "".join(partes[:-1])
            return valor_para_centavos(f"{inteiro},{partes[-1]}")
        return None
    if t.count(".") == 1:
        a, b = t.split(".")
        if a.isdigit() and b.isdigit() and len(b) == 2:
            return valor_para_centavos(f"{a},{b}")
    return valor_para_centavos(t)


def extrair_valores_reais(texto: str) -> list[int]:
    centavos: list[int] = []
    vistos: set[tuple[int, int]] = set()
    for regex in (_RE_DINHEIRO, _RE_DINHEIRO_SOLTO):
        for match in regex.finditer(texto):
            span = match.span(1)
            if span in vistos:
                continue
            v = _centavos_de_bruto(match.group(1))
            if v is not None:
                vistos.add(span)
                centavos.append(v)
    return centavos


def extrair_valor_token(token: str) -> int | None:
    """Extrai um valor de um token PyMuPDF (ex.: «R$1073,96»)."""
    m = _RE_DINHEIRO_TOKEN.match(token.strip())
    if not m:
        return None
    return _centavos_de_bruto(m.group(1))


def extrair_primeiro_reais(texto: str) -> int | None:
    valores = extrair_valores_reais(texto)
    return valores[0] if valores else None


def extrair_decimais(texto: str) -> list[int]:
    centavos: list[int] = []
    for match in _RE_DECIMAL.finditer(texto):
        bruto = match.group(1)
        if "," in bruto:
            v = valor_para_centavos(bruto)
        else:
            v = valor_para_centavos(bruto.replace(".", ","))
        if v is not None:
            centavos.append(v)
    return centavos


def linha_contem_plano_porto(linha: str, codigo_plano: str) -> bool:
    return codigo_plano.upper() in linha.upper()


def valor_de_celula(texto: str | None) -> int | None:
    if not texto:
        return None
    bruto = str(texto).strip()
    valor = extrair_primeiro_reais(bruto)
    if valor is not None:
        return valor
    from newport_app.siscor_importer.money import valor_para_centavos

    return valor_para_centavos(bruto.replace("R$", "").strip())


def extrair_percentual(texto: str) -> float | None:
    match = re.search(r"(\d{1,2}(?:,\d+)?)\s*%", texto)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None
