"""Repositório de persistência histórica longitudinal — ETAPA 2.8.1."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.historico import (
    BeneficiarioLogico,
    BeneficiarioParticipacao,
    CicloRenovacao,
    Cliente,
    ConfirmarVinculoRequest,
    EstudoMeta,
    HistoricoEstudoResponse,
    PlanoContratadoVersao,
    PosicaoCadastralVersao,
    RegistrarPlanoContratadoRequest,
    SugestaoVinculoBeneficiario,
    VincularEstudoRequest,
)
from newport_app.repository.migration import migrar_estudos_db
from newport_motor.faixa import faixa_em


class HistoricoRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        migrar_estudos_db(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _sugestao_hash(nome: str, nascimento: date, parentesco: str | None) -> str:
        return hashlib.sha256(
            f"{nome.strip().lower()}|{nascimento.isoformat()}|{parentesco or ''}".encode()
        ).hexdigest()[:16]

    def criar_cliente(self, nome: str) -> Cliente:
        agora = datetime.now(timezone.utc)
        cliente = Cliente(id=str(uuid.uuid4()), nome=nome.strip(), criado_em=agora)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO clientes (id, nome, criado_em) VALUES (?, ?, ?)",
                (cliente.id, cliente.nome, agora.isoformat()),
            )
        return cliente

    def listar_clientes(self) -> list[Cliente]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM clientes ORDER BY nome").fetchall()
        return [
            Cliente(
                id=r["id"],
                nome=r["nome"],
                criado_em=datetime.fromisoformat(r["criado_em"]),
            )
            for r in rows
        ]

    def criar_ciclo(
        self,
        cliente_id: str,
        numero: int,
        *,
        vigencia_inicio: date | None = None,
        vigencia_fim: date | None = None,
    ) -> CicloRenovacao:
        agora = datetime.now(timezone.utc)
        ciclo = CicloRenovacao(
            id=str(uuid.uuid4()),
            cliente_id=cliente_id,
            numero=numero,
            vigencia_inicio=vigencia_inicio,
            vigencia_fim=vigencia_fim,
            criado_em=agora,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ciclos_renovacao (
                    id, cliente_id, numero, vigencia_inicio, vigencia_fim, criado_em
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    ciclo.id,
                    ciclo.cliente_id,
                    ciclo.numero,
                    ciclo.vigencia_inicio.isoformat() if ciclo.vigencia_inicio else None,
                    ciclo.vigencia_fim.isoformat() if ciclo.vigencia_fim else None,
                    agora.isoformat(),
                ),
            )
        return ciclo

    def listar_ciclos(self, cliente_id: str) -> list[CicloRenovacao]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ciclos_renovacao WHERE cliente_id=? ORDER BY numero DESC",
                (cliente_id,),
            ).fetchall()
        return [
            CicloRenovacao(
                id=r["id"],
                cliente_id=r["cliente_id"],
                numero=r["numero"],
                vigencia_inicio=(
                    date.fromisoformat(r["vigencia_inicio"]) if r["vigencia_inicio"] else None
                ),
                vigencia_fim=date.fromisoformat(r["vigencia_fim"]) if r["vigencia_fim"] else None,
                criado_em=datetime.fromisoformat(r["criado_em"]),
            )
            for r in rows
        ]

    def vincular_estudo(self, estudo_id: str, req: VincularEstudoRequest) -> EstudoMeta:
        with self._connect() as conn:
            ciclo_id = req.ciclo_id
            if req.criar_ciclo:
                ultimo = conn.execute(
                    "SELECT MAX(numero) AS n FROM ciclos_renovacao WHERE cliente_id=?",
                    (req.cliente_id,),
                ).fetchone()
                numero = req.ciclo_numero or int(ultimo["n"] or 0) + 1
                ciclo = self.criar_ciclo(req.cliente_id, numero)
                ciclo_id = ciclo.id
            conn.execute(
                "UPDATE estudos_meta SET cliente_id=?, ciclo_id=?, atualizado_em=? WHERE id=?",
                (
                    req.cliente_id,
                    ciclo_id,
                    datetime.now(timezone.utc).isoformat(),
                    estudo_id,
                ),
            )
        meta = self.obter_estudo_meta(estudo_id)
        if meta is None:
            raise ValueError("Estudo não encontrado.")
        return meta

    def obter_estudo_meta(self, estudo_id: str) -> EstudoMeta | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM estudos_meta WHERE id=?", (estudo_id,)).fetchone()
        if row is None:
            return None
        return self._row_estudo_meta(row)

    def sincronizar_estudo_meta(self, rascunho: RascunhoEstudo) -> EstudoMeta:
        agora = datetime.now(timezone.utc)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM estudos_meta WHERE id = ?", (rascunho.id,)
            ).fetchone()
            cliente_nome = rascunho.empresa_cliente.nome if rascunho.empresa_cliente else None
            if row is None:
                meta = EstudoMeta(
                    id=rascunho.id,
                    titulo=rascunho.titulo,
                    formato=rascunho.formato,
                    cliente_nome=cliente_nome,
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
                if cliente_nome:
                    self._garantir_cliente_por_nome(conn, rascunho.id, cliente_nome, agora)
                return meta
            conn.execute(
                """
                UPDATE estudos_meta SET titulo=?, cliente_nome=?, atualizado_em=?
                WHERE id=?
                """,
                (rascunho.titulo, cliente_nome, agora.isoformat(), rascunho.id),
            )
            if cliente_nome and not row["cliente_id"]:
                self._garantir_cliente_por_nome(conn, rascunho.id, cliente_nome, agora)
            return self._row_estudo_meta(
                conn.execute("SELECT * FROM estudos_meta WHERE id=?", (rascunho.id,)).fetchone()
            )

    def _garantir_cliente_por_nome(
        self,
        conn: sqlite3.Connection,
        estudo_id: str,
        nome: str,
        agora: datetime,
    ) -> None:
        row = conn.execute("SELECT id FROM clientes WHERE nome=?", (nome,)).fetchone()
        if row:
            cliente_id = row["id"]
        else:
            cliente_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO clientes (id, nome, criado_em) VALUES (?, ?, ?)",
                (cliente_id, nome, agora.isoformat()),
            )
        ciclo_row = conn.execute(
            "SELECT id FROM ciclos_renovacao WHERE cliente_id=? ORDER BY numero DESC LIMIT 1",
            (cliente_id,),
        ).fetchone()
        if ciclo_row:
            ciclo_id = ciclo_row["id"]
        else:
            ciclo_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO ciclos_renovacao (id, cliente_id, numero, criado_em)
                VALUES (?, ?, 1, ?)
                """,
                (ciclo_id, cliente_id, agora.isoformat()),
            )
        conn.execute(
            "UPDATE estudos_meta SET cliente_id=?, ciclo_id=? WHERE id=?",
            (cliente_id, ciclo_id, estudo_id),
        )

    def _faixa_valor_vida(self, rascunho: RascunhoEstudo, vida_id: str) -> tuple[int | None, int | None]:
        vida = next((v for v in rascunho.vidas if v.id == vida_id), None)
        if vida is None:
            return None, None
        faixa = None
        if rascunho.escolhas.data_referencia_idade:
            _, faixa = faixa_em(vida.nascimento, rascunho.escolhas.data_referencia_idade)
        valor = None
        if vida.valor_fatura:
            valor = vida.valor_fatura.centavos
        elif vida.valor_conferencia:
            valor = vida.valor_conferencia.centavos
        return faixa, valor

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
            meta = conn.execute(
                "SELECT cliente_id FROM estudos_meta WHERE id=?", (rascunho.id,)
            ).fetchone()
            cliente_id = meta["cliente_id"] if meta else None

            for vida in rascunho.vidas:
                parentesco = vida.parentesco.value if vida.parentesco else None
                sugestao = self._sugestao_hash(vida.nome, vida.nascimento, parentesco)
                sg = next(
                    (s for s in rascunho.subgrupos_atuais if s.id == vida.subgrupo_atual_id),
                    None,
                )
                faixa, valor = self._faixa_valor_vida(rascunho, vida.id)
                participacao_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO beneficiario_participacao (
                        id, estudo_id, posicao_versao_id, beneficiario_id,
                        vida_rascunho_id, nome, nascimento, parentesco, status,
                        subgrupo_id, plano_nome, faixa, valor_centavos,
                        sugestao_vinculo, vinculo_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        participacao_id,
                        rascunho.id,
                        pos_id,
                        None,
                        vida.id,
                        vida.nome,
                        vida.nascimento.isoformat(),
                        parentesco,
                        "incluido" if vida.incluida else "excluido",
                        vida.subgrupo_atual_id,
                        sg.plano_nome if sg else None,
                        faixa,
                        valor,
                        sugestao,
                        "pendente",
                    ),
                )
                if cliente_id:
                    self._registrar_sugestao_vinculo(
                        conn, participacao_id, cliente_id, sugestao, vida.nome, vida.nascimento, parentesco
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

    def _registrar_sugestao_vinculo(
        self,
        conn: sqlite3.Connection,
        participacao_id: str,
        cliente_id: str,
        sugestao: str,
        nome: str,
        nascimento: date,
        parentesco: str | None,
    ) -> None:
        candidato = conn.execute(
            """
            SELECT id FROM beneficiarios
            WHERE cliente_id=? AND nome=? AND nascimento=?
            AND (parentesco IS ? OR parentesco=?)
            """,
            (cliente_id, nome, nascimento.isoformat(), parentesco, parentesco),
        ).fetchone()
        if candidato is None:
            return
        conn.execute(
            """
            UPDATE beneficiario_participacao SET sugestao_vinculo=?
            WHERE id=?
            """,
            (f"sug-{candidato['id']}", participacao_id),
        )

    def confirmar_vinculo(self, req: ConfirmarVinculoRequest) -> BeneficiarioParticipacao:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM beneficiario_participacao WHERE id=?",
                (req.participacao_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Participação não encontrada.")
            meta = conn.execute(
                "SELECT cliente_id FROM estudos_meta WHERE id=?", (row["estudo_id"],)
            ).fetchone()
            cliente_id = meta["cliente_id"] if meta else None
            if req.acao == "novo":
                if not cliente_id:
                    raise ValueError("Estudo sem cliente vinculado.")
                benef_id = str(uuid.uuid4())
                agora = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    """
                    INSERT INTO beneficiarios (
                        id, cliente_id, nome, nascimento, parentesco, criado_em
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        benef_id,
                        cliente_id,
                        row["nome"],
                        row["nascimento"],
                        row["parentesco"],
                        agora,
                    ),
                )
                conn.execute(
                    """
                    UPDATE beneficiario_participacao
                    SET beneficiario_id=?, vinculo_status='novo'
                    WHERE id=?
                    """,
                    (benef_id, req.participacao_id),
                )
            elif req.acao == "confirmar":
                if not req.beneficiario_id:
                    raise ValueError("Informe o beneficiário para confirmar.")
                conn.execute(
                    """
                    UPDATE beneficiario_participacao
                    SET beneficiario_id=?, vinculo_status='confirmado'
                    WHERE id=?
                    """,
                    (req.beneficiario_id, req.participacao_id),
                )
            elif req.acao == "rejeitar":
                conn.execute(
                    """
                    UPDATE beneficiario_participacao
                    SET beneficiario_id=NULL, vinculo_status='rejeitado'
                    WHERE id=?
                    """,
                    (req.participacao_id,),
                )
            updated = conn.execute(
                "SELECT * FROM beneficiario_participacao WHERE id=?",
                (req.participacao_id,),
            ).fetchone()
        return self._row_participacao(updated)

    def confirmar_vinculos_coerentes(self, participacao_ids: list[str]) -> int:
        confirmados = 0
        with self._connect() as conn:
            for pid in participacao_ids:
                row = conn.execute(
                    "SELECT * FROM beneficiario_participacao WHERE id=?", (pid,)
                ).fetchone()
                if row is None or not row["sugestao_vinculo"]:
                    continue
                if not str(row["sugestao_vinculo"]).startswith("sug-"):
                    continue
                benef_id = str(row["sugestao_vinculo"])[4:]
                conn.execute(
                    """
                    UPDATE beneficiario_participacao
                    SET beneficiario_id=?, vinculo_status='confirmado'
                    WHERE id=?
                    """,
                    (benef_id, pid),
                )
                confirmados += 1
        return confirmados

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

    def listar_participacoes(
        self, estudo_id: str, posicao_versao_id: str | None = None
    ) -> list[BeneficiarioParticipacao]:
        with self._connect() as conn:
            if posicao_versao_id:
                rows = conn.execute(
                    """
                    SELECT * FROM beneficiario_participacao
                    WHERE estudo_id=? AND posicao_versao_id=?
                    ORDER BY nome
                    """,
                    (estudo_id, posicao_versao_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM beneficiario_participacao
                    WHERE estudo_id=?
                    ORDER BY nome
                    """,
                    (estudo_id,),
                ).fetchall()
        return [self._row_participacao(r) for r in rows]

    def obter_historico_estudo(self, estudo_id: str) -> HistoricoEstudoResponse:
        meta = self.obter_estudo_meta(estudo_id)
        if meta is None:
            raise ValueError("Estudo não encontrado.")
        posicoes = self.listar_posicoes(estudo_id)
        participacoes = self.listar_participacoes(estudo_id)
        planos = self.listar_planos_contratados(estudo_id)
        sugestoes = self._montar_sugestoes(participacoes)
        ultimo = planos[0] if planos else None
        if ultimo is None and meta.cliente_id:
            ultimo = self.obter_ultimo_plano_cliente(meta.cliente_id, excluir_estudo=estudo_id)
        return HistoricoEstudoResponse(
            estudo=meta,
            posicoes=posicoes,
            participacoes=participacoes,
            planos_contratados=planos,
            ultimo_plano_contratado=ultimo,
            sugestoes_vinculo=sugestoes,
        )

    def _montar_sugestoes(
        self, participacoes: list[BeneficiarioParticipacao]
    ) -> list[SugestaoVinculoBeneficiario]:
        sugestoes: list[SugestaoVinculoBeneficiario] = []
        for p in participacoes:
            if p.vinculo_status != "pendente" or not p.sugestao_vinculo:
                continue
            candidato = None
            if p.sugestao_vinculo.startswith("sug-"):
                candidato = p.sugestao_vinculo[4:]
            sugestoes.append(
                SugestaoVinculoBeneficiario(
                    participacao_id=p.id,
                    sugestao_hash=p.sugestao_vinculo,
                    beneficiario_candidato_id=candidato,
                    confianca="baixa",
                    motivo="Correspondência por nome, nascimento e parentesco — requer confirmação.",
                )
            )
        return sugestoes

    def obter_ultimo_plano_cliente(
        self, cliente_id: str, *, excluir_estudo: str | None = None
    ) -> PlanoContratadoVersao | None:
        with self._connect() as conn:
            if excluir_estudo:
                row = conn.execute(
                    """
                    SELECT p.* FROM planos_contratados p
                    JOIN estudos_meta e ON e.id = p.estudo_id
                    WHERE e.cliente_id=? AND p.estudo_id != ?
                    ORDER BY p.criado_em DESC LIMIT 1
                    """,
                    (cliente_id, excluir_estudo),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT p.* FROM planos_contratados p
                    JOIN estudos_meta e ON e.id = p.estudo_id
                    WHERE e.cliente_id=?
                    ORDER BY p.criado_em DESC LIMIT 1
                    """,
                    (cliente_id,),
                ).fetchone()
        return self._row_plano(row) if row else None

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
        meta = self.obter_estudo_meta(rascunho.id)
        agora = datetime.now(timezone.utc)
        registro = PlanoContratadoVersao(
            id=str(uuid.uuid4()),
            estudo_id=rascunho.id,
            ciclo_id=meta.ciclo_id if meta else None,
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
                    id, estudo_id, ciclo_id, opcao_proposta_id, operadora, plano_nome,
                    vigencia_inicio, vigencia_fim, acomodacao, modalidade,
                    regime_copart, copart_percentual, premio_centavos, iof_centavos,
                    total_recorrente_centavos, tabela_json, documento_origem_id,
                    criado_em, criado_por
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    registro.id,
                    registro.estudo_id,
                    registro.ciclo_id,
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
        return [self._row_plano(r) for r in rows]

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

    def _row_estudo_meta(self, row: sqlite3.Row) -> EstudoMeta:
        return EstudoMeta(
            id=row["id"],
            titulo=row["titulo"],
            formato=row["formato"],
            cliente_id=row["cliente_id"],
            ciclo_id=row["ciclo_id"],
            cliente_nome=row["cliente_nome"],
            ciclo_numero=row["ciclo_numero"],
            estado_workflow=row["estado_workflow"],
            criado_em=datetime.fromisoformat(row["criado_em"]),
            atualizado_em=datetime.fromisoformat(row["atualizado_em"]),
        )

    def _row_participacao(self, row: sqlite3.Row) -> BeneficiarioParticipacao:
        return BeneficiarioParticipacao(
            id=row["id"],
            estudo_id=row["estudo_id"],
            posicao_versao_id=row["posicao_versao_id"],
            beneficiario_id=row["beneficiario_id"],
            vida_rascunho_id=row["vida_rascunho_id"],
            nome=row["nome"],
            nascimento=date.fromisoformat(row["nascimento"]),
            parentesco=row["parentesco"],
            sexo=row["sexo"],
            status=row["status"],
            subgrupo_id=row["subgrupo_id"],
            plano_nome=row["plano_nome"],
            faixa=row["faixa"],
            valor_centavos=row["valor_centavos"],
            motivo_alteracao=row["motivo_alteracao"],
            sugestao_vinculo=row["sugestao_vinculo"],
            vinculo_status=row["vinculo_status"] or "pendente",
        )

    def _row_plano(self, row: sqlite3.Row) -> PlanoContratadoVersao:
        return PlanoContratadoVersao(
            id=row["id"],
            estudo_id=row["estudo_id"],
            ciclo_id=row["ciclo_id"] if "ciclo_id" in row.keys() else None,
            opcao_proposta_id=row["opcao_proposta_id"],
            operadora=row["operadora"],
            plano_nome=row["plano_nome"],
            vigencia_inicio=date.fromisoformat(row["vigencia_inicio"]),
            vigencia_fim=date.fromisoformat(row["vigencia_fim"]) if row["vigencia_fim"] else None,
            acomodacao=row["acomodacao"],
            modalidade=row["modalidade"],
            regime_copart=row["regime_copart"],
            copart_percentual=row["copart_percentual"],
            premio_centavos=row["premio_centavos"],
            iof_centavos=row["iof_centavos"],
            total_recorrente_centavos=row["total_recorrente_centavos"],
            tabela_json=row["tabela_json"],
            documento_origem_id=row["documento_origem_id"],
            criado_em=datetime.fromisoformat(row["criado_em"]),
            criado_por=row["criado_por"],
        )
