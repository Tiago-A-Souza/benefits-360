"""Rótulo de prestador na aba Rede — bairro inline e corte de sufixo repetido."""

from __future__ import annotations

import html
import unicodedata


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
    if not _fold(p).endswith(_fold(b)):
        return p
    n = len(p)
    # Variação de separador e espaços antes do sufixo.
    for sep_len in range(0, 5):
        cut = n - len(b) - sep_len
        if cut <= 0:
            continue
        cand = p[:cut].rstrip(" \t-–—")
        resto = p[cut:].lstrip(" \t-–—")
        if _fold(resto) == _fold(b):
            return cand
    if _fold(p[-len(b) :]) == _fold(b):
        return p[: max(0, n - len(b))].rstrip(" \t-–—")
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
        nome = recortar_bairro_do_nome(nome, b)
        return (
            f"{html.escape(nome)}"
            f"<span class='bairro-rede'>{html.escape(b)}</span>"
        )
    return html.escape(nome)
