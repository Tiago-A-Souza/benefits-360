"""Backup SQLite (API oficial) + restauração das pastas."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from newport_app.backup import (
    copiar_sqlite_seguro,
    executar_backup,
    limpar_antigos,
    restaurar,
)
from newport_app.config.runtime import ModoExecucao


def _banco(path: Path, marca: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("DROP TABLE IF EXISTS t")
        conn.execute("CREATE TABLE t (id INTEGER, nota TEXT)")
        conn.execute("INSERT INTO t VALUES (1, ?)", (marca,))
        conn.commit()
    finally:
        conn.close()


def _ler(path: Path) -> str:
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT nota FROM t WHERE id = 1").fetchone()[0]


def test_copia_sqlite_nao_e_copy_de_arquivo(tmp_path: Path):
    origem = tmp_path / "vivo.db"
    destino = tmp_path / "copia.db"
    _banco(origem, "ok")
    with sqlite3.connect(origem) as vivo:
        vivo.execute("INSERT INTO t VALUES (2, 'aberto')")
        vivo.commit()
        copiar_sqlite_seguro(origem, destino)
    assert _ler(destino) == "ok"
    with sqlite3.connect(destino) as conn:
        n = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    assert n == 2


def test_backup_e_restore_local(tmp_path: Path, monkeypatch):
    runtime = tmp_path / "runtime"
    backups = tmp_path / "backups"
    monkeypatch.setenv("NEWPORT_MODO", "real")
    monkeypatch.setenv("NEWPORT_PRIVATE_RUNTIME", str(runtime))
    monkeypatch.setenv("NEWPORT_BACKUP_DIR", str(backups))
    monkeypatch.setenv("NEWPORT_DATA_DIR", str(tmp_path / "demo"))

    _banco(runtime / "estudos.db", "cliente-a")
    _banco(runtime / "importacoes.db", "siscor")
    _banco(runtime / "cotacoes.db", "pdf")
    (runtime / "uploads").mkdir()
    (runtime / "uploads" / "posicao.xlsx").write_bytes(b"xlsx")
    (runtime / "cotacoes").mkdir()
    (runtime / "cotacoes" / "proposta.pdf").write_bytes(b"%PDF")
    (runtime / "entregaveis").mkdir()
    (runtime / "entregaveis" / "estudo.html").write_text("<p>ok</p>", encoding="utf-8")

    pasta = executar_backup(backups, agora=datetime(2026, 11, 19, tzinfo=timezone.utc))
    assert pasta.name == "2026-11-19"
    assert (pasta / "estudos.db").is_file()
    assert (pasta / "cotacoes" / "proposta.pdf").read_bytes() == b"%PDF"
    assert "estudos.db" in (pasta / "MANIFEST.txt").read_text(encoding="utf-8")

    _banco(runtime / "estudos.db", "estragado")
    (runtime / "cotacoes" / "proposta.pdf").unlink()
    (runtime / "entregaveis" / "estudo.html").write_text("perdido", encoding="utf-8")

    restaurar(pasta, runtime)
    assert _ler(runtime / "estudos.db") == "cliente-a"
    assert (runtime / "cotacoes" / "proposta.pdf").read_bytes() == b"%PDF"
    assert (runtime / "entregaveis" / "estudo.html").read_text(encoding="utf-8") == "<p>ok</p>"


def test_retencao_mantem_ultimos_n_dias(tmp_path: Path):
    raiz = tmp_path / "backups"
    for nome in ("2026-11-01", "2026-11-10", "2026-11-18", "2026-11-19"):
        (raiz / nome).mkdir(parents=True)
        (raiz / nome / "ok.txt").write_text("x", encoding="utf-8")
    hoje = datetime(2026, 11, 19, tzinfo=timezone.utc)
    removidos = limpar_antigos(raiz, 7, hoje=hoje)
    nomes = {p.name for p in removidos}
    assert nomes == {"2026-11-01", "2026-11-10"}
    assert (raiz / "2026-11-18").is_dir()
    assert (raiz / "2026-11-19").is_dir()


def test_backup_respeita_modo_dos_caminhos(tmp_path: Path, monkeypatch):
    demo = tmp_path / "demo"
    monkeypatch.setenv("NEWPORT_MODO", "demo")
    monkeypatch.setenv("NEWPORT_DATA_DIR", str(demo))
    monkeypatch.delenv("NEWPORT_BACKUP_DIR", raising=False)
    _banco(demo / "newport_app.db", "demo")
    pasta = executar_backup(modo=ModoExecucao.DEMO)
    assert pasta.parent == demo / "backups"
    assert _ler(pasta / "estudos.db") == "demo"
