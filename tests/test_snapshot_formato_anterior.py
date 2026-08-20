"""Correção 3 — recusa explícita de comparativo em formato anterior a 37cf41f."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from newport_app.models.responses import ComparativoResponse
from newport_app.models.snapshot import SnapshotCalculo
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.snapshot import (
    SnapshotFormatoIncompativelError,
    SnapshotService,
)


def _svc(tmp_path: Path):
    db = tmp_path / "estudos.db"
    repo = SQLiteStudyRepository(db)
    snap_repo = SnapshotRepository(db)
    snap_svc = SnapshotService(repo, snap_repo, HistoricoRepository(db))
    return repo, snap_repo, snap_svc


def _gravar(snap_repo: SnapshotRepository, comparativo: dict, snap_id: str = "snap-fmt") -> str:
    snap_repo.salvar_snapshot(
        SnapshotCalculo(
            id=snap_id,
            estudo_id="est-fmt",
            estado="aprovado",
            hash_sha256="abc",
            payload={"comparativo": comparativo},
            compiler_versao="x",
            motor_versao="0.1.0",
            policy_set_versao="p",
            snapshot_versao=None,
            criado_em=datetime.now(timezone.utc),
        )
    )
    return snap_id


def test_formato_anterior_nao_reabre_com_planos_atuais_vazio(tmp_path: Path):
    _, snap_repo, snap_svc = _svc(tmp_path)
    comparativo = {
        "estudo_id": "est-legado",
        "titulo": "Renovação",
        "beneficiarios_calculados": 12,
        "calculo_realizado": True,
        "formato": "renovacao",
        "plano_atual": {"operadora": "AMIL", "plano_nome": "S750"},
    }
    silencioso = ComparativoResponse.model_validate(comparativo)
    assert silencioso.planos_atuais == []

    snap_id = _gravar(snap_repo, comparativo)
    with pytest.raises(SnapshotFormatoIncompativelError) as exc:
        snap_svc.comparativo_do_snapshot(snap_id)
    msg = str(exc.value)
    assert "formato anterior" in msg.lower()
    assert "gere um novo snapshot" in msg.lower()
    assert "est-legado" not in msg
    assert snap_id not in msg
    assert "abc" not in msg


def test_formato_atual_reabre_normalmente(tmp_path: Path):
    repo, _, snap_svc = _svc(tmp_path)
    r = rascunho_demo_12_vidas()
    repo.salvar_rascunho(r)
    gerado = snap_svc.gerar_snapshot_candidato(r.id)
    resp = snap_svc.comparativo_do_snapshot(gerado.snapshot_id)
    assert resp.estudo_id == r.id
    assert resp.planos_atuais
    assert resp.planos_atuais[0].plano_nome


def test_mensagem_recusa_e_legivel(tmp_path: Path):
    _, snap_repo, snap_svc = _svc(tmp_path)
    snap_id = _gravar(
        snap_repo,
        {
            "estudo_id": "uuid-interno-nao-vazar",
            "titulo": "X",
            "beneficiarios_calculados": 1,
            "calculo_realizado": True,
            "plano_atual": {"operadora": "Y"},
        },
        snap_id="uuid-do-snapshot",
    )
    with pytest.raises(SnapshotFormatoIncompativelError) as exc:
        snap_svc.comparativo_do_snapshot(snap_id)
    msg = str(exc.value)
    assert "uuid-interno-nao-vazar" not in msg
    assert "uuid-do-snapshot" not in msg
    assert "Gere um novo snapshot" in msg
