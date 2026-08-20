"""Repositório de snapshots, aprovações e entregáveis."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from newport_app.models.snapshot import (
    AprovacaoSnapshot,
    EntregavelApresentacao,
    SnapshotCalculo,
)
from newport_app.repository.migration import migrar_estudos_db


class SnapshotRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        migrar_estudos_db(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def salvar_snapshot(self, snap: SnapshotCalculo) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE snapshots SET estado='superado', superado_em=?
                WHERE estudo_id=? AND estado='candidato'
                """,
                (datetime.now(timezone.utc).isoformat(), snap.estudo_id),
            )
            conn.execute(
                """
                INSERT INTO snapshots (
                    id, estudo_id, estado, hash_sha256, payload,
                    compiler_versao, motor_versao, policy_set_versao,
                    snapshot_versao, tem_bloqueio, criado_em, superado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snap.id,
                    snap.estudo_id,
                    snap.estado,
                    snap.hash_sha256,
                    json.dumps(snap.payload, ensure_ascii=False),
                    snap.compiler_versao,
                    snap.motor_versao,
                    snap.policy_set_versao,
                    snap.snapshot_versao,
                    1 if snap.tem_bloqueio else 0,
                    snap.criado_em.isoformat(),
                    snap.superado_em.isoformat() if snap.superado_em else None,
                ),
            )

    def obter_snapshot(self, snapshot_id: str) -> SnapshotCalculo | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM snapshots WHERE id=?", (snapshot_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_snapshot(row)

    def snapshot_candidato_atual(self, estudo_id: str) -> SnapshotCalculo | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM snapshots
                WHERE estudo_id=? AND estado='candidato'
                ORDER BY criado_em DESC LIMIT 1
                """,
                (estudo_id,),
            ).fetchone()
        return self._row_snapshot(row) if row else None

    def snapshot_aprovado_atual(self, estudo_id: str) -> SnapshotCalculo | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT s.* FROM snapshots s
                JOIN aprovacoes a ON a.snapshot_id = s.id
                WHERE s.estudo_id=? AND s.estado='aprovado' AND a.invalidada_em IS NULL
                ORDER BY a.aprovado_em DESC LIMIT 1
                """,
                (estudo_id,),
            ).fetchone()
        return self._row_snapshot(row) if row else None

    def listar_snapshots(self, estudo_id: str) -> list[SnapshotCalculo]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM snapshots WHERE estudo_id=? ORDER BY criado_em DESC",
                (estudo_id,),
            ).fetchall()
        return [self._row_snapshot(r) for r in rows]

    def marcar_superado(self, snapshot_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE snapshots SET estado='superado', superado_em=?
                WHERE id=?
                """,
                (datetime.now(timezone.utc).isoformat(), snapshot_id),
            )

    def marcar_aprovado(self, snapshot_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE snapshots SET estado='aprovado' WHERE id=?",
                (snapshot_id,),
            )

    def salvar_aprovacao(self, aprov: AprovacaoSnapshot) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO aprovacoes (
                    id, snapshot_id, revisor_nome, aprovado_em,
                    justificativa, auto_aprovacao, invalidada_em, invalidada_motivo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    aprov.id,
                    aprov.snapshot_id,
                    aprov.revisor_nome,
                    aprov.aprovado_em.isoformat(),
                    aprov.justificativa,
                    1 if aprov.auto_aprovacao else 0,
                    aprov.invalidada_em.isoformat() if aprov.invalidada_em else None,
                    aprov.invalidada_motivo,
                ),
            )

    def obter_aprovacao(self, snapshot_id: str) -> AprovacaoSnapshot | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM aprovacoes WHERE snapshot_id=?", (snapshot_id,)
            ).fetchone()
        if row is None:
            return None
        return AprovacaoSnapshot(
            id=row["id"],
            snapshot_id=row["snapshot_id"],
            revisor_nome=row["revisor_nome"],
            aprovado_em=datetime.fromisoformat(row["aprovado_em"]),
            justificativa=row["justificativa"],
            auto_aprovacao=bool(row["auto_aprovacao"]),
            invalidada_em=(
                datetime.fromisoformat(row["invalidada_em"]) if row["invalidada_em"] else None
            ),
            invalidada_motivo=row["invalidada_motivo"],
        )

    def invalidar_aprovacoes_estudo(self, estudo_id: str, motivo: str) -> None:
        agora = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE aprovacoes SET invalidada_em=?, invalidada_motivo=?
                WHERE snapshot_id IN (
                    SELECT id FROM snapshots WHERE estudo_id=?
                ) AND invalidada_em IS NULL
                """,
                (agora, motivo, estudo_id),
            )
            conn.execute(
                """
                UPDATE snapshots SET estado='superado', superado_em=?
                WHERE estudo_id=? AND estado IN ('candidato', 'aprovado')
                """,
                (agora, estudo_id),
            )
            conn.execute(
                "UPDATE entregaveis SET invalidado=1 WHERE estudo_id=?",
                (estudo_id,),
            )

    def salvar_entregavel(self, ent: EntregavelApresentacao) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO entregaveis (
                    id, estudo_id, snapshot_id, aprovacao_id, modo,
                    propostas_selecionadas, renderer_versao, hash_conteudo,
                    caminho_arquivo, invalidado, gerado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ent.id,
                    ent.estudo_id,
                    ent.snapshot_id,
                    ent.aprovacao_id,
                    ent.modo,
                    json.dumps(ent.propostas_selecionadas),
                    ent.renderer_versao,
                    ent.hash_conteudo,
                    ent.caminho_arquivo,
                    1 if ent.invalidado else 0,
                    ent.gerado_em.isoformat(),
                ),
            )

    def listar_entregaveis(self, estudo_id: str) -> list[EntregavelApresentacao]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM entregaveis WHERE estudo_id=? ORDER BY gerado_em DESC",
                (estudo_id,),
            ).fetchall()
        return [self._row_entregavel(r) for r in rows]

    def _row_snapshot(self, row: sqlite3.Row) -> SnapshotCalculo:
        return SnapshotCalculo(
            id=row["id"],
            estudo_id=row["estudo_id"],
            estado=row["estado"],
            hash_sha256=row["hash_sha256"],
            payload=json.loads(row["payload"]),
            compiler_versao=row["compiler_versao"],
            motor_versao=row["motor_versao"],
            policy_set_versao=row["policy_set_versao"],
            snapshot_versao=row["snapshot_versao"] if "snapshot_versao" in row.keys() else None,
            tem_bloqueio=bool(row["tem_bloqueio"]),
            criado_em=datetime.fromisoformat(row["criado_em"]),
            superado_em=(
                datetime.fromisoformat(row["superado_em"]) if row["superado_em"] else None
            ),
        )

    def _row_entregavel(self, row: sqlite3.Row) -> EntregavelApresentacao:
        return EntregavelApresentacao(
            id=row["id"],
            estudo_id=row["estudo_id"],
            snapshot_id=row["snapshot_id"],
            aprovacao_id=row["aprovacao_id"],
            modo=row["modo"],
            propostas_selecionadas=json.loads(row["propostas_selecionadas"]),
            renderer_versao=row["renderer_versao"],
            hash_conteudo=row["hash_conteudo"],
            caminho_arquivo=row["caminho_arquivo"],
            invalidado=bool(row["invalidado"]),
            gerado_em=datetime.fromisoformat(row["gerado_em"]),
        )
