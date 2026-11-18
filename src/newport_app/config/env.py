"""Carrega .env.local / .env da raiz sem sobrescrever o ambiente já definido."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_carregado = False


def carregar_env_local() -> None:
    global _carregado
    if _carregado:
        return
    _carregado = True
    for nome in (".env.local", ".env"):
        caminho = ROOT / nome
        if not caminho.is_file():
            continue
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            texto = linha.strip()
            if not texto or texto.startswith("#") or "=" not in texto:
                continue
            chave, _, valor = texto.partition("=")
            chave = chave.strip()
            if not chave or chave in os.environ:
                continue
            os.environ[chave] = valor.strip().strip('"').strip("'")
