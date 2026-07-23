"""Migração segura do SQLite operacional — ETAPA 2.6."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def backup_banco(db_path: Path) -> Path:
    if not db_path.is_file():
        return db_path
    backups = db_path.parent / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destino = backups / f"{db_path.stem}_{stamp}.db"
    shutil.copy2(db_path, destino)
    return destino


def migrar_estudos_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.is_file():
        primeiro_arquivo = True
    else:
        primeiro_arquivo = False

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (versao TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)"
        )
        ja_migrado = conn.execute(
            "SELECT versao FROM schema_migrations WHERE versao = ?", ("2.6.0",)
        ).fetchone()
        if not primeiro_arquivo and ja_migrado is None:
            backup_banco(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rascunhos (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                atualizado_em TEXT NOT NULL,
                rascunho_versao TEXT NOT NULL DEFAULT '1.0',
                policy_set_versao TEXT
            )
            """
        )
        _ensure_column(conn, "rascunhos", "rascunho_versao", "TEXT NOT NULL DEFAULT '1.0'")
        _ensure_column(conn, "rascunhos", "policy_set_versao", "TEXT")

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS estudos_meta (
                id TEXT PRIMARY KEY,
                titulo TEXT NOT NULL,
                formato TEXT NOT NULL DEFAULT 'renovacao',
                cliente_nome TEXT,
                ciclo_numero INTEGER NOT NULL DEFAULT 1,
                estado_workflow TEXT NOT NULL DEFAULT 'rascunho',
                criado_em TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS posicao_cadastral_versao (
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

            CREATE TABLE IF NOT EXISTS beneficiario_participacao (
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
                sugestao_vinculo TEXT
            );

            CREATE TABLE IF NOT EXISTS planos_contratados (
                id TEXT PRIMARY KEY,
                estudo_id TEXT NOT NULL,
                opcao_proposta_id TEXT NOT NULL,
                operadora TEXT NOT NULL,
                plano_nome TEXT NOT NULL,
                vigencia_inicio TEXT NOT NULL,
                vigencia_fim TEXT,
                acomodacao TEXT,
                modalidade TEXT,
                regime_copart TEXT,
                copart_percentual INTEGER,
                premio_centavos INTEGER,
                iof_centavos INTEGER,
                total_recorrente_centavos INTEGER,
                tabela_json TEXT NOT NULL,
                documento_origem_id TEXT,
                criado_em TEXT NOT NULL,
                criado_por TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id TEXT PRIMARY KEY,
                estudo_id TEXT NOT NULL,
                estado TEXT NOT NULL,
                hash_sha256 TEXT NOT NULL,
                payload TEXT NOT NULL,
                compiler_versao TEXT NOT NULL,
                motor_versao TEXT NOT NULL,
                policy_set_versao TEXT NOT NULL,
                tem_bloqueio INTEGER NOT NULL DEFAULT 0,
                criado_em TEXT NOT NULL,
                superado_em TEXT
            );

            CREATE TABLE IF NOT EXISTS aprovacoes (
                id TEXT PRIMARY KEY,
                snapshot_id TEXT NOT NULL UNIQUE,
                revisor_nome TEXT NOT NULL,
                aprovado_em TEXT NOT NULL,
                justificativa TEXT,
                auto_aprovacao INTEGER NOT NULL DEFAULT 0,
                invalidada_em TEXT,
                invalidada_motivo TEXT
            );

            CREATE TABLE IF NOT EXISTS entregaveis (
                id TEXT PRIMARY KEY,
                estudo_id TEXT NOT NULL,
                snapshot_id TEXT NOT NULL,
                aprovacao_id TEXT NOT NULL,
                modo TEXT NOT NULL,
                propostas_selecionadas TEXT NOT NULL,
                renderer_versao TEXT NOT NULL,
                hash_conteudo TEXT NOT NULL,
                caminho_arquivo TEXT NOT NULL,
                invalidado INTEGER NOT NULL DEFAULT 0,
                gerado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS auditoria (
                id TEXT PRIMARY KEY,
                estudo_id TEXT NOT NULL,
                entidade TEXT NOT NULL,
                entidade_id TEXT,
                acao TEXT NOT NULL,
                detalhe TEXT,
                criado_em TEXT NOT NULL,
                criado_por TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_posicao_estudo ON posicao_cadastral_versao(estudo_id);
            CREATE INDEX IF NOT EXISTS idx_benef_estudo ON beneficiario_participacao(estudo_id);
            CREATE INDEX IF NOT EXISTS idx_snapshot_estudo ON snapshots(estudo_id);
            CREATE INDEX IF NOT EXISTS idx_entregavel_estudo ON entregaveis(estudo_id);
            """
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (versao TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)"
        )
        row = conn.execute(
            "SELECT versao FROM schema_migrations WHERE versao = ?", ("2.6.0",)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO schema_migrations (versao, aplicada_em) VALUES (?, ?)",
                ("2.6.0", datetime.now(timezone.utc).isoformat()),
            )


def _ensure_column(conn: sqlite3.Connection, tabela: str, coluna: str, definicao: str) -> None:
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})").fetchall()}
    if coluna not in cols:
        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")
