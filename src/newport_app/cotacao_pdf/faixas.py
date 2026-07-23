"""Mapeamento de rótulos de faixa etária para índices 0–9."""

from __future__ import annotations

import re

_FAIXAS: list[tuple[int, tuple[str, ...]]] = [
    (0, (r"0\s*[-a]\s*18", r"00-18", r"at[eé]\s*18", r"até\s*18")),
    (1, (r"19\s*[-a]\s*23",)),
    (2, (r"24\s*[-a]\s*28",)),
    (3, (r"29\s*[-a]\s*33",)),
    (4, (r"34\s*[-a]\s*38",)),
    (5, (r"39\s*[-a]\s*43",)),
    (6, (r"44\s*[-a]\s*48",)),
    (7, (r"49\s*[-a]\s*53",)),
    (8, (r"54\s*[-a]\s*58",)),
    (9, (r"59\s*\+?", r"59\s*ou", r"59\s*adiante", r"\+59", r"59\+")),
]

ROTULOS_FAIXA = [
    "0 a 18",
    "19 a 23",
    "24 a 28",
    "29 a 33",
    "34 a 38",
    "39 a 43",
    "44 a 48",
    "49 a 53",
    "54 a 58",
    "59+",
]


def faixa_de_rotulo(texto: str) -> int | None:
    bruto = texto.strip().lower()
    if not bruto:
        return None
    for idx, padroes in _FAIXAS:
        for padrao in padroes:
            if re.search(padrao, bruto, re.IGNORECASE):
                return idx
    return None


def cabecalhos_faixa_em_texto(texto: str) -> list[tuple[int, str]]:
    encontrados: list[tuple[int, str]] = []
    for rotulo in ROTULOS_FAIXA:
        idx = faixa_de_rotulo(rotulo)
        if idx is not None and rotulo.split()[0] in texto:
            encontrados.append((idx, rotulo))
    return sorted(encontrados, key=lambda x: x[0])
