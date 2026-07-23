"""Persistência versionada de extrações de cotação PDF."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from newport_app.models.cotacao_pdf import ExtracaoCotacaoCandidata


class ExtracaoCotacaoRepository:
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
                CREATE TABLE IF NOT EXISTS extracoes_cotacao (
                    id TEXT PRIMARY KEY,
                    estudo_id TEXT NOT NULL,
                    documento_id TEXT NOT NULL,
                    versao INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    ativa INTEGER NOT NULL DEFAULT 1,
                    criado_em TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_extracao_estudo_doc
                ON extracoes_cotacao (estudo_id, documento_id, ativa)
                """
            )

    def salvar(self, extracao: ExtracaoCotacaoCandidata, *, ativa: bool = True) -> None:
        agora = datetime.now(timezone.utc).isoformat()
        payload = extracao.model_dump_json()
        with self._connect() as conn:
            if ativa:
                conn.execute(
                    """
                    UPDATE extracoes_cotacao SET ativa = 0
                    WHERE estudo_id = ? AND documento_id = ?
                    """,
                    (extracao.estudo_id, extracao.documento.id),
                )
            conn.execute(
                """
                INSERT INTO extracoes_cotacao
                (id, estudo_id, documento_id, versao, payload, ativa, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    ativa = excluded.ativa,
                    criado_em = excluded.criado_em
                """,
                (
                    extracao.id,
                    extracao.estudo_id,
                    extracao.documento.id,
                    extracao.versao,
                    payload,
                    1 if ativa else 0,
                    agora,
                ),
            )

    def obter_ativa_por_documento(
        self, estudo_id: str, documento_id: str
    ) -> ExtracaoCotacaoCandidata | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload FROM extracoes_cotacao
                WHERE estudo_id = ? AND documento_id = ? AND ativa = 1
                ORDER BY versao DESC LIMIT 1
                """,
                (estudo_id, documento_id),
            ).fetchone()
        if row is None:
            return None
        return ExtracaoCotacaoCandidata.model_validate_json(row["payload"])

    def listar_ativas(self, estudo_id: str) -> list[ExtracaoCotacaoCandidata]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload FROM extracoes_cotacao
                WHERE estudo_id = ? AND ativa = 1
                ORDER BY criado_em DESC
                """,
                (estudo_id,),
            ).fetchall()
        return [ExtracaoCotacaoCandidata.model_validate_json(row["payload"]) for r in rows]

    def desativar_por_documento(self, estudo_id: str, documento_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE extracoes_cotacao SET ativa = 0
                WHERE estudo_id = ? AND documento_id = ?
                """,
                (estudo_id, documento_id),
            )

    def listar_versoes(self, estudo_id: str, documento_id: str) -> list[int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT versao FROM extracoes_cotacao
                WHERE estudo_id = ? AND documento_id = ?
                ORDER BY versao
                """,
                (estudo_id, documento_id),
            ).fetchall()
        return [int(r["versao"]) for r in rows]

    def obter_por_id(self, extracao_id: str) -> ExtracaoCotacaoCandidata | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM extracoes_cotacao WHERE id = ?",
                (extracao_id,),
            ).fetchone()
        if row is None:
            return None
        return ExtracaoCotacaoCandidata.model_validate_json(row["payload"])
