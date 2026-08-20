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

        _migrar_281(conn)
        _migrar_282(conn)
        _migrar_301(conn, db_path=db_path)


def _participacao_precisa_correcao(conn: sqlite3.Connection) -> bool:
    cols = {
        r[1]: r
        for r in conn.execute("PRAGMA table_info(beneficiario_participacao)").fetchall()
    }
    if not cols:
        return False
    if "beneficiario_logico_id" in cols:
        return True
    if "beneficiario_id" not in cols or "vinculo_status" not in cols:
        return True
    return False


def _ensure_idx_posicao_importacao(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_posicao_estudo_importacao
        ON posicao_cadastral_versao(estudo_id, importacao_id)
        WHERE importacao_id IS NOT NULL
        """
    )


def _recriar_beneficiario_participacao(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS beneficiario_participacao_new")
    cols = {
        r[1]: r
        for r in conn.execute("PRAGMA table_info(beneficiario_participacao)").fetchall()
    }
    has_logico = "beneficiario_logico_id" in cols

    conn.executescript(
        """
        CREATE TABLE beneficiario_participacao_new (
            id TEXT PRIMARY KEY,
            estudo_id TEXT NOT NULL,
            posicao_versao_id TEXT NOT NULL,
            beneficiario_id TEXT,
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
            vinculo_status TEXT NOT NULL DEFAULT 'pendente'
        );
        """
    )
    if has_logico:
        conn.execute(
            """
            INSERT INTO beneficiario_participacao_new (
                id, estudo_id, posicao_versao_id, beneficiario_id, vida_rascunho_id,
                nome, nascimento, parentesco, sexo, status, subgrupo_id, plano_nome,
                faixa, valor_centavos, motivo_alteracao, sugestao_vinculo, vinculo_status
            )
            SELECT
                id, estudo_id, posicao_versao_id,
                COALESCE(beneficiario_id, beneficiario_logico_id),
                vida_rascunho_id, nome, nascimento, parentesco, sexo,
                status, subgrupo_id, plano_nome, faixa, valor_centavos,
                motivo_alteracao, sugestao_vinculo,
                COALESCE(vinculo_status, 'pendente')
            FROM beneficiario_participacao
            """
        )
    else:
        conn.execute(
            """
            INSERT INTO beneficiario_participacao_new (
                id, estudo_id, posicao_versao_id, beneficiario_id, vida_rascunho_id,
                nome, nascimento, parentesco, sexo, status, subgrupo_id, plano_nome,
                faixa, valor_centavos, motivo_alteracao, sugestao_vinculo, vinculo_status
            )
            SELECT
                id, estudo_id, posicao_versao_id, beneficiario_id, vida_rascunho_id,
                nome, nascimento, parentesco, sexo, status, subgrupo_id, plano_nome,
                faixa, valor_centavos, motivo_alteracao, sugestao_vinculo,
                COALESCE(vinculo_status, 'pendente')
            FROM beneficiario_participacao
            """
        )
    conn.execute("DROP TABLE beneficiario_participacao")
    conn.execute("ALTER TABLE beneficiario_participacao_new RENAME TO beneficiario_participacao")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_benef_estudo ON beneficiario_participacao(estudo_id)"
    )


def _migrar_301(conn: sqlite3.Connection, *, db_path: Path) -> None:
    """Correção 3.0.1 — estrutura real de participação e importacao_id em posição."""
    ja_aplicada = (
        conn.execute(
            "SELECT versao FROM schema_migrations WHERE versao = ?", ("3.0.1",)
        ).fetchone()
        is not None
    )
    precisa = _participacao_precisa_correcao(conn)

    if ja_aplicada and not precisa:
        _ensure_column(conn, "posicao_cadastral_versao", "importacao_id", "TEXT")
        _ensure_idx_posicao_importacao(conn)
        return

    if precisa:
        backup_banco(db_path)
        _recriar_beneficiario_participacao(conn)

    _ensure_column(conn, "posicao_cadastral_versao", "importacao_id", "TEXT")
    _ensure_idx_posicao_importacao(conn)
    if not ja_aplicada:
        conn.execute(
            "INSERT INTO schema_migrations (versao, aplicada_em) VALUES (?, ?)",
            ("3.0.1", datetime.now(timezone.utc).isoformat()),
        )


def _migrar_281(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT versao FROM schema_migrations WHERE versao = ?", ("2.8.1",)
    ).fetchone()
    if row is not None:
        return

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS clientes (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            criado_em TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ciclos_renovacao (
            id TEXT PRIMARY KEY,
            cliente_id TEXT NOT NULL,
            numero INTEGER NOT NULL,
            vigencia_inicio TEXT,
            vigencia_fim TEXT,
            criado_em TEXT NOT NULL,
            UNIQUE(cliente_id, numero)
        );

        CREATE TABLE IF NOT EXISTS beneficiarios (
            id TEXT PRIMARY KEY,
            cliente_id TEXT NOT NULL,
            nome TEXT NOT NULL,
            nascimento TEXT NOT NULL,
            parentesco TEXT,
            sexo TEXT,
            criado_em TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_benef_cliente ON beneficiarios(cliente_id);
        CREATE INDEX IF NOT EXISTS idx_ciclo_cliente ON ciclos_renovacao(cliente_id);
        """
    )
    _ensure_column(conn, "estudos_meta", "cliente_id", "TEXT")
    _ensure_column(conn, "estudos_meta", "ciclo_id", "TEXT")
    _ensure_column(conn, "beneficiario_participacao", "beneficiario_id", "TEXT")
    _ensure_column(
        conn,
        "beneficiario_participacao",
        "vinculo_status",
        "TEXT NOT NULL DEFAULT 'pendente'",
    )
    _ensure_column(conn, "planos_contratados", "ciclo_id", "TEXT")

    # Recria participação sem beneficiario_logico_id obrigatório (legado 2.6)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(beneficiario_participacao)").fetchall()}
    if "beneficiario_logico_id" in cols:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS beneficiario_participacao_new (
                id TEXT PRIMARY KEY,
                estudo_id TEXT NOT NULL,
                posicao_versao_id TEXT NOT NULL,
                beneficiario_id TEXT,
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
                vinculo_status TEXT NOT NULL DEFAULT 'pendente'
            );
            INSERT INTO beneficiario_participacao_new (
                id, estudo_id, posicao_versao_id, beneficiario_id, vida_rascunho_id,
                nome, nascimento, parentesco, sexo, status, subgrupo_id, plano_nome,
                faixa, valor_centavos, motivo_alteracao, sugestao_vinculo, vinculo_status
            )
            SELECT
                id, estudo_id, posicao_versao_id,
                beneficiario_id, vida_rascunho_id, nome, nascimento, parentesco, sexo,
                status, subgrupo_id, plano_nome, faixa, valor_centavos,
                motivo_alteracao, sugestao_vinculo,
                COALESCE(vinculo_status, 'pendente')
            FROM beneficiario_participacao;
            DROP TABLE beneficiario_participacao;
            ALTER TABLE beneficiario_participacao_new RENAME TO beneficiario_participacao;
            CREATE INDEX IF NOT EXISTS idx_benef_estudo ON beneficiario_participacao(estudo_id);
            """
        )

    conn.execute(
        "INSERT INTO schema_migrations (versao, aplicada_em) VALUES (?, ?)",
        ("2.8.1", datetime.now(timezone.utc).isoformat()),
    )


def _migrar_282(conn: sqlite3.Connection) -> None:
    """Persiste snapshot_versao — formato do payload canônico, distinto de motor_versao."""
    _ensure_column(conn, "snapshots", "snapshot_versao", "TEXT")
    ja = conn.execute(
        "SELECT versao FROM schema_migrations WHERE versao = ?", ("2.8.2",)
    ).fetchone()
    if ja is None:
        conn.execute(
            "INSERT INTO schema_migrations (versao, aplicada_em) VALUES (?, ?)",
            ("2.8.2", datetime.now(timezone.utc).isoformat()),
        )


def _ensure_column(conn: sqlite3.Connection, tabela: str, coluna: str, definicao: str) -> None:
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})").fetchall()}
    if coluna not in cols:
        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")
