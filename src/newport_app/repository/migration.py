"""Migração segura do SQLite operacional — ETAPA 2.6."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import uuid
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
        _migrar_283(conn)
        _migrar_284(conn)
        _migrar_285(conn)
        _migrar_301(conn, db_path=db_path)
        _migrar_3b_usuario(conn, db_path=db_path)


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


MOTIVO_REPARO_APROVACAO_UNICA = (
    "Migração 2.8.3 — uma aprovação em vigor por estudo; histórico preservado"
)


def reparar_aprovacoes_vivas_duplicadas(conn: sqlite3.Connection) -> int:
    """Deixa uma aprovação viva por estudo. Idempotente. Não apaga linhas.

    Permanece a de `aprovado_em` mais recente (`snapshots.id` desempata).
    As demais recebem `invalidada_em` e `estado='superado'`. Grava auditoria.
    """
    tabelas = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "snapshots" not in tabelas or "aprovacoes" not in tabelas:
        return 0

    agora = datetime.now(timezone.utc).isoformat()
    estudos = conn.execute(
        """
        SELECT s.estudo_id
        FROM snapshots s
        JOIN aprovacoes a ON a.snapshot_id = s.id
        WHERE s.estado='aprovado' AND a.invalidada_em IS NULL
        GROUP BY s.estudo_id
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    reparados = 0
    for (estudo_id,) in estudos:
        keep_row = conn.execute(
            """
            SELECT s.id FROM snapshots s
            JOIN aprovacoes a ON a.snapshot_id = s.id
            WHERE s.estudo_id=? AND s.estado='aprovado' AND a.invalidada_em IS NULL
            ORDER BY a.aprovado_em DESC, s.id DESC
            LIMIT 1
            """,
            (estudo_id,),
        ).fetchone()
        if keep_row is None:
            continue
        keep_id = keep_row[0]
        conn.execute(
            """
            UPDATE aprovacoes SET invalidada_em=?, invalidada_motivo=?
            WHERE snapshot_id IN (
                SELECT id FROM snapshots WHERE estudo_id=? AND estado='aprovado'
            ) AND invalidada_em IS NULL AND snapshot_id != ?
            """,
            (agora, MOTIVO_REPARO_APROVACAO_UNICA, estudo_id, keep_id),
        )
        conn.execute(
            """
            UPDATE snapshots SET estado='superado', superado_em=?
            WHERE estudo_id=? AND estado='aprovado' AND id != ?
            """,
            (agora, estudo_id, keep_id),
        )
        conn.execute(
            "UPDATE entregaveis SET invalidado=1 WHERE estudo_id=? AND snapshot_id != ?",
            (estudo_id, keep_id),
        )
        if "auditoria" in tabelas:
            conn.execute(
                """
                INSERT INTO auditoria (
                    id, estudo_id, entidade, entidade_id, acao, detalhe, criado_em, criado_por
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    estudo_id,
                    "aprovacao",
                    keep_id,
                    "reparar_aprovacao_unica",
                    MOTIVO_REPARO_APROVACAO_UNICA,
                    agora,
                    "migracao-2.8.3",
                ),
            )
        reparados += 1
    return reparados


def _migrar_283(conn: sqlite3.Connection) -> None:
    """Uma aprovação viva por estudo — repara legado; o GET de governança só lê."""
    ja = conn.execute(
        "SELECT versao FROM schema_migrations WHERE versao = ?", ("2.8.3",)
    ).fetchone()
    if ja is not None:
        return
    reparar_aprovacoes_vivas_duplicadas(conn)
    conn.execute(
        "INSERT INTO schema_migrations (versao, aplicada_em) VALUES (?, ?)",
        ("2.8.3", datetime.now(timezone.utc).isoformat()),
    )


MOTIVO_MIGRACAO_MODALIDADE_ADESAO = (
    "Migração 2.8.4 — modalidade adesão «desconhecido» → «compulsorio»"
)


def migrar_modalidade_desconhecida(conn: sqlite3.Connection) -> int:
    """Converte modalidade «desconhecido» em «compulsorio» nos rascunhos.

    Idempotente. Não toca snapshots. Grava auditoria por estudo alterado.
    Retorna quantos campos (subgrupos + opções) foram convertidos.
    """
    tabelas = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "rascunhos" not in tabelas:
        return 0

    agora = datetime.now(timezone.utc).isoformat()
    convertidos = 0
    rows = conn.execute("SELECT id, payload FROM rascunhos").fetchall()
    for estudo_id, payload in rows:
        data = json.loads(payload)
        alterados: list[str] = []
        for lista in ("subgrupos_atuais", "opcoes_proposta"):
            for item in data.get(lista) or []:
                if item.get("modalidade") != "desconhecido":
                    continue
                item["modalidade"] = "compulsorio"
                convertidos += 1
                alterados.append(f"{lista}:{item.get('id')}")
        if not alterados:
            continue
        conn.execute(
            "UPDATE rascunhos SET payload = ?, atualizado_em = ? WHERE id = ?",
            (
                json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                agora,
                estudo_id,
            ),
        )
        if "auditoria" in tabelas:
            conn.execute(
                """
                INSERT INTO auditoria (
                    id, estudo_id, entidade, entidade_id, acao, detalhe, criado_em, criado_por
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    estudo_id,
                    "rascunho",
                    estudo_id,
                    "migrar_modalidade_adesao",
                    f"{MOTIVO_MIGRACAO_MODALIDADE_ADESAO}; {', '.join(alterados)}",
                    agora,
                    "migracao-2.8.4",
                ),
            )
    return convertidos


def _migrar_284(conn: sqlite3.Connection) -> None:
    """Remove «desconhecido» da adesão — converte legado para compulsório."""
    ja = conn.execute(
        "SELECT versao FROM schema_migrations WHERE versao = ?", ("2.8.4",)
    ).fetchone()
    if ja is not None:
        return
    migrar_modalidade_desconhecida(conn)
    conn.execute(
        "INSERT INTO schema_migrations (versao, aplicada_em) VALUES (?, ?)",
        ("2.8.4", datetime.now(timezone.utc).isoformat()),
    )


MOTIVO_MIGRACAO_REGIME_CUSTOMIZADA = (
    "Migração 2.8.5 — remove regime de coparticipação «customizada» órfão do catálogo"
)


class RegimeCustomizadaEmUsoError(RuntimeError):
    """Subgrupo ou opção ainda aponta para um regime customizada — migração abortada."""


def migrar_regime_customizada(conn: sqlite3.Connection) -> int:
    """Remove entradas «customizada» do catálogo regimes_copart nos rascunhos.

    Idempotente. Não toca snapshots. Aborta se algum subgrupo/opção referenciar
    o id removido. Retorna quantos itens de catálogo foram removidos.
    """
    tabelas = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "rascunhos" not in tabelas:
        return 0

    agora = datetime.now(timezone.utc).isoformat()
    removidos = 0
    rows = conn.execute("SELECT id, payload FROM rascunhos").fetchall()
    for estudo_id, payload in rows:
        data = json.loads(payload)
        regimes = list(data.get("regimes_copart") or [])
        custom = [
            r
            for r in regimes
            if r.get("tipo") == "customizada"
            or str(r.get("id") or "").startswith("regime-customizada")
        ]
        if not custom:
            continue
        ids_custom = {r.get("id") for r in custom if r.get("id")}
        for lista in ("subgrupos_atuais", "opcoes_proposta"):
            for item in data.get(lista) or []:
                rid = item.get("regime_copart_id")
                if rid in ids_custom:
                    raise RegimeCustomizadaEmUsoError(
                        f"Estudo {estudo_id}: {lista} {item.get('id')} "
                        f"ainda referencia {rid}"
                    )
        novos = [r for r in regimes if r.get("id") not in ids_custom]
        removidos += len(regimes) - len(novos)
        data["regimes_copart"] = novos
        conn.execute(
            "UPDATE rascunhos SET payload = ?, atualizado_em = ? WHERE id = ?",
            (
                json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                agora,
                estudo_id,
            ),
        )
        if "auditoria" in tabelas:
            ids_txt = ", ".join(sorted(ids_custom))
            conn.execute(
                """
                INSERT INTO auditoria (
                    id, estudo_id, entidade, entidade_id, acao, detalhe, criado_em, criado_por
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    estudo_id,
                    "rascunho",
                    estudo_id,
                    "migrar_regime_customizada",
                    f"{MOTIVO_MIGRACAO_REGIME_CUSTOMIZADA}; removidos: {ids_txt}",
                    agora,
                    "migracao-2.8.5",
                ),
            )
    return removidos


def _migrar_285(conn: sqlite3.Connection) -> None:
    """Remove «customizada» do catálogo de regimes — só órfãos."""
    ja = conn.execute(
        "SELECT versao FROM schema_migrations WHERE versao = ?", ("2.8.5",)
    ).fetchone()
    if ja is not None:
        return
    migrar_regime_customizada(conn)
    conn.execute(
        "INSERT INTO schema_migrations (versao, aplicada_em) VALUES (?, ?)",
        ("2.8.5", datetime.now(timezone.utc).isoformat()),
    )


def _ensure_column(conn: sqlite3.Connection, tabela: str, coluna: str, definicao: str) -> None:
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})").fetchall()}
    if coluna not in cols:
        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")


TABELAS_POR_USUARIO = (
    "estudos_meta",
    "rascunhos",
    "posicao_cadastral_versao",
    "beneficiario_participacao",
    "beneficiarios",
    "clientes",
    "ciclos_renovacao",
    "planos_contratados",
    "snapshots",
    "aprovacoes",
    "entregaveis",
    "auditoria",
)

TABELAS_POR_USUARIO_COTACOES = ("extracoes_cotacao",)
TABELAS_POR_USUARIO_IMPORTACOES = ("importacoes_siscor",)


def valor_backfill_usuario() -> str | None:
    """Dono dos registros antigos. Só lê BENEFITS_DONO_LEGADO_ID do ambiente.

    Fora do demo, se a variável não estiver definida, os legados ficam com
    usuario_id NULL e invisíveis para todos até ela ser definida.
    No demo, o backfill usa o usuário fixo 'demo'.
    """
    legado = (os.environ.get("BENEFITS_DONO_LEGADO_ID") or "").strip()
    if legado:
        return legado
    from newport_app.config.runtime import ModoExecucao, modo_execucao

    if modo_execucao() == ModoExecucao.DEMO:
        return "demo"
    return None


def aplicar_coluna_usuario(conn: sqlite3.Connection, tabelas: tuple[str, ...]) -> None:
    existentes = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for tabela in tabelas:
        if tabela not in existentes:
            continue
        _ensure_column(conn, tabela, "usuario_id", "TEXT")
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{tabela}_usuario_id ON {tabela}(usuario_id)"
        )
    dono = valor_backfill_usuario()
    if not dono:
        return
    for tabela in tabelas:
        if tabela not in existentes:
            continue
        conn.execute(
            f"UPDATE {tabela} SET usuario_id = ? WHERE usuario_id IS NULL",
            (dono,),
        )


def _migrar_3b_usuario(conn: sqlite3.Connection, *, db_path: Path) -> None:
    ja = conn.execute(
        "SELECT versao FROM schema_migrations WHERE versao = ?", ("3.1.0",)
    ).fetchone()
    if ja is not None:
        aplicar_coluna_usuario(conn, TABELAS_POR_USUARIO)
        return
    destino = backup_banco(db_path) if db_path.is_file() else None
    aplicar_coluna_usuario(conn, TABELAS_POR_USUARIO)
    conn.execute(
        "INSERT INTO schema_migrations (versao, aplicada_em) VALUES (?, ?)",
        ("3.1.0", datetime.now(timezone.utc).isoformat()),
    )
    if destino is not None:
        print(
            f"Migração 3.1.0: usuario_id aplicado; backup em {destino}",
            flush=True,
        )
    else:
        print("Migração 3.1.0: usuario_id aplicado (banco novo, sem backup).", flush=True)


def migrar_banco_cotacoes(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        aplicar_coluna_usuario(conn, TABELAS_POR_USUARIO_COTACOES)


def migrar_banco_importacoes(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        aplicar_coluna_usuario(conn, TABELAS_POR_USUARIO_IMPORTACOES)
