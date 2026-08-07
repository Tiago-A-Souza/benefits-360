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


def diretorio_uploads_cotacao(modo: ModoExecucao | None = None) -> Path:
    if (modo or modo_execucao()) == ModoExecucao.REAL:
        return diretorio_runtime_privado() / "cotacoes"
    return diretorio_dados_demo() / "cotacoes_demo"


def caminho_banco_cotacoes(modo: ModoExecucao | None = None) -> Path:
    if (modo or modo_execucao()) == ModoExecucao.REAL:
        return diretorio_runtime_privado() / "cotacoes.db"
    return diretorio_dados_demo() / "cotacoes_demo.db"


def diretorio_entregaveis(modo: ModoExecucao | None = None) -> Path:
    if (modo or modo_execucao()) == ModoExecucao.REAL:
        return diretorio_runtime_privado() / "entregaveis"
    return diretorio_dados_demo() / "entregaveis_demo"


def diretorio_dados(modo: ModoExecucao | None = None) -> Path:
    if (modo or modo_execucao()) == ModoExecucao.REAL:
        return diretorio_runtime_privado()
    return diretorio_dados_demo()


def caminho_diagnostico_jsonl(modo: ModoExecucao | None = None) -> Path:
    return diretorio_dados(modo) / "diagnostico.jsonl"


def diretorio_corpus_cotacoes() -> Path:
    """Corpus privado de cotações (PDFs reais — nunca versionados)."""
    env = os.environ.get("NEWPORT_CORPUS_COTACOES")
    if env:
        return Path(env)
    root = ROOT / ".private" / "corpus"
    for nome in ("cotacoes", "cotações", "cota\u00e7\u00f5es"):
        candidato = root / nome
        if candidato.is_dir():
            return candidato
    return root / "cotacoes"


def diretorio_corpus_anistia() -> Path:
    return diretorio_corpus_cotacoes()


def diretorio_golden_privado() -> Path:
    return diretorio_runtime_privado().parent / "golden"


def garantir_diretorios(modo: ModoExecucao | None = None) -> None:
    diretorio_dados_demo().mkdir(parents=True, exist_ok=True)
    diretorio_runtime_privado().mkdir(parents=True, exist_ok=True)
    caminho_banco_estudos(modo).parent.mkdir(parents=True, exist_ok=True)
    diretorio_uploads(modo).mkdir(parents=True, exist_ok=True)
    diretorio_uploads_cotacao(modo).mkdir(parents=True, exist_ok=True)
    diretorio_entregaveis(modo).mkdir(parents=True, exist_ok=True)
