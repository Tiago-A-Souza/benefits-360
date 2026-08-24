"""Ajuste A — remover regime de coparticipação «customizada»."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from newport_app.models.draft import RegimeCopartRascunho, RascunhoEstudo
from newport_app.repository.migration import (
    RegimeCustomizadaEmUsoError,
    migrar_estudos_db,
    migrar_regime_customizada,
)
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_motor.types import RegimeCopartTipo


def _inserir_rascunho_com_regimes(
    db: Path,
    *,
    estudo_id: str,
    regimes: list[dict],
    regime_refs: dict[str, str] | None = None,
) -> None:
    migrar_estudos_db(db)
    base = rascunho_demo_12_vidas()
    base.id = estudo_id
    payload = json.loads(base.model_dump_json())
    payload["id"] = estudo_id
    payload["regimes_copart"] = regimes
    if regime_refs:
        for lista, rid in regime_refs.items():
            if payload.get(lista):
                payload[lista][0]["regime_copart_id"] = rid
    agora = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO rascunhos (id, payload, atualizado_em, rascunho_versao, policy_set_versao)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                payload=excluded.payload,
                atualizado_em=excluded.atualizado_em
            """,
            (
                estudo_id,
                json.dumps(payload, ensure_ascii=False),
                agora,
                payload.get("rascunho_versao", "1.0"),
                payload.get("policy_set_versao"),
            ),
        )
        conn.commit()


def test_enum_sem_customizada():
    assert {t.value for t in RegimeCopartTipo} == {"sem", "parcial", "percentual"}
    with pytest.raises(ValueError):
        RegimeCopartTipo("customizada")
    with pytest.raises(ValidationError):
        RegimeCopartRascunho(id="regime-customizada", tipo="customizada")


def test_constants_js_sem_customizada_e_parcial_terapias():
    texto = (Path(__file__).resolve().parents[1] / "web" / "src" / "constants.js").read_text(
        encoding="utf-8"
    )
    bloco = texto.split("export const REGIMES_COPART")[1].split("];")[0]
    assert "sem" in bloco
    assert "parcial" in bloco
    assert "percentual" in bloco
    assert "customizada" not in bloco
    assert "Parcial (terapias)" in bloco


def test_migracao_remove_orfao_e_e_idempotente(tmp_path: Path):
    db = tmp_path / "regime.db"
    regimes = [
        {"id": "regime-sem", "tipo": "sem", "percentual": None},
        {"id": "regime-customizada", "tipo": "customizada", "percentual": None},
    ]
    _inserir_rascunho_com_regimes(db, estudo_id="est-reg-cust", regimes=regimes)

    with sqlite3.connect(db) as conn:
        n1 = migrar_regime_customizada(conn)
        conn.commit()
        aud = conn.execute(
            """
            SELECT acao, criado_por FROM auditoria
            WHERE estudo_id=? AND acao='migrar_regime_customizada'
            """,
            ("est-reg-cust",),
        ).fetchone()
        n2 = migrar_regime_customizada(conn)
        conn.commit()

    assert n1 == 1
    assert n2 == 0
    assert aud is not None
    assert aud[1] == "migracao-2.8.5"

    repo = SQLiteStudyRepository(db)
    rascunho = repo.obter_rascunho("est-reg-cust")
    assert rascunho is not None
    assert all(r.tipo != "customizada" for r in rascunho.regimes_copart)
    assert not any(r.id == "regime-customizada" for r in rascunho.regimes_copart)

    with sqlite3.connect(db) as conn:
        bruto = conn.execute(
            "SELECT payload FROM rascunhos WHERE id=?", ("est-reg-cust",)
        ).fetchone()[0]
    assert "customizada" not in bruto


def test_migracao_aborta_se_em_uso(tmp_path: Path):
    db = tmp_path / "regime-uso.db"
    regimes = [
        {"id": "regime-customizada", "tipo": "customizada", "percentual": None},
    ]
    _inserir_rascunho_com_regimes(
        db,
        estudo_id="est-em-uso",
        regimes=regimes,
        regime_refs={"opcoes_proposta": "regime-customizada"},
    )
    with sqlite3.connect(db) as conn:
        with pytest.raises(RegimeCustomizadaEmUsoError):
            migrar_regime_customizada(conn)


def test_migracao_285_marca_schema(tmp_path: Path):
    db = tmp_path / "schema285.db"
    regimes = [
        {"id": "regime-customizada", "tipo": "customizada", "percentual": None},
    ]
    _inserir_rascunho_com_regimes(db, estudo_id="est-schema", regimes=regimes)
    with sqlite3.connect(db) as conn:
        marca = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE versao='2.8.5'"
        ).fetchone()
        assert marca is not None
        assert migrar_regime_customizada(conn) in (0, 1)
        conn.commit()


def test_rascunho_validate_rejeita_customizada():
    base = rascunho_demo_12_vidas()
    data = json.loads(base.model_dump_json())
    data["regimes_copart"].append(
        {"id": "regime-customizada", "tipo": "customizada", "percentual": None}
    )
    with pytest.raises(ValidationError):
        RascunhoEstudo.model_validate(data)


def test_rotulo_parcial_terapias():
    from newport_app.presentation.rotulos import rotulo_regime

    assert rotulo_regime("parcial") == "Coparticipação parcial (terapias)"
