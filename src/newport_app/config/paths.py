"""Caminhos de dados — demos vs runtime privado."""

from __future__ import annotations

import os
from pathlib import Path

from newport_app.config.runtime import ModoExecucao, modo_execucao

ROOT = Path(__file__).resolve().parents[3]


def diretorio_dados_demo() -> Path:
    return Path(os.environ.get("NEWPORT_DATA_DIR", ROOT / ".data"))


def diretorio_runtime_privado() -> Path:
    return Path(os.environ.get("NEWPORT_PRIVATE_RUNTIME", ROOT / ".private" / "runtime"))


def caminho_banco_estudos(modo: ModoExecucao | None = None) -> Path:
    if (modo or modo_execucao()) == ModoExecucao.REAL:
        return diretorio_runtime_privado() / "estudos.db"
    return diretorio_dados_demo() / "newport_app.db"


def caminho_banco_importacoes(modo: ModoExecucao | None = None) -> Path:
    if (modo or modo_execucao()) == ModoExecucao.REAL:
        return diretorio_runtime_privado() / "importacoes.db"
    return diretorio_dados_demo() / "importacoes_demo.db"


def diretorio_uploads(modo: ModoExecucao | None = None) -> Path:
    if (modo or modo_execucao()) == ModoExecucao.REAL:
        return diretorio_runtime_privado() / "uploads"
    return diretorio_dados_demo() / "uploads_demo"


def garantir_diretorios(modo: ModoExecucao | None = None) -> None:
    diretorio_dados_demo().mkdir(parents=True, exist_ok=True)
    diretorio_runtime_privado().mkdir(parents=True, exist_ok=True)
    caminho_banco_estudos(modo).parent.mkdir(parents=True, exist_ok=True)
    diretorio_uploads(modo).mkdir(parents=True, exist_ok=True)
