"""Testes HOTFIX 3.0.1 — migração corretiva e confirmação idempotente."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.importacao_siscor import ImportacaoSiscorRepository
from newport_app.repository.migration import migrar_estudos_db
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.importacao_siscor import ImportacaoSiscorService
from tests.fixtures.siscor.xlsx_builder import planilha_41_vidas_2_planos


def _criar_banco_legado_281(db: Path) -> None:
    """Simula banco com 2.8.1 marcada mas participação ainda com beneficiario_logico_id NOT NULL."""
    conn = sqlite3.connect(db)
    agora = datetime.now(timezone.utc).isoformat()
    conn.executescript(
        """
        CREATE TABLE schema_migrations (
            versao TEXT PRIMARY KEY,
            aplicada_em TEXT NOT NULL
        );
        CREATE TABLE rascunhos (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            atualizado_em TEXT NOT NULL,
            rascunho_versao TEXT NOT NULL DEFAULT '1.0',
            policy_set_versao TEXT
        );
        CREATE TABLE estudos_meta (
            id TEXT PRIMARY KEY,
            titulo TEXT NOT NULL,
            formato TEXT NOT NULL DEFAULT 'renovacao',
            cliente_nome TEXT,
            ciclo_numero INTEGER NOT NULL DEFAULT 1,
            estado_workflow TEXT NOT NULL DEFAULT 'rascunho',
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        );
        CREATE TABLE posicao_cadastral_versao (
            id TEXT PRIMARY KEY,
            estudo_id TEXT NOT NULL,
            versao INTEGER NOT NULL,
            origem TEXT NOT NULL,
            documento_hash TEXT,
            importador_versao TEXT,
            criado_em TEXT NOT NULL,
            observacao TEXT,
            UNIQUE(estudo_id, versao)
        );
        CREATE TABLE beneficiario_participacao (
            id TEXT PRIMARY KEY,
            estudo_id TEXT NOT NULL,
            posicao_versao_id TEXT NOT NULL,
            beneficiario_logico_id TEXT NOT NULL,
            vida_rascunho_id TEXT NOT NULL,
            nome TEXT NOT NULL,
            nascimento TEXT NOT NULL,
            parentesco TEXT,
            sexo TEXT,
            status TEXT NOT NULL,
            subgrupo_id TEXT,
            plano_nome TEXT,
            faixa INTEGER,
            valor_centavos INTEGER,
            motivo_alteracao TEXT,
            sugestao_vinculo TEXT,
            beneficiario_id TEXT,
            vinculo_status TEXT NOT NULL DEFAULT 'pendente'
        );
        """
    )
    conn.execute(
        "INSERT INTO schema_migrations (versao, aplicada_em) VALUES (?, ?)",
        ("2.6.0", agora),
    )
    conn.execute(
        "INSERT INTO schema_migrations (versao, aplicada_em) VALUES (?, ?)",
        ("2.8.1", agora),
    )
    conn.execute(
        """
        INSERT INTO posicao_cadastral_versao (
            id, estudo_id, versao, origem, criado_em
        ) VALUES ('pos-1', 'legado', 1, 'manual', ?)
        """,
        (agora,),
    )
    conn.execute(
        """
        INSERT INTO beneficiario_participacao (
            id, estudo_id, posicao_versao_id, beneficiario_logico_id,
            vida_rascunho_id, nome, nascimento, status, vinculo_status
        ) VALUES (
            'part-1', 'legado', 'pos-1', 'bl-legacy',
            'vida-1', 'Beneficiário Legado', '1990-01-01', 'incluido', 'pendente'
        )
        """
    )
    conn.commit()
    conn.close()


def test_migracao_301_corrige_participacao_com_281_marcada(tmp_path: Path):
    db = tmp_path / "legado.db"
    _criar_banco_legado_281(db)

    migrar_estudos_db(db)

    conn = sqlite3.connect(db)
    cols = {r[1]: r for r in conn.execute("PRAGMA table_info(beneficiario_participacao)").fetchall()}
    assert "beneficiario_logico_id" not in cols
    assert "beneficiario_id" in cols
    assert conn.execute("SELECT COUNT(*) FROM beneficiario_participacao").fetchone()[0] == 1
    row = conn.execute(
        "SELECT beneficiario_id FROM beneficiario_participacao WHERE id='part-1'"
    ).fetchone()
    assert row[0] == "bl-legacy"
    assert conn.execute(
        "SELECT 1 FROM schema_migrations WHERE versao='3.0.1'"
    ).fetchone() is not None
    pos_cols = {r[1] for r in conn.execute("PRAGMA table_info(posicao_cadastral_versao)").fetchall()}
    assert "importacao_id" in pos_cols
    conn.close()

    migrar_estudos_db(db)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE versao='3.0.1'").fetchone()[0] == 1
    conn.close()


def test_confirmar_lote_41_vidas_duas_vezes_idempotente(tmp_path: Path):
    db = tmp_path / "estudos.db"
    repo = SQLiteStudyRepository(db)
    imp = ImportacaoSiscorRepository(tmp_path / "importacoes.db")
    historico = HistoricoRepository(db)
    svc = ImportacaoSiscorService(
        repo,
        imp,
        uploads_dir=tmp_path / "uploads",
        historico=historico,
    )

    svc.importar_planilha(
        "est-41-hotfix",
        planilha_41_vidas_2_planos(),
        titulo="41 vidas hotfix",
        modo="substituir",
    )
    r1 = svc.confirmar_lote("est-41-hotfix")
    assert r1.vidas_no_rascunho == 41
    assert r1.historico_registrado is True
    assert r1.posicoes_cadastrais == 1
    assert r1.participacoes_historicas == 41
    assert r1.repeticao is False

    rascunho = repo.obter_rascunho("est-41-hotfix")
    assert rascunho is not None
    assert len(rascunho.vidas) == 41
    assert len(rascunho.subgrupos_atuais) == 2

    r2 = svc.confirmar_lote("est-41-hotfix")
    assert r2.repeticao is True
    assert historico.contar_posicoes("est-41-hotfix") == 1
    assert historico.contar_participacoes("est-41-hotfix") == 41
    assert len(repo.obter_rascunho("est-41-hotfix").vidas) == 41


def test_recuperacao_estudo_real_em_copia(tmp_path: Path):
    origem = Path(".data/newport_app.db")
    if not origem.is_file():
        pytest.skip("Cópia local dos bancos reais indisponível")

    db = tmp_path / "newport_app.db"
    shutil.copy2(origem, db)
    imp_origem = Path(".data/importacoes_demo.db")
    imp_db = tmp_path / "importacoes_demo.db"
    if imp_origem.is_file():
        shutil.copy2(imp_origem, imp_db)

    estudo_id = "est-6ec6d7945a"
    repo = SQLiteStudyRepository(db)
    imp = ImportacaoSiscorRepository(imp_db) if imp_db.is_file() else ImportacaoSiscorRepository(tmp_path / "imp-empty.db")
    historico = HistoricoRepository(db)
    svc = ImportacaoSiscorService(repo, imp, historico=historico)

    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(beneficiario_participacao)").fetchall()}
    assert "beneficiario_logico_id" not in cols
    conn.close()

    r1 = svc.confirmar_lote(estudo_id)
    assert r1.vidas_no_rascunho == 41
    assert r1.historico_registrado is True
    assert historico.contar_posicoes(estudo_id) == 1
    assert historico.contar_participacoes(estudo_id) == 41

    rascunho = repo.obter_rascunho(estudo_id)
    assert len(rascunho.vidas) == 41
    assert len(rascunho.subgrupos_atuais) == 2

    r2 = svc.confirmar_lote(estudo_id)
    assert r2.repeticao is True
    assert historico.contar_posicoes(estudo_id) == 1
    assert historico.contar_participacoes(estudo_id) == 41
