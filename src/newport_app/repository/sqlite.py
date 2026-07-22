"""Implementação SQLite do StudyRepository."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

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

    def obter_rascunho(self, estudo_id: str) -> RascunhoEstudo | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM rascunhos WHERE id = ?", (estudo_id,)
            ).fetchone()
        if row is None:
            return None
        return RascunhoEstudo.model_validate_json(row["payload"])

    def salvar_rascunho(self, rascunho: RascunhoEstudo) -> None:
        agora = datetime.now(timezone.utc).isoformat()
        payload = rascunho.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO rascunhos (id, payload, atualizado_em)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    atualizado_em = excluded.atualizado_em
                """,
                (rascunho.id, payload, agora),
            )

    def listar_ids(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id FROM rascunhos ORDER BY id").fetchall()
        return [str(r["id"]) for r in rows]
