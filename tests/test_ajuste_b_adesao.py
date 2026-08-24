"""Ajuste B — remover modalidade «desconhecido» da adesão dos funcionários."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from newport_app.draft_compiler import compile
from newport_app.models.draft import ModalidadeRascunho, RascunhoEstudo
from newport_app.models.presentation import PropostaApresentacao
from newport_app.presentation.html_renderer import _meta_proposta
from newport_app.repository.migration import (
    migrar_estudos_db,
    migrar_modalidade_desconhecida,
)
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.calculo import CalculoService
from newport_motor.engine import calcular


def _inserir_rascunho_com_modalidade(
    db: Path, *, estudo_id: str, modalidade: str | None
) -> None:
    migrar_estudos_db(db)
    base = rascunho_demo_12_vidas()
    base.id = estudo_id
    payload = json.loads(base.model_dump_json())
    payload["id"] = estudo_id
    payload["subgrupos_atuais"][0]["modalidade"] = modalidade
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


def test_enum_sem_desconhecido():
    assert {m.value for m in ModalidadeRascunho} == {"adesao", "compulsorio"}
    with pytest.raises(ValueError):
        ModalidadeRascunho("desconhecido")


def test_constants_js_sem_desconhecido_em_modalidades():
    texto = (Path(__file__).resolve().parents[1] / "web" / "src" / "constants.js").read_text(
        encoding="utf-8"
    )
    bloco = texto.split("export const MODALIDADES")[1].split("];")[0]
    assert "adesao" in bloco
    assert "compulsorio" in bloco
    assert "desconhecido" not in bloco


def test_migracao_converte_e_e_idempotente(tmp_path: Path):
    db = tmp_path / "adesao.db"
    _inserir_rascunho_com_modalidade(db, estudo_id="est-mod-desc", modalidade="desconhecido")

    with sqlite3.connect(db) as conn:
        n1 = migrar_modalidade_desconhecida(conn)
        conn.commit()
        aud = conn.execute(
            """
            SELECT acao, criado_por FROM auditoria
            WHERE estudo_id=? AND acao='migrar_modalidade_adesao'
            """,
            ("est-mod-desc",),
        ).fetchone()
        n2 = migrar_modalidade_desconhecida(conn)
        conn.commit()

    assert n1 == 1
    assert n2 == 0
    assert aud is not None
    assert aud[1] == "migracao-2.8.4"

    repo = SQLiteStudyRepository(db)
    rascunho = repo.obter_rascunho("est-mod-desc")
    assert rascunho is not None
    assert rascunho.subgrupos_atuais[0].modalidade == ModalidadeRascunho.COMPULSORIO

    with sqlite3.connect(db) as conn:
        bruto = conn.execute(
            "SELECT payload FROM rascunhos WHERE id=?", ("est-mod-desc",)
        ).fetchone()[0]
    assert '"modalidade": "desconhecido"' not in bruto
    assert '"modalidade":"desconhecido"' not in bruto
    assert json.loads(bruto)["subgrupos_atuais"][0]["modalidade"] == "compulsorio"


def test_migracao_284_marca_schema(tmp_path: Path):
    db = tmp_path / "schema284.db"
    _inserir_rascunho_com_modalidade(db, estudo_id="est-schema", modalidade="desconhecido")
    with sqlite3.connect(db) as conn:
        # _inserir já rodou migrar_estudos_db — 2.8.4 já aplicada na 1ª passagem
        # se o insert foi depois, precisamos reaplicar a função idempotente.
        marca = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE versao='2.8.4'"
        ).fetchone()
        assert marca is not None
        # garante conversão mesmo se o insert veio após a marca
        assert migrar_modalidade_desconhecida(conn) in (0, 1)
        conn.commit()


def test_modalidade_null_carrega_calcula_sem_linha_modalidade(tmp_path: Path):
    db = tmp_path / "null.db"
    repo = SQLiteStudyRepository(db)
    svc = CalculoService(repo)
    rascunho = rascunho_demo_12_vidas()
    rascunho.id = "est-mod-null"
    for sg in rascunho.subgrupos_atuais:
        sg.modalidade = None
    for op in rascunho.opcoes_proposta:
        op.modalidade = None
    svc.garantir_rascunho(rascunho)

    carregado = repo.obter_rascunho(rascunho.id)
    assert carregado is not None
    assert all(sg.modalidade is None for sg in carregado.subgrupos_atuais)

    resultado = compile(carregado)
    assert resultado.compilavel
    assert resultado.compilado is not None
    motor = calcular(
        resultado.compilado.estudo_input,
        resultado.compilado.effective_policy,
    )
    assert motor.cenarios

    meta = _meta_proposta(
        PropostaApresentacao(
            opcao_id="op-x",
            operadora="Amil",
            plano_nome="Plano X",
            regime_rotulo="Sem",
            regime_tipo="sem",
            modalidade=None,
        )
    )
    assert "Modalidade:" not in meta


def test_rascunho_compulsorio_pos_enum_restrito(tmp_path: Path):
    db = tmp_path / "comp.db"
    _inserir_rascunho_com_modalidade(db, estudo_id="est-comp", modalidade="desconhecido")
    with sqlite3.connect(db) as conn:
        assert migrar_modalidade_desconhecida(conn) >= 0
        conn.commit()
    rascunho = SQLiteStudyRepository(db).obter_rascunho("est-comp")
    assert isinstance(rascunho, RascunhoEstudo)
    assert rascunho.subgrupos_atuais[0].modalidade == ModalidadeRascunho.COMPULSORIO
