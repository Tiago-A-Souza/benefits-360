"""Fase 3B — JWT, rota pública /api/saude e isolamento por usuario_id."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from newport_app.auth.jwt_supabase import ValidadorJwtSupabase, configurar_validador
from newport_app.auth.startup import AuthNaoConfiguradaError
from newport_app.repository.extracao_cotacao import ExtracaoCotacaoRepository
from newport_app.repository.importacao_siscor import ImportacaoSiscorRepository
from newport_app.repository.migration import TABELAS_POR_USUARIO, migrar_estudos_db
from newport_app.repository.sqlite import SQLiteStudyRepository

SUPA = "https://exemplo.supabase.co"
_PRIV = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_JWK = json.loads(RSAAlgorithm.to_jwk(_PRIV.public_key()))
_JWK.update({"kid": "t3b", "alg": "RS256", "use": "sig"})
_HS = "segredo-hs256-de-teste-nao-usar-em-producao"


def _token(sub: str, *, exp_delta: int = 3600, alg: str = "RS256") -> str:
    agora = int(time.time())
    payload = {
        "sub": sub,
        "email": f"{sub}@exemplo.com",
        "aud": "authenticated",
        "iss": f"{SUPA}/auth/v1",
        "iat": agora,
        "exp": agora + exp_delta,
        "role": "authenticated",
    }
    if alg == "HS256":
        return jwt.encode(payload, _HS, algorithm="HS256")
    return jwt.encode(payload, _PRIV, algorithm="RS256", headers={"kid": "t3b"})


def _app_real(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEWPORT_MODO", "real")
    monkeypatch.setenv("SUPABASE_URL", SUPA)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", _HS)
    monkeypatch.setenv("NEWPORT_PRIVATE_RUNTIME", str(tmp_path / "priv"))
    monkeypatch.setenv("NEWPORT_DATA_DIR", str(tmp_path / "demo"))
    monkeypatch.setenv("BENEFITS_DONO_LEGADO_ID", "")
    from newport_app.api.main import create_app

    app = create_app(
        repo=SQLiteStudyRepository(tmp_path / "estudos.db"),
        import_repo=ImportacaoSiscorRepository(tmp_path / "imp.db"),
        cotacao_repo=ExtracaoCotacaoRepository(tmp_path / "cot.db"),
        seed_demos=False,
    )
    configurar_validador(
        ValidadorJwtSupabase(
            supabase_url=SUPA,
            jwt_secret=_HS,
            jwks={"keys": [_JWK]},
        )
    )
    return app


def test_recusa_subir_sem_supabase_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEWPORT_MODO", "real")
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("NEWPORT_PRIVATE_RUNTIME", str(tmp_path))
    from newport_app.api.main import create_app

    with pytest.raises(AuthNaoConfiguradaError):
        create_app(seed_demos=False)


def test_saude_publica_e_resto_exige_login(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = TestClient(_app_real(tmp_path, monkeypatch))
    saude = client.get("/api/saude")
    assert saude.status_code == 200
    assert saude.json() == {"ok": True}
    assert client.get("/api/config").status_code == 401
    assert client.get("/api/estudos").status_code == 401
    assert client.post("/api/diagnostico", json={"etapa": "x", "evento": "y"}).status_code == 401
    assert client.get("/api/simular-rede/opcoes").status_code == 401
    preflight = client.options("/api/estudos")
    assert preflight.status_code != 401


def test_jwt_rs256_jwks_e_hs256(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = TestClient(_app_real(tmp_path, monkeypatch))
    rs = client.get(
        "/api/config",
        headers={"Authorization": f"Bearer {_token('user-rs')}"},
    )
    assert rs.status_code == 200
    assert rs.json()["modo"] == "real"
    hs = client.get(
        "/api/config",
        headers={"Authorization": f"Bearer {_token('user-hs', alg='HS256')}"},
    )
    assert hs.status_code == 200
    expirado = client.get(
        "/api/config",
        headers={"Authorization": f"Bearer {_token('user-rs', exp_delta=-10)}"},
    )
    assert expirado.status_code == 401


def test_usuario_a_nao_ve_estudo_de_b(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = TestClient(_app_real(tmp_path, monkeypatch))
    ha = {"Authorization": f"Bearer {_token('user-a')}"}
    hb = {"Authorization": f"Bearer {_token('user-b')}"}
    criado = client.post(
        "/api/estudos",
        json={"titulo": "Estudo A", "nome_empresa": "Empresa A"},
        headers=ha,
    )
    assert criado.status_code == 200, criado.text
    eid = criado.json()["id"]
    assert client.get(f"/api/estudos/{eid}", headers=ha).status_code == 200
    assert client.get(f"/api/estudos/{eid}", headers=hb).status_code == 404
    lista_b = client.get("/api/estudos", headers=hb)
    assert lista_b.status_code == 200
    assert lista_b.json() == []
    with sqlite3.connect(tmp_path / "estudos.db") as conn:
        dono = conn.execute(
            "SELECT usuario_id FROM rascunhos WHERE id=?", (eid,)
        ).fetchone()[0]
    assert dono == "user-a"


def test_migracao_preserva_linhas_e_backfill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEWPORT_MODO", "demo")
    monkeypatch.setenv("BENEFITS_DONO_LEGADO_ID", "dono-legado")
    db = tmp_path / "legado.db"
    migrar_estudos_db(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO rascunhos (id, payload, atualizado_em, rascunho_versao) "
            "VALUES ('est-legado', '{}', '2026-01-01T00:00:00+00:00', '1.0')"
        )
        conn.execute("UPDATE rascunhos SET usuario_id = NULL")
        n_antes = conn.execute("SELECT COUNT(*) FROM rascunhos").fetchone()[0]
    migrar_estudos_db(db)
    with sqlite3.connect(db) as conn:
        n_depois = conn.execute("SELECT COUNT(*) FROM rascunhos").fetchone()[0]
        dono = conn.execute(
            "SELECT usuario_id FROM rascunhos WHERE id='est-legado'"
        ).fetchone()[0]
        cols = {
            t: {r[1] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()}
            for t in TABELAS_POR_USUARIO
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)
            ).fetchone()
        }
    assert n_antes == n_depois == 1
    assert dono == "dono-legado"
    for tabela, nomes in cols.items():
        assert "usuario_id" in nomes, tabela
    assert "schema_migrations" not in TABELAS_POR_USUARIO
