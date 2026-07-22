"""Caminhos de dados — demos vs runtime privado."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def diretorio_dados_demo() -> Path:
    return Path(os.environ.get("NEWPORT_DATA_DIR", ROOT / ".data"))


def diretorio_runtime_privado() -> Path:
    return Path(os.environ.get("NEWPORT_PRIVATE_RUNTIME", ROOT / ".private" / "runtime"))


def garantir_diretorios() -> None:
    diretorio_dados_demo().mkdir(parents=True, exist_ok=True)
    diretorio_runtime_privado().mkdir(parents=True, exist_ok=True)
    (diretorio_runtime_privado() / "uploads").mkdir(parents=True, exist_ok=True)
