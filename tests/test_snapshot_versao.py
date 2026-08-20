"""Correção 1 — snapshot_versao gravada no registro e no payload."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from newport_app.models.snapshot import SNAPSHOT_VERSAO, SnapshotCalculo
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.snapshot import SnapshotService


def test_snapshot_novo_grava_versao_atual(tmp_path: Path):
    db = tmp_path / "estudos.db"
    repo = SQLiteStudyRepository(db)
    snap_repo = SnapshotRepository(db)
    snap_svc = SnapshotService(repo, snap_repo, HistoricoRepository(db))
    r = rascunho_demo_12_vidas()
    repo.salvar_rascunho(r)

    gerado = snap_svc.gerar_snapshot_candidato(r.id)
    snap = snap_svc.obter_snapshot(gerado.snapshot_id)

    assert SNAPSHOT_VERSAO == "2.8.0"
    assert snap.snapshot_versao == SNAPSHOT_VERSAO
    assert snap.payload["snapshot_versao"] == SNAPSHOT_VERSAO


def test_snapshot_sem_versao_gravada_nao_presume_versao_atual(tmp_path: Path):
    db = tmp_path / "estudos.db"
    snap_repo = SnapshotRepository(db)
    legado = SnapshotCalculo(
        id="snap-legado",
        estudo_id="est-legado",
        estado="candidato",
        hash_sha256="abc",
        payload={"comparativo": {}},
        compiler_versao="x",
        motor_versao="0.1.0",
        policy_set_versao="p",
        snapshot_versao=None,
        criado_em=datetime.now(timezone.utc),
    )
    snap_repo.salvar_snapshot(legado)
    lido = snap_repo.obter_snapshot("snap-legado")
    assert lido is not None
    assert lido.snapshot_versao is None
    assert lido.snapshot_versao != SNAPSHOT_VERSAO
