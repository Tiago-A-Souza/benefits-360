"""FASE 0 — o hash canônico dos snapshots já gravados continua o mesmo."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from newport_app.snapshot.hashing import hash_snapshot_canonico

DB = Path(".data/newport_app.db")


def main() -> int:
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    colunas = {r[1] for r in conn.execute("PRAGMA table_info(snapshots)")}
    if not colunas:
        print("SEM_TABELA_SNAPSHOTS")
        return 0
    linhas = conn.execute(
        "SELECT id, estudo_id, hash_sha256, payload, snapshot_versao "
        "FROM snapshots ORDER BY id"
    ).fetchall()
    conn.close()

    iguais = 0
    divergentes: list[tuple[str, str, str]] = []
    amostra: list[tuple[str, str]] = []

    for snap_id, estudo_id, gravado, conteudo, versao in linhas:
        recalculado = hash_snapshot_canonico(json.loads(conteudo), versao)
        if recalculado == gravado:
            iguais += 1
            if len(amostra) < 5:
                amostra.append((f"{estudo_id}/{snap_id}", gravado))
        else:
            divergentes.append((snap_id, gravado, recalculado))

    print(f"SNAPSHOTS_TOTAL={len(linhas)}")
    print(f"HASH_IGUAL={iguais}")
    print(f"HASH_DIVERGENTE={len(divergentes)}")
    for snap_id, gravado, recalculado in divergentes[:5]:
        print(f"  DIVERGE {snap_id}: gravado={gravado} recalculado={recalculado}")
    for rotulo, digest in amostra:
        print(f"  DIGEST {rotulo} = {digest}")
    return 1 if divergentes else 0


if __name__ == "__main__":
    sys.exit(main())
