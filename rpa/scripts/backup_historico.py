"""Cópia do histórico do robô. Não apaga rpa\\saida nem tela.db original.

Uso (só quando o corretor autorizar):
  python scripts/backup_historico.py --diario
  python scripts/backup_historico.py --semanal

Diário: API sqlite3.Connection.backup do tela.db → C:\\Backups\\rpa-tela\\YYYY-MM-DD.sqlite
        (retenção 14 dias só nessa pasta de backup).
Semanal: robocopy /E da pasta saida para C:\\Backups\\rpa-saida-semanal (não apaga o destino).
"""
from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
PADRAO_TELA = Path(r"C:\Backups\rpa-tela")
PADRAO_SEMANAL = Path(r"C:\Backups\rpa-saida-semanal")
RETENCAO = 14


def _ler_backup(config: Path) -> dict:
    dados = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    return dados.get("backup") or {}


def _pasta_saida(config: Path) -> Path:
    dados = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    pasta = Path((dados.get("geral") or {}).get("pasta_saida") or "saida")
    if not pasta.is_absolute():
        pasta = config.parent / pasta
    return pasta.resolve()


def backup_diario(tela_db: Path, destino: Path, retencao_dias: int = RETENCAO, hoje: date | None = None) -> Path:
    """Cópia consistente do SQLite. Nunca grava por cima do tela.db original."""
    if not tela_db.is_file():
        raise FileNotFoundError(f"não achei {tela_db}")
    destino.mkdir(parents=True, exist_ok=True)
    dia = hoje or date.today()
    arquivo = destino / f"{dia.isoformat()}.sqlite"
    src = sqlite3.connect(f"file:{tela_db.resolve().as_posix()}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(arquivo))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    limite = datetime.combine(dia, datetime.min.time()) - timedelta(days=int(retencao_dias))
    for antigo in destino.glob("*.sqlite"):
        try:
            if datetime.fromtimestamp(antigo.stat().st_mtime) < limite and antigo != arquivo:
                antigo.unlink()
        except OSError:
            pass
    return arquivo


def backup_semanal(origem: Path, destino: Path) -> int:
    """Espelho /E sem /MIR nem /PURGE: não apaga nada no destino."""
    origem = origem.resolve()
    destino.mkdir(parents=True, exist_ok=True)
    cmd = ["robocopy", str(origem), str(destino), "/E", "/COPY:DAT", "/R:2", "/W:1", "/NFL", "/NDL", "/NP"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    # robocopy: 0–7 = sucesso (bit flags); >= 8 = erro
    if proc.returncode >= 8:
        raise RuntimeError(f"robocopy falhou ({proc.returncode}): {proc.stderr or proc.stdout}")
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Backup do histórico do robô (não apaga a origem).")
    ap.add_argument("--config", default=str(RAIZ / "config.yaml"))
    ap.add_argument("--diario", action="store_true")
    ap.add_argument("--semanal", action="store_true")
    args = ap.parse_args(argv)
    if not args.diario and not args.semanal:
        ap.print_help()
        return 2
    cfg = Path(args.config)
    secoes = _ler_backup(cfg) if cfg.is_file() else {}
    pasta_saida = _pasta_saida(cfg) if cfg.is_file() else (RAIZ / "saida")
    if args.diario:
        tela = pasta_saida / "tela.db"
        dest = Path(secoes.get("pasta_tela") or PADRAO_TELA)
        ret = int(secoes.get("retencao_dias") or RETENCAO)
        arq = backup_diario(tela, dest, ret)
        print(f"Backup diário: {arq}")
    if args.semanal:
        dest = Path(secoes.get("pasta_saida_semanal") or PADRAO_SEMANAL)
        rc = backup_semanal(pasta_saida, dest)
        print(f"Espelho semanal em {dest} (robocopy {rc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
