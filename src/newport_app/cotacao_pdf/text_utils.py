"""Utilitários de texto para parsers PDF."""

from __future__ import annotations

import re
from datetime import date, datetime

from newport_app.siscor_importer.money import valor_para_centavos

_RE_DINHEIRO = re.compile(
    r"R\$\s*([\d]{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})",
    re.IGNORECASE,
)
_RE_DINHEIRO_SOLTO = re.compile(
    r"(?<!\d)([\d]{1,3}(?:\.\d{3})*,\d{2})(?!\d)",
)
_RE_DECIMAL = re.compile(r"([\d]{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})")
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


def extrair_valores_reais(texto: str) -> list[int]:
    centavos: list[int] = []
    for match in _RE_DINHEIRO.finditer(texto):
        v = valor_para_centavos(match.group(1))
        if v is not None:
            centavos.append(v)
    return centavos


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
