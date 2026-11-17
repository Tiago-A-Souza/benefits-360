"""Funções de texto: normalização, regex sem acento, dinheiro e CNPJ.

O portal mistura textos com e sem acento ("Cotacao enviada com sucesso!" aparece
sem acento; "COTAÇÃO EMITIDA COM SUCESSO!" com acento). Por isso todo texto
procurado na tela passa por `rx()`, que aceita as duas formas.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP

_VARIANTES = {
    "a": "aáàâãä",
    "e": "eéèêë",
    "i": "iíìîï",
    "o": "oóòôõö",
    "u": "uúùûü",
    "c": "cç",
    "n": "nñ",
}


def sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", str(texto))
    return "".join(ch for ch in decomposto if not unicodedata.combining(ch))


def norm(texto: str | None) -> str:
    """Minúsculas, sem acento, espaços colapsados. Para comparar nomes."""
    if texto is None:
        return ""
    return re.sub(r"\s+", " ", sem_acento(texto).lower()).strip()


def rx(texto: str, exato: bool = False) -> re.Pattern:
    """Regex que casa `texto` ignorando acento, maiúsculas e espaços extras.

    exato=True ancora no começo e no fim (o elemento inteiro tem só esse texto).
    """
    partes = []
    for ch in sem_acento(texto).lower():
        if ch.isspace():
            if not partes or partes[-1] != r"\s+":
                partes.append(r"\s+")
        elif ch in _VARIANTES:
            partes.append(f"[{_VARIANTES[ch]}]")
        else:
            partes.append(re.escape(ch))
    corpo = "".join(partes)
    if exato:
        corpo = rf"^\s*{corpo}\s*$"
    return re.compile(corpo, re.IGNORECASE)


_DINHEIRO = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?")


def dinheiro(texto: str) -> Decimal | None:
    """'R$ 1.144,03' -> Decimal('1144.03'); 'R$ 0' -> Decimal('0.00'). None se não achar."""
    m = _DINHEIRO.search(str(texto))
    if not m:
        return None
    inteiro = m.group(1).replace(".", "")
    centavos = (m.group(2) or "0").ljust(2, "0")
    return Decimal(f"{inteiro}.{centavos}")


def todos_dinheiros(texto: str) -> list[Decimal]:
    valores = []
    for m in _DINHEIRO.finditer(str(texto)):
        inteiro = m.group(1).replace(".", "")
        centavos = (m.group(2) or "0").ljust(2, "0")
        valores.append(Decimal(f"{inteiro}.{centavos}"))
    return valores


def reais(valor: Decimal | None) -> str:
    if valor is None:
        return ""
    q = valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    inteiro, dec = f"{q:.2f}".split(".")
    inteiro_fmt = f"{int(inteiro):,}".replace(",", ".")
    return f"R$ {inteiro_fmt},{dec}"


def so_digitos(texto) -> str:
    return "".join(ch for ch in str(texto or "") if ch.isdigit())


def cnpj_valido(cnpj: str) -> bool:
    d = so_digitos(cnpj)
    if len(d) != 14 or len(set(d)) == 1:
        return False

    def digito(base: str, pesos: list[int]) -> str:
        soma = sum(int(n) * p for n, p in zip(base, pesos))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    p2 = [6] + p1
    d1 = digito(d[:12], p1)
    d2 = digito(d[:12] + d1, p2)
    return d[12:] == d1 + d2


def formatar_cnpj(cnpj: str) -> str:
    d = so_digitos(cnpj)
    if len(d) != 14:
        return str(cnpj)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def nome_arquivo_seguro(nome: str) -> str:
    """Remove caracteres proibidos em nomes de arquivo do Windows."""
    limpo = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", nome)
    return re.sub(r"\s+", " ", limpo).strip().rstrip(".")
