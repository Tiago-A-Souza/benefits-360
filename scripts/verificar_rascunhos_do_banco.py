"""FASE 0 — os 93 rascunhos continuam carregando e os 66 continuam compilando."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from newport_app.draft_compiler import compile as compilar
from newport_app.models.draft import RascunhoEstudo

DB = Path(".data/newport_app.db")


def main() -> int:
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    linhas = conn.execute("SELECT id, payload FROM rascunhos").fetchall()
    conn.close()

    carregam = 0
    falham_carga: list[str] = []
    compilam = 0
    bloqueados: dict[str, int] = {}

    for estudo_id, payload in linhas:
        try:
            rascunho = RascunhoEstudo.model_validate(json.loads(payload))
        except Exception as exc:  # noqa: BLE001
            falham_carga.append(f"{estudo_id}: {type(exc).__name__}")
            continue
        carregam += 1
        try:
            resultado = compilar(rascunho)
        except Exception as exc:  # noqa: BLE001
            bloqueados[f"EXCECAO-{type(exc).__name__}"] = (
                bloqueados.get(f"EXCECAO-{type(exc).__name__}", 0) + 1
            )
            continue
        if resultado.compilado is not None:
            compilam += 1
        for e in resultado.erros:
            bloqueados[e.codigo] = bloqueados.get(e.codigo, 0) + 1

    print(f"RASCUNHOS_TOTAL={len(linhas)}")
    print(f"CARREGAM={carregam}")
    print(f"FALHAM_CARGA={len(falham_carga)} {falham_carga[:5]}")
    print(f"COMPILAM={compilam}")
    print(f"BLOQUEIOS={dict(sorted(bloqueados.items()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
