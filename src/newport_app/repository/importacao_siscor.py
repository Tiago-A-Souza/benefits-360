"""Persistência de importações SISCOR candidatas."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from newport_app.auth.contexto import id_dono, params_visivel
from newport_app.models.siscor_import import ImportacaoSiscorCandidata
from newport_app.repository.migration import migrar_banco_importacoes


class ImportacaoSiscorRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        migrar_banco_importacoes(self._db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS importacoes_siscor (
                    id TEXT PRIMARY KEY,
                    estudo_id TEXT NOT NULL,
                    versao INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    ativa INTEGER NOT NULL DEFAULT 1,
                    criado_em TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_importacoes_estudo
                ON importacoes_siscor (estudo_id, ativa)
                """
            )

    def salvar(self, candidata: ImportacaoSiscorCandidata, *, ativa: bool = True) -> None:
        agora = datetime.now(timezone.utc).isoformat()
        payload = candidata.model_dump_json()
        with self._connect() as conn:
            if ativa:
                conn.execute(
                    "UPDATE importacoes_siscor SET ativa = 0 WHERE estudo_id = ? AND (usuario_id = ? OR ? = 1)",
                    (candidata.estudo_id, *params_visivel()),
                )
            conn.execute(
                """
                INSERT INTO importacoes_siscor (id, estudo_id, versao, payload, ativa, criado_em, usuario_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    ativa = excluded.ativa,
                    criado_em = excluded.criado_em
                WHERE importacoes_siscor.usuario_id = excluded.usuario_id
                """,
                (
                    candidata.id,
                    candidata.estudo_id,
                    candidata.versao,
                    payload,
                    1 if ativa else 0,
                    agora,
                    id_dono(),
                ),
            )

    def obter_ativa(self, estudo_id: str) -> ImportacaoSiscorCandidata | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload FROM importacoes_siscor
                WHERE estudo_id = ? AND ativa = 1 AND (usuario_id = ? OR ? = 1)
                ORDER BY versao DESC LIMIT 1
                """,
                (estudo_id, *params_visivel()),
            ).fetchone()
        if row is None:
            return None
        return ImportacaoSiscorCandidata.model_validate_json(row["payload"])

    def listar_versoes(self, estudo_id: str) -> list[int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT versao FROM importacoes_siscor WHERE estudo_id = ? AND (usuario_id = ? OR ? = 1) ORDER BY versao",
                (estudo_id, *params_visivel()),
            ).fetchall()
        return [int(r["versao"]) for r in rows]

    def possui_confirmacoes(self, estudo_id: str) -> bool:
        candidata = self.obter_ativa(estudo_id)
        if candidata is None:
            return False
        return any(linha.registro_confirmado for linha in candidata.linhas)
