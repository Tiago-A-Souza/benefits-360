"""Legenda dinâmica dos códigos de especialidade crus no documento de rede.

Os nomes NÃO ficam no código: vêm de `docs/codigos_rede_legenda.csv`
(`codigo;nome;confianca`). Só linhas com confiança «alta» são impressas — os
nomes são interpretação, não vêm da base, e o documento vai a um cliente
corporativo. Código fora do CSV aparece cru, sem entrada na legenda.

A legenda só cresce quando um código cru aparece de fato nas células.
"""

from __future__ import annotations

import csv
import threading
from collections.abc import Iterable
from pathlib import Path

from newport_app.config.paths import arquivo_docs
from newport_app.models.presentation import RedeApresentacaoDocumento

_LEGENDA_REPO = Path(__file__).resolve().parents[3] / "docs" / "codigos_rede_legenda.csv"
CAMINHO_LEGENDA = _LEGENDA_REPO

# Siglas que a legenda fixa do rodapé já explica.
SIGLAS_PADRAO = frozenset({"H", "HD", "M", "PS"})
CONFIANCA_IMPRESSA = "alta"

_LOCK = threading.Lock()
_CACHE: dict[Path, tuple[tuple[int, int], dict[str, str]]] = {}


def _assinatura(caminho: Path) -> tuple[int, int]:
    st = caminho.stat()
    return (st.st_mtime_ns, st.st_size)


def _ler(caminho: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with caminho.open(encoding="utf-8-sig", newline="") as fh:
        for linha in csv.DictReader(fh, delimiter=";", quotechar='"'):
            codigo = (linha.get("codigo") or "").strip().upper()
            nome = (linha.get("nome") or "").strip()
            confianca = (linha.get("confianca") or "").strip().lower()
            if codigo and nome and confianca == CONFIANCA_IMPRESSA:
                out[codigo] = nome
    return out


def carregar_legenda_codigos(caminho: Path | None = None) -> dict[str, str]:
    """Código → nome (só confiança alta). Arquivo ausente ou ilegível → vazio."""
    origem = caminho or CAMINHO_LEGENDA
    if origem == CAMINHO_LEGENDA:
        origem = arquivo_docs("codigos_rede_legenda.csv") if CAMINHO_LEGENDA == _LEGENDA_REPO else CAMINHO_LEGENDA
    try:
        chave = origem.resolve()
        assinatura = _assinatura(origem)
    except OSError:
        return {}
    with _LOCK:
        hit = _CACHE.get(chave)
        if hit is not None and hit[0] == assinatura:
            return hit[1]
        try:
            dados = _ler(origem)
        except (OSError, csv.Error, UnicodeDecodeError):
            return {}
        _CACHE[chave] = (assinatura, dados)
        return dados


def limpar_cache_legenda_codigos() -> None:
    with _LOCK:
        _CACHE.clear()


def _tokens(celula: str) -> Iterable[str]:
    return (t for t in (celula or "").replace("—", " ").split() if t)


def codigos_crus_no_documento(doc: RedeApresentacaoDocumento) -> list[str]:
    """Códigos que aparecem nas células e não são as quatro siglas padrão."""
    vistos: set[str] = set()
    for sec in doc.secoes:
        for bloco in sec.blocos:
            for ln in bloco.linhas:
                for val in ln.celulas.values():
                    for tok in _tokens(val):
                        if tok.upper() not in SIGLAS_PADRAO:
                            vistos.add(tok.upper())
    return sorted(vistos)


def itens_legenda_extra(
    doc: RedeApresentacaoDocumento,
    legenda: dict[str, str] | None = None,
) -> list[tuple[str, str]]:
    """(código, nome) dos crus presentes no documento que o CSV explica."""
    tabela = carregar_legenda_codigos() if legenda is None else legenda
    return [(c, tabela[c]) for c in codigos_crus_no_documento(doc) if c in tabela]
