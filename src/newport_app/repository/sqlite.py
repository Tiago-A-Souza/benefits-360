"""Implementação SQLite do StudyRepository.

Persistência provisória em JSON — endurecimento previsto na ETAPA 2.6.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from newport_app.draft_compiler.structural import (
    RascunhoEstruturalInvalidoError,
    validar_estrutura,
)
from newport_app.models.draft import RascunhoEstudo


class SQLiteStudyRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rascunhos (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
                """
            )
            colunas = {
                row[1]
                for row in conn.execute("PRAGMA table_info(rascunhos)").fetchall()
            }
            if "rascunho_versao" not in colunas:
                conn.execute(
                    "ALTER TABLE rascunhos ADD COLUMN rascunho_versao TEXT NOT NULL DEFAULT '1.0'"
                )
            if "policy_set_versao" not in colunas:
                conn.execute(
                    "ALTER TABLE rascunhos ADD COLUMN policy_set_versao TEXT"
                )

    def obter_rascunho(self, estudo_id: str) -> RascunhoEstudo | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM rascunhos WHERE id = ?", (estudo_id,)
            ).fetchone()
        if row is None:
            return None
        return RascunhoEstudo.model_validate_json(row["payload"])

    def salvar_rascunho(self, rascunho: RascunhoEstudo) -> None:
        erros = validar_estrutura(rascunho)
        if erros:
            raise RascunhoEstruturalInvalidoError(erros)

        agora = datetime.now(timezone.utc).isoformat()
        payload = rascunho.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO rascunhos (
                    id, payload, rascunho_versao, policy_set_versao, atualizado_em
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    rascunho_versao = excluded.rascunho_versao,
                    policy_set_versao = excluded.policy_set_versao,
                    atualizado_em = excluded.atualizado_em
                """,
                (
                    rascunho.id,
                    payload,
                    rascunho.rascunho_versao,
                    rascunho.policy_set_versao,
                    agora,
                ),
            )

    def listar_ids(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id FROM rascunhos ORDER BY id").fetchall()
        return [str(r["id"]) for r in rows]
