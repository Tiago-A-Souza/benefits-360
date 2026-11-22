"""Backup diário dos SQLite (API oficial) e das pastas de PDF/entregáveis.

Não copia o arquivo .db aberto. Uso:

    python -m newport_app.backup
    python -m newport_app.backup restaurar 2026-11-19
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from newport_app.config.env import carregar_env_local
from newport_app.config.paths import (
    caminho_banco_cotacoes,
    caminho_banco_estudos,
    caminho_banco_importacoes,
    diretorio_backup,
    diretorio_dados,
    diretorio_entregaveis,
    diretorio_uploads,
    diretorio_uploads_cotacao,
)


def retencao_dias() -> int:
    bruto = (os.environ.get("NEWPORT_BACKUP_RETENCAO_DIAS") or "14").strip()
    try:
        dias = int(bruto)
    except ValueError as exc:
        raise RuntimeError(
            f"NEWPORT_BACKUP_RETENCAO_DIAS inválida: {bruto!r}."
        ) from exc
    if dias < 1:
        raise RuntimeError("NEWPORT_BACKUP_RETENCAO_DIAS deve ser >= 1.")
    return dias


def nome_pasta_dia(agora: datetime | None = None) -> str:
    momento = agora or datetime.now(timezone.utc)
    return momento.strftime("%Y-%m-%d")


def copiar_sqlite_seguro(origem: Path, destino: Path) -> None:
    """Cópia consistente via sqlite3.Connection.backup (não copia o arquivo aberto)."""
    if not origem.is_file():
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(origem))
    try:
        dst = sqlite3.connect(str(destino))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _copiar_pasta(origem: Path, destino: Path) -> None:
    if not origem.is_dir():
        return
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(origem, destino, dirs_exist_ok=True)


def itens_backup(modo=None) -> list[tuple[str, Path, str]]:
    """(nome_no_backup, caminho_origem, tipo db|pasta)."""
    return [
        ("estudos.db", caminho_banco_estudos(modo), "db"),
        ("importacoes.db", caminho_banco_importacoes(modo), "db"),
        ("cotacoes.db", caminho_banco_cotacoes(modo), "db"),
        ("uploads", diretorio_uploads(modo), "pasta"),
        ("cotacoes", diretorio_uploads_cotacao(modo), "pasta"),
        ("entregaveis", diretorio_entregaveis(modo), "pasta"),
    ]


def executar_backup(
    destino_raiz: Path | None = None,
    *,
    agora: datetime | None = None,
    modo=None,
) -> Path:
    raiz = destino_raiz or diretorio_backup(modo)
    pasta = raiz / nome_pasta_dia(agora)
    pasta.mkdir(parents=True, exist_ok=True)
    linhas = [
        f"criado_em_utc={(agora or datetime.now(timezone.utc)).isoformat()}",
        f"origem={diretorio_dados(modo)}",
    ]
    for nome, origem, tipo in itens_backup(modo):
        alvo = pasta / nome
        if tipo == "db":
            copiar_sqlite_seguro(origem, alvo)
        else:
            _copiar_pasta(origem, alvo)
        linhas.append(f"{nome}\t{origem}\t{'ok' if alvo.exists() else 'ausente'}")
    (pasta / "MANIFEST.txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return pasta


def limpar_antigos(
    raiz: Path,
    dias: int,
    *,
    hoje: datetime | None = None,
) -> list[Path]:
    limite = (hoje or datetime.now(timezone.utc)).date() - timedelta(days=dias)
    removidos: list[Path] = []
    if not raiz.is_dir():
        return removidos
    for pasta in sorted(raiz.iterdir()):
        if not pasta.is_dir():
            continue
        try:
            dia = datetime.strptime(pasta.name[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if dia < limite:
            shutil.rmtree(pasta)
            removidos.append(pasta)
    return removidos


def restaurar(
    pasta_backup: Path,
    destino_runtime: Path | None = None,
    *,
    modo=None,
) -> None:
    """Devolve o backup ao runtime. Pare a API antes de restaurar."""
    if not pasta_backup.is_dir():
        raise FileNotFoundError(f"Backup não encontrado: {pasta_backup}")
    if destino_runtime is None:
        alvos = [(nome, origem, tipo) for nome, origem, tipo in itens_backup(modo)]
    else:
        destino_runtime.mkdir(parents=True, exist_ok=True)
        alvos = [
            (nome, destino_runtime / nome, tipo) for nome, _origem, tipo in itens_backup(modo)
        ]
    for nome, destino, tipo in alvos:
        origem = pasta_backup / nome
        if tipo == "db":
            copiar_sqlite_seguro(origem, destino)
        else:
            _copiar_pasta(origem, destino)


def _cli(argv: list[str] | None = None) -> int:
    carregar_env_local()
    parser = argparse.ArgumentParser(
        description="Backup seguro dos bancos SQLite e das pastas de PDF/HTML."
    )
    parser.add_argument(
        "comando",
        nargs="?",
        default="backup",
        choices=("backup", "restaurar"),
    )
    parser.add_argument(
        "alvo",
        nargs="?",
        help="Data YYYY-MM-DD (restaurar) ou pasta de backup.",
    )
    parser.add_argument(
        "--destino",
        help="Pasta de runtime para restaurar (padrão: dados do modo atual).",
    )
    args = parser.parse_args(argv)
    if args.comando == "backup":
        pasta = executar_backup()
        apagados = limpar_antigos(diretorio_backup(), retencao_dias())
        print(f"backup em {pasta}")
        for velho in apagados:
            print(f"removido {velho}")
        return 0
    if not args.alvo:
        print("Informe a data do backup (YYYY-MM-DD) ou o caminho da pasta.", file=sys.stderr)
        return 2
    alvo = Path(args.alvo)
    if not alvo.is_dir():
        alvo = diretorio_backup() / args.alvo
    destino = Path(args.destino) if args.destino else None
    restaurar(alvo, destino)
    print(f"restaurado {alvo} -> {destino or diretorio_dados()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
