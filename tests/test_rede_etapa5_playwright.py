"""Jornada etapa 5 — API (mesmo contrato que a UI, sem Vite 5174)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.repository.sqlite import SQLiteStudyRepository
from tests.test_rede_fase_d1 import _rascunho_dois_grupos_um_cenario

ROOT = Path(__file__).resolve().parents[1]
_XLSX = ROOT / "docs" / "SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx"


@pytest.fixture
def repo_jornada(tmp_path: Path) -> SQLiteStudyRepository:
    return SQLiteStudyRepository(tmp_path / "jornada_et5.db")


@pytest.fixture
def client_jornada(repo_jornada: SQLiteStudyRepository) -> TestClient:
    return TestClient(create_app(repo=repo_jornada, seed_demos=False))


def test_jornada_carregar_salvar_rede_e_rascunho(
    client_jornada: TestClient, repo_jornada: SQLiteStudyRepository
):
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    rascunho, _, _ = _rascunho_dois_grupos_um_cenario()
    eid = "est-jornada-et5"
    repo_jornada.salvar_rascunho(rascunho.model_copy(update={"id": eid}))

    get_rede = client_jornada.get(f"/api/estudos/{eid}/rede-selecao")
    assert get_rede.status_code == 200
    body = get_rede.json()
    assert body["secoes"] or body.get("aviso_sem_localizacao")

    put = client_jornada.put(
        f"/api/estudos/{eid}/rede-selecao",
        json={"excluidos": [], "revisada": True},
    )
    assert put.status_code == 200

    get_r = client_jornada.get(f"/api/estudos/{eid}/rascunho")
    assert get_r.status_code == 200
    assert get_r.json()["selecao_rede"]["revisada"] is True
