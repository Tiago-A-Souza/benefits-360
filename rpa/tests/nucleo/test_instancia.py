"""Portas 8600/8601, recusa de config no lugar errado e instância única."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from nucleo.instancia import (
    MENSAGEM_REAL_NO_TREINO,
    MENSAGEM_TREINO_NA_REAL,
    OcupadoErro,
    TravaPorta,
    mensagem_porta_config,
)


def test_config_simulador_recusada_na_porta_real():
    msg = mensagem_porta_config("config_simulador.yaml", 8600)
    assert msg == MENSAGEM_TREINO_NA_REAL
    assert "porta 8601" in msg and "config.yaml" in msg


def test_config_real_recusada_na_porta_treino():
    msg = mensagem_porta_config("config.yaml", 8601)
    assert msg == MENSAGEM_REAL_NO_TREINO
    assert "porta 8600" in msg and "config_simulador.yaml" in msg


def test_casamento_certo_e_nomes_desconhecidos_passam(tmp_path):
    assert mensagem_porta_config("config.yaml", 8600) is None
    assert mensagem_porta_config("config_simulador.yaml", 8601) is None
    assert mensagem_porta_config(tmp_path / "outro.yaml", 8600) is None
    assert mensagem_porta_config("CONFIG_SIMULADOR.YAML", 8600) == MENSAGEM_TREINO_NA_REAL


def test_main_recusa_treino_na_8600(tmp_path, capsys):
    cfg = tmp_path / "config_simulador.yaml"
    cfg.write_text("geral:\n  pasta_saida: saida\ntela:\n  porta: 8601\n", encoding="utf-8")
    from app.__main__ import main

    assert main(["--config", str(cfg), "--porta", "8600", "--sem-navegador"]) == 2
    saida = capsys.readouterr().out
    assert "modo TREINO" in saida
    assert "8601" in saida


def test_main_recusa_real_na_8601(tmp_path, capsys):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("geral:\n  pasta_saida: saida\ntela:\n  porta: 8600\n", encoding="utf-8")
    from app.__main__ import main

    assert main(["--config", str(cfg), "--porta", "8601", "--sem-navegador"]) == 2
    saida = capsys.readouterr().out
    assert "robô REAL" in saida
    assert "8600" in saida


def test_segunda_trava_na_mesma_porta_nao_derruba_a_primeira(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWPORT_TRAVA_PASTA", str(tmp_path))
    with TravaPorta(18600):
        with pytest.raises(OcupadoErro, match="Já existe um robô nesta porta"):
            with TravaPorta(18600):
                pass
        assert (tmp_path / "porta-18600.lock").is_file()


def test_portas_diferentes_podem_conviver(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWPORT_TRAVA_PASTA", str(tmp_path))
    with TravaPorta(18601), TravaPorta(18602):
        pass


def test_main_segunda_instancia_sai_sem_subir(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("NEWPORT_TRAVA_PASTA", str(tmp_path))
    cfg = tmp_path / "config.yaml"
    cfg.write_text("geral:\n  pasta_saida: saida\ntela:\n  porta: 18603\n", encoding="utf-8")
    from app.__main__ import main

    with TravaPorta(18603):
        codigo = main(["--config", str(cfg), "--porta", "18603", "--sem-navegador"])
    assert codigo in (0, 1)
    assert "Já existe um robô" in capsys.readouterr().out


def test_pasta_saida_e_absoluta(tmp_path):
    from nucleo.registro import pasta_saida

    p = pasta_saida({"geral": {"pasta_saida": "saida"}, "_pasta_config": str(tmp_path)})
    assert p.is_absolute()
    assert p == (tmp_path / "saida").absolute()


def test_estado_traz_pasta_absoluta_e_modo(tmp_path, monkeypatch):
    import asyncio
    import json

    import operadoras
    from starlette.requests import Request

    from app.servidor import Tela

    def carregar(*itens):
        operadoras._carregar(list(itens))

    carregar(("falsa", "Operadora Falsa", "tests.nucleo.operadora_falsa", "OperadoraFalsa"))
    try:
        linhas = (
            "geral:\n  pasta_saida: saida\nteste:\n  cofre: memoria\n  simulador: true\n"
            "operadoras:\n  falsa: {}\n"
        )
        cfg = tmp_path / "config.yaml"
        cfg.write_text(linhas, encoding="utf-8")
        tela = Tela(cfg, 0)
        pedido = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""})
        estado = json.loads(asyncio.run(tela.estado(pedido)).body)
        assert Path(estado["pasta_saida"]).is_absolute()
        assert estado["simulador"] is True
        assert estado["modo"] == "treino"
        geral = json.loads(asyncio.run(tela.ler_geral(pedido)).body)
        assert Path(geral["pasta_saida"]).is_absolute()
        assert geral["simulador"] is True
    finally:
        operadoras._carregar()


def test_backup_diario_nao_apaga_origem(tmp_path):
    import importlib.util

    origem = tmp_path / "saida"
    origem.mkdir()
    db = origem / "tela.db"
    con = sqlite3.connect(str(db))
    con.execute("create table t(x int)")
    con.execute("insert into t values (1)")
    con.commit()
    con.close()
    dest = tmp_path / "backups"
    spec = importlib.util.spec_from_file_location(
        "backup_historico",
        Path(__file__).resolve().parents[2] / "scripts" / "backup_historico.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    copiado = mod.backup_diario(db, dest, retencao_dias=14)
    assert copiado.is_file()
    assert db.is_file()
    lido = sqlite3.connect(str(copiado))
    assert lido.execute("select x from t").fetchone()[0] == 1
    lido.close()
    velho = dest / "2000-01-01.sqlite"
    velho.write_bytes(b"x")
    import os
    from datetime import datetime

    os.utime(velho, (0, 0))
    mod.backup_diario(db, dest, retencao_dias=14, hoje=datetime.now().date())
    assert not velho.exists()
    assert db.is_file()


def test_tee_isatty_e_fileno_nao_quebram_o_uvicorn(tmp_path):
    """--log espelha stdout; o formatter do uvicorn chama isatty() no stream."""
    import sys

    from app.__main__ import _Tee, _ligar_log
    from uvicorn.config import Config

    log = tmp_path / "robo.log"
    antigo_out, antigo_err = sys.stdout, sys.stderr
    try:
        _ligar_log(str(log))
        assert isinstance(sys.stdout, _Tee)
        assert isinstance(sys.stdout.isatty(), bool)
        assert sys.stdout.fileno() == sys.__stdout__.fileno()
        Config(app="app.servidor:Tela", log_level="warning").configure_logging()
        print("tee-ok")
    finally:
        sys.stdout, sys.stderr = antigo_out, antigo_err
    assert "tee-ok" in log.read_text(encoding="utf-8")
