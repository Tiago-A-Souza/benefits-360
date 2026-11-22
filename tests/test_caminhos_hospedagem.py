"""Caminhos graváveis e catálogos apontam para o volume por variável de ambiente."""

from __future__ import annotations

from pathlib import Path

import pytest

from newport_app.config.paths import (
    arquivo_docs,
    caminho_banco_cotacoes,
    caminho_banco_estudos,
    caminho_banco_importacoes,
    diretorio_dados_demo,
    diretorio_docs,
    diretorio_entregaveis,
    diretorio_runtime_privado,
    diretorio_uploads,
    diretorio_uploads_cotacao,
)
from newport_app.config.runtime import ModoExecucao


@pytest.fixture
def sem_env_caminhos(monkeypatch):
    for chave in (
        "NEWPORT_DATA_DIR",
        "NEWPORT_PRIVATE_RUNTIME",
        "NEWPORT_VOLUME_DIR",
        "NEWPORT_DOCS_DIR",
        "NEWPORT_REDE_XLSX",
    ):
        monkeypatch.delenv(chave, raising=False)


def test_sem_env_mantem_padroes_do_repo(sem_env_caminhos):
    root = Path(__file__).resolve().parents[1]
    assert diretorio_dados_demo() == root / ".data"
    assert diretorio_runtime_privado() == root / ".private" / "runtime"
    assert diretorio_docs() == root / "docs"
    assert arquivo_docs("regras_comerciais_base.csv").name == "regras_comerciais_base.csv"


def test_volume_substitui_runtime_real(monkeypatch, tmp_path: Path):
    vol = tmp_path / "data"
    monkeypatch.setenv("NEWPORT_VOLUME_DIR", str(vol))
    monkeypatch.delenv("NEWPORT_PRIVATE_RUNTIME", raising=False)
    assert diretorio_runtime_privado() == vol
    assert caminho_banco_estudos(ModoExecucao.REAL) == vol / "estudos.db"
    assert caminho_banco_importacoes(ModoExecucao.REAL) == vol / "importacoes.db"
    assert caminho_banco_cotacoes(ModoExecucao.REAL) == vol / "cotacoes.db"
    assert diretorio_uploads(ModoExecucao.REAL) == vol / "uploads"
    assert diretorio_uploads_cotacao(ModoExecucao.REAL) == vol / "cotacoes"
    assert diretorio_entregaveis(ModoExecucao.REAL) == vol / "entregaveis"


def test_private_runtime_vence_volume(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NEWPORT_VOLUME_DIR", str(tmp_path / "vol"))
    monkeypatch.setenv("NEWPORT_PRIVATE_RUNTIME", str(tmp_path / "priv"))
    assert diretorio_runtime_privado() == tmp_path / "priv"


def test_data_dir_so_afeta_demo(sem_env_caminhos, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NEWPORT_DATA_DIR", str(tmp_path / "demo"))
    monkeypatch.delenv("NEWPORT_VOLUME_DIR", raising=False)
    monkeypatch.delenv("NEWPORT_PRIVATE_RUNTIME", raising=False)
    assert diretorio_dados_demo() == tmp_path / "demo"
    assert caminho_banco_estudos(ModoExecucao.DEMO) == tmp_path / "demo" / "newport_app.db"
    root = Path(__file__).resolve().parents[1]
    assert caminho_banco_estudos(ModoExecucao.REAL) == root / ".private" / "runtime" / "estudos.db"


def test_docs_dir_desvia_catalogos(monkeypatch, tmp_path: Path):
    docs = tmp_path / "catalogos"
    docs.mkdir()
    monkeypatch.setenv("NEWPORT_DOCS_DIR", str(docs))
    assert arquivo_docs("hospitais_principais_base.csv") == docs / "hospitais_principais_base.csv"
    assert arquivo_docs("laboratorios_principais_base.csv").parent == docs
