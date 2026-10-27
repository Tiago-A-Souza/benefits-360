"""Implementação SQLite do StudyRepository + migração histórica ETAPA 2.6."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from newport_app.draft_compiler.structural import (
    RascunhoEstruturalInvalidoError,
    validar_estrutura,
)
from newport_app.models.draft import RascunhoEstudo
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from newport_app.rascunho.selecao_grupo import sanear_selecao_por_grupo
from newport_app.services.comparativo_confirmacao import sanitizar_confirmacao_comparativo
from newport_app.services.comparativo_ui import sanitizar_selecao_apresentacao
from newport_app.presentation.rede_matriz_hospital import carregar_base_rede_hospital
from newport_app.services.rede_selecao import (
    descartar_incluidos_invalidos,
    sanitizar_selecao_rede,
)
from newport_app.services.rede_selecao_ui import todos_ids_linha_rede
from newport_app.repository.migration import migrar_estudos_db


def _sanitizar_rede_selecao_rascunho(rascunho: RascunhoEstudo) -> None:
    if rascunho.selecao_rede is None:
        return
    if not rascunho.cenarios:
        return
    try:
        if rascunho.selecao_rede.incluidos:
            # Inclusões manuais: validadas contra a base COMPLETA, e descartadas
            # se o prestador já está na visão calculada (virou principal).
            base = carregar_base_rede_hospital()
            visao = todos_ids_linha_rede(rascunho, incluir_manuais=False)
            descartar_incluidos_invalidos(rascunho, base.chaves_prestadores, visao)
        ids = todos_ids_linha_rede(rascunho)
    except Exception:
        return
    sanitizar_selecao_rede(rascunho, ids)


class SQLiteStudyRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        migrar_estudos_db(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def obter_rascunho(self, estudo_id: str) -> RascunhoEstudo | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM rascunhos WHERE id = ?", (estudo_id,)
            ).fetchone()
        if row is None:
            return None
        rascunho = RascunhoEstudo.model_validate_json(row["payload"])
        rascunho = sincronizar_cenarios(rascunho)
        sanitizar_selecao_apresentacao(rascunho)
        sanitizar_confirmacao_comparativo(rascunho)
        sanear_selecao_por_grupo(rascunho)
        _sanitizar_rede_selecao_rascunho(rascunho)
        return rascunho

    def salvar_rascunho(self, rascunho: RascunhoEstudo) -> None:
        rascunho = sincronizar_cenarios(rascunho)
        sanitizar_selecao_apresentacao(rascunho)
        sanitizar_confirmacao_comparativo(rascunho)
        sanear_selecao_por_grupo(rascunho)
        _sanitizar_rede_selecao_rascunho(rascunho)
        erros = validar_estrutura(rascunho)
        if erros:
            raise RascunhoEstruturalInvalidoError(erros)

        agora = datetime.now(timezone.utc).isoformat()
        payload = rascunho.model_dump_json()
        with self._connect() as conn:
            self._salvar_rascunho_conn(conn, rascunho, payload, agora)

    def _salvar_rascunho_conn(
        self,
        conn: sqlite3.Connection,
        rascunho: RascunhoEstudo,
        payload: str,
        agora: str,
    ) -> None:
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

    @property
    def db_path(self) -> Path:
        return self._db_path

    def listar_ids(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id FROM rascunhos ORDER BY id").fetchall()
        return [str(r["id"]) for r in rows]

    def listar_metadados(self) -> list[tuple[str, str | None]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, atualizado_em FROM rascunhos ORDER BY atualizado_em DESC"
            ).fetchall()
        return [(str(r["id"]), r["atualizado_em"]) for r in rows]
