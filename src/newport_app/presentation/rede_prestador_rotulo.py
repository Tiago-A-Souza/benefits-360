"""Rótulo de prestador na aba Rede — bairro inline e corte de sufixo repetido."""

from __future__ import annotations

import html
import unicodedata

_SEPARADORES_SUFIXO = " \t-–—/"

# Não encurtar se o que sobrar ficar vazio ou insignificante.
_MIN_CARACTERES_RESTO = 3


def _fold(texto: str) -> str:
    bruto = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in bruto if not unicodedata.combining(c))
    return sem_acento.casefold()


def recortar_bairro_do_nome(prestador: str, bairro: str) -> str:
    """Remove sufixo do nome quando coincide com o bairro (fold, sufixo exato)."""
    p = (prestador or "").strip()
    b = (bairro or "").strip()
    if not p or not b:
        return p
    bf = _fold(b)
    if not bf or not _fold(p).endswith(bf):
        return p

    melhor: str | None = None
    for i in range(len(p)):
        cauda = p[i:].lstrip(_SEPARADORES_SUFIXO)
        if _fold(cauda) != bf:
            continue
        cand = p[:i].rstrip(_SEPARADORES_SUFIXO)
        if len(cand.strip()) < _MIN_CARACTERES_RESTO:
            continue
        melhor = cand
    return melhor if melhor is not None else p


def nome_prestador_para_rotulo(prestador: str, bairro: str) -> str:
    """Nome exibido antes do span de bairro — recorta sufixo real ou implícito."""
    p = (prestador or "").strip()
    b = (bairro or "").strip()
    if not p or not b:
        return p
    curto = recortar_bairro_do_nome(p, b)
    if _fold(curto) != _fold(p):
        return curto
    # Matriz SiscorNet: coluna Prestador costuma vir sem o bairro; o par completo
    # é prestador + bairro. Simula só para recortar repetição, não altera a base.
    virtual = f"{p} {b}"
    if _fold(virtual).endswith(_fold(b)):
        recortado = recortar_bairro_do_nome(virtual, b)
        if _fold(recortado) != _fold(virtual):
            return recortado
    return p


def rotulo_prestador_html(
    prestador: str,
    bairro: str,
    *,
    prefixo_zona: str = "",
) -> str:
    nome = (prestador or "").strip()
    if prefixo_zona:
        nome = f"{prefixo_zona} {nome}".strip()
    b = (bairro or "").strip()
    if b:
        nome = nome_prestador_para_rotulo(nome, b)
        return (
            f"{html.escape(nome)}"
            f"<span class='bairro-rede'>{html.escape(b)}</span>"
        )
    return html.escape(nome)
