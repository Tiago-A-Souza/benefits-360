"""Repositório de persistência histórica."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.historico import (
    PlanoContratadoVersao,
    PosicaoCadastralVersao,
    RegistrarPlanoContratadoRequest,
)
from newport_app.models.historico import EstudoMeta
from newport_app.repository.migration import migrar_estudos_db


class HistoricoRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        migrar_estudos_db(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def sincronizar_estudo_meta(self, rascunho: RascunhoEstudo) -> EstudoMeta:
        agora = datetime.now(timezone.utc)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM estudos_meta WHERE id = ?", (rascunho.id,)
            ).fetchone()
            cliente = rascunho.empresa_cliente.nome if rascunho.empresa_cliente else None
            if row is None:
                meta = EstudoMeta(
                    id=rascunho.id,
                    titulo=rascunho.titulo,
                    formato=rascunho.formato,
                    cliente_nome=cliente,
                    criado_em=agora,
                    atualizado_em=agora,
                )
                conn.execute(
                    """
                    INSERT INTO estudos_meta (
                        id, titulo, formato, cliente_nome, ciclo_numero,
                        estado_workflow, criado_em, atualizado_em
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        meta.id,
                        meta.titulo,
                        meta.formato,
                        meta.cliente_nome,
                        meta.ciclo_numero,
                        meta.estado_workflow,
                        meta.criado_em.isoformat(),
                        meta.atualizado_em.isoformat(),
                    ),
                )
                return meta
            conn.execute(
                """
                UPDATE estudos_meta SET titulo=?, cliente_nome=?, atualizado_em=?
                WHERE id=?
                """,
                (rascunho.titulo, cliente, agora.isoformat(), rascunho.id),
            )
            return EstudoMeta(
                id=rascunho.id,
                titulo=rascunho.titulo,
                formato=row["formato"],
                cliente_nome=cliente,
                ciclo_numero=row["ciclo_numero"],
                estado_workflow=row["estado_workflow"],
                criado_em=datetime.fromisoformat(row["criado_em"]),
                atualizado_em=agora,
            )

    def registrar_posicao_cadastral(
        self,
        rascunho: RascunhoEstudo,
        *,
        origem: str,
        documento_hash: str | None,
        importador_versao: str | None,
    ) -> PosicaoCadastralVersao:
        agora = datetime.now(timezone.utc)
        self.sincronizar_estudo_meta(rascunho)
        with self._connect() as conn:
            ultima = conn.execute(
                "SELECT MAX(versao) AS v FROM posicao_cadastral_versao WHERE estudo_id=?",
                (rascunho.id,),
            ).fetchone()
            versao = int(ultima["v"] or 0) + 1
            pos_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO posicao_cadastral_versao (
                    id, estudo_id, versao, origem, documento_hash,
                    importador_versao, criado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pos_id,
                    rascunho.id,
                    versao,
                    origem,
                    documento_hash,
                    importador_versao,
                    agora.isoformat(),
                ),
            )
            for vida in rascunho.vidas:
                sugestao = hashlib.sha256(
                    f"{vida.nome}|{vida.nascimento.isoformat()}".encode()
                ).hexdigest()[:16]
                sg = next(
                    (s for s in rascunho.subgrupos_atuais if s.id == vida.subgrupo_atual_id),
                    None,
                )
                conn.execute(
                    """
                    INSERT INTO beneficiario_participacao (
                        id, estudo_id, posicao_versao_id, beneficiario_logico_id,
                        vida_rascunho_id, nome, nascimento, parentesco, status,
                        subgrupo_id, plano_nome, sugestao_vinculo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        rascunho.id,
                        pos_id,
                        f"bl-{sugestao}",
                        vida.id,
                        vida.nome,
                        vida.nascimento.isoformat(),
                        vida.parentesco.value if vida.parentesco else None,
                        "incluido" if vida.incluida else "excluido",
                        vida.subgrupo_atual_id,
                        sg.plano_nome if sg else None,
                        sugestao,
                    ),
                )
        return PosicaoCadastralVersao(
            id=pos_id,
            estudo_id=rascunho.id,
            versao=versao,
            origem=origem,  # type: ignore[arg-type]
            documento_hash=documento_hash,
            importador_versao=importador_versao,
            criado_em=agora,
        )

    def listar_posicoes(self, estudo_id: str) -> list[PosicaoCadastralVersao]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM posicao_cadastral_versao
                WHERE estudo_id=? ORDER BY versao DESC
                """,
                (estudo_id,),
            ).fetchall()
        return [
            PosicaoCadastralVersao(
                id=r["id"],
                estudo_id=r["estudo_id"],
                versao=r["versao"],
                origem=r["origem"],
                documento_hash=r["documento_hash"],
                importador_versao=r["importador_versao"],
                criado_em=datetime.fromisoformat(r["criado_em"]),
                observacao=r["observacao"],
            )
            for r in rows
        ]

    def registrar_plano_contratado(
        self,
        rascunho: RascunhoEstudo,
        req: RegistrarPlanoContratadoRequest,
        *,
        criado_por: str = "analista-local",
    ) -> PlanoContratadoVersao:
        opcao = next(
            (o for o in rascunho.opcoes_proposta if o.id == req.opcao_proposta_id),
            None,
        )
        if opcao is None:
            raise ValueError("Opção de proposta não encontrada.")
        regime = next(
            (r for r in rascunho.regimes_copart if r.id == opcao.regime_copart_id),
            None,
        )
        agora = datetime.now(timezone.utc)
        registro = PlanoContratadoVersao(
            id=str(uuid.uuid4()),
            estudo_id=rascunho.id,
            opcao_proposta_id=opcao.id,
            operadora=opcao.operadora,
            plano_nome=opcao.plano_nome,
            vigencia_inicio=req.vigencia_inicio,
            vigencia_fim=req.vigencia_fim,
            acomodacao=req.acomodacao or opcao.acomodacao,
            modalidade=req.modalidade or (opcao.modalidade.value if opcao.modalidade else None),
            regime_copart=req.regime_copart or (regime.tipo if regime else None),
            copart_percentual=req.copart_percentual,
            premio_centavos=opcao.premio_saude.centavos if opcao.premio_saude else None,
            iof_centavos=opcao.iof.centavos if opcao.iof else None,
            total_recorrente_centavos=(
                opcao.total_recorrente.centavos if opcao.total_recorrente else None
            ),
            tabela_json=json.dumps([f.model_dump(mode="json") for f in opcao.tabela]),
            documento_origem_id=req.documento_origem_id or opcao.documento_cotacao_id,
            criado_em=agora,
            criado_por=criado_por,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO planos_contratados (
                    id, estudo_id, opcao_proposta_id, operadora, plano_nome,
                    vigencia_inicio, vigencia_fim, acomodacao, modalidade,
                    regime_copart, copart_percentual, premio_centavos, iof_centavos,
                    total_recorrente_centavos, tabela_json, documento_origem_id,
                    criado_em, criado_por
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    registro.id,
                    registro.estudo_id,
                    registro.opcao_proposta_id,
                    registro.operadora,
                    registro.plano_nome,
                    registro.vigencia_inicio.isoformat(),
                    registro.vigencia_fim.isoformat() if registro.vigencia_fim else None,
                    registro.acomodacao,
                    registro.modalidade,
                    registro.regime_copart,
                    registro.copart_percentual,
                    registro.premio_centavos,
                    registro.iof_centavos,
                    registro.total_recorrente_centavos,
                    registro.tabela_json,
                    registro.documento_origem_id,
                    registro.criado_em.isoformat(),
                    registro.criado_por,
                ),
            )
        self.registrar_auditoria(
            rascunho.id,
            entidade="plano_contratado",
            entidade_id=registro.id,
            acao="registrar",
            detalhe=f"Plano contratado: {registro.plano_nome}",
            criado_por=criado_por,
        )
        return registro

    def listar_planos_contratados(self, estudo_id: str) -> list[PlanoContratadoVersao]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM planos_contratados WHERE estudo_id=? ORDER BY criado_em DESC",
                (estudo_id,),
            ).fetchall()
        return [
            PlanoContratadoVersao(
                id=r["id"],
                estudo_id=r["estudo_id"],
                opcao_proposta_id=r["opcao_proposta_id"],
                operadora=r["operadora"],
                plano_nome=r["plano_nome"],
                vigencia_inicio=date.fromisoformat(r["vigencia_inicio"]),
                vigencia_fim=date.fromisoformat(r["vigencia_fim"]) if r["vigencia_fim"] else None,
                acomodacao=r["acomodacao"],
                modalidade=r["modalidade"],
                regime_copart=r["regime_copart"],
                copart_percentual=r["copart_percentual"],
                premio_centavos=r["premio_centavos"],
                iof_centavos=r["iof_centavos"],
                total_recorrente_centavos=r["total_recorrente_centavos"],
                tabela_json=r["tabela_json"],
                documento_origem_id=r["documento_origem_id"],
                criado_em=datetime.fromisoformat(r["criado_em"]),
                criado_por=r["criado_por"],
            )
            for r in rows
        ]

    def registrar_auditoria(
        self,
        estudo_id: str,
        *,
        entidade: str,
        entidade_id: str | None,
        acao: str,
        detalhe: str | None,
        criado_por: str = "analista-local",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO auditoria (
                    id, estudo_id, entidade, entidade_id, acao, detalhe, criado_em, criado_por
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    estudo_id,
                    entidade,
                    entidade_id,
                    acao,
                    detalhe,
                    datetime.now(timezone.utc).isoformat(),
                    criado_por,
                ),
            )

    def atualizar_estado_workflow(self, estudo_id: str, estado: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE estudos_meta SET estado_workflow=?, atualizado_em=? WHERE id=?",
                (estado, datetime.now(timezone.utc).isoformat(), estudo_id),
            )
