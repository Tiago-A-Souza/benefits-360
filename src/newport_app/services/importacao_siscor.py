"""Serviço de importação e conferência SISCOR."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collections.abc import Callable

from newport_app.config.paths import diretorio_uploads
from newport_app.draft_compiler.structural import validar_estrutura
from newport_app.models.draft import (
    ComponenteFinanceiroRascunho,
    OrigemValorRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
)
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses_siscor import (
    ConfirmacaoLoteResponse,
    ConferenciaSiscorResponse,
    ResumoImportacaoSiscor,
    ResultadoImportacaoSiscorResponse,
)
from newport_app.models.siscor_import import (
    IMPORTADOR_SISCOR_VERSAO,
    CorrespondenciaSugeridaSiscor,
    EdicaoManualSiscor,
    ImportacaoSiscorCandidata,
    LinhaSiscorCandidata,
)
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.importacao_siscor import ImportacaoSiscorRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.siscor_importer.duplicidades import recalcular_duplicidades
from newport_app.siscor_importer.parser import parse_planilha_siscor
from newport_app.siscor_importer.revalidate import revalidar_linha
from newport_app.siscor_importer.subgrupos import remontar_subgrupos_candidata
from newport_app.siscor_mapper.apply import (
    aplicar_candidata_ao_rascunho,
    estudo_possui_dados,
    rascunho_vazio,
)

MODOS_REIMPORTACAO_VALIDOS = frozenset({"substituir", "nova_versao"})

MENSAGEM_HISTORICO_FALHOU = (
    "Os dados foram lidos, mas não foi possível concluir o registro histórico. "
    "Nenhuma nova importação é necessária."
)


class EstudoNaoEncontradoError(Exception):
    pass


class HistoricoPersistenciaError(Exception):
    def __init__(self, mensagem_operacional: str = MENSAGEM_HISTORICO_FALHOU) -> None:
        self.mensagem_operacional = mensagem_operacional
        super().__init__(mensagem_operacional)


class ImportacaoRequerDecisaoError(Exception):
    def __init__(self, opcoes: list[str]) -> None:
        self.opcoes = opcoes
        super().__init__("reimportação requer decisão do usuário")


class ModoImportacaoInvalidoError(Exception):
    pass


class LinhaNaoEncontradaError(Exception):
    pass


class ExclusaoSemMotivoError(Exception):
    pass


class LinhaIncompletaConfirmacaoError(Exception):
    pass


class ImportacaoSiscorService:
    def __init__(
        self,
        estudos: SQLiteStudyRepository,
        importacoes: ImportacaoSiscorRepository,
        *,
        uploads_dir: Path | None = None,
        historico: HistoricoRepository | None = None,
        on_rascunho_alterado: Callable[[str, str], None] | None = None,
    ) -> None:
        self._estudos = estudos
        self._importacoes = importacoes
        self._uploads_dir = uploads_dir or diretorio_uploads()
        self._historico = historico
        self._on_rascunho_alterado = on_rascunho_alterado

    def _persistir_rascunho(
        self,
        rascunho: RascunhoEstudo,
        *,
        motivo_invalidacao: str = "Alteração via SISCOR",
    ) -> None:
        self._estudos.salvar_rascunho(rascunho)
        if self._on_rascunho_alterado:
            self._on_rascunho_alterado(rascunho.id, motivo_invalidacao)

    def _registrar_posicao_siscor(
        self,
        conn: sqlite3.Connection,
        rascunho: RascunhoEstudo,
        candidata: ImportacaoSiscorCandidata,
    ):
        if self._historico is None or not rascunho.vidas:
            return None
        return self._historico._registrar_posicao_cadastral_conn(
            conn,
            rascunho,
            origem="siscor",
            documento_hash=candidata.documento_hash_sha256,
            importador_versao=IMPORTADOR_SISCOR_VERSAO,
            importacao_id=candidata.id,
        )

    def _resposta_confirmacao_idempotente(
        self,
        estudo_id: str,
        candidata: ImportacaoSiscorCandidata,
        posicao,
    ) -> ConfirmacaoLoteResponse:
        rascunho = self._estudos.obter_rascunho(estudo_id)
        excecoes = sum(1 for l in candidata.linhas if l.tem_excecao and not l.excluida)
        participacoes = 0
        if self._historico and posicao:
            participacoes = self._historico.contar_participacoes(
                estudo_id, posicao_id=posicao.id
            )
        return ConfirmacaoLoteResponse(
            confirmadas=candidata.estatisticas.confirmadas,
            excecoes_restantes=excecoes,
            vidas_no_rascunho=len(rascunho.vidas) if rascunho else candidata.estatisticas.vidas_no_rascunho,
            base_aplicada=True,
            historico_registrado=posicao is not None,
            repeticao=True,
            mensagem="Confirmação já registrada para esta importação.",
            posicoes_cadastrais=self._historico.contar_posicoes(estudo_id) if self._historico else 0,
            participacoes_historicas=participacoes,
        )

    def _persistir_confirmacao_transacional(
        self,
        candidata: ImportacaoSiscorCandidata,
        rascunho: RascunhoEstudo,
    ):
        agora = datetime.now(timezone.utc).isoformat()
        payload = rascunho.model_dump_json()
        conn = sqlite3.connect(self._estudos.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._estudos._salvar_rascunho_conn(conn, rascunho, payload, agora)
            posicao = self._registrar_posicao_siscor(conn, rascunho, candidata)
            conn.commit()
            return posicao
        except sqlite3.Error as exc:
            conn.rollback()
            raise HistoricoPersistenciaError() from exc
        finally:
            conn.close()

    def _salvar_arquivo(self, documento_id: str, conteudo: bytes) -> Path:
        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        destino = self._uploads_dir / f"{documento_id}.xlsx"
        destino.write_bytes(conteudo)
        return destino

    def _remover_arquivo(self, documento_id: str) -> None:
        caminho = self._uploads_dir / f"{documento_id}.xlsx"
        if caminho.is_file():
            caminho.unlink()

    def _recalcular_estatisticas(self, candidata: ImportacaoSiscorCandidata) -> None:
        com_excecao = sum(
            1 for linha in candidata.linhas if linha.tem_excecao and not linha.excluida
        )
        confirmadas = sum(1 for linha in candidata.linhas if linha.registro_confirmado)
        planos = {l.subgrupo_sugerido_id for l in candidata.linhas if l.subgrupo_sugerido_id}
        candidata.estatisticas = candidata.estatisticas.model_copy(
            update={
                "total_linhas_lidas": len(candidata.linhas),
                "linhas_utilizaveis": len(candidata.linhas),
                "linhas_com_excecao": com_excecao,
                "planos_detectados": len(planos),
                "confirmadas": confirmadas,
                "aguardando_conferencia": len(candidata.linhas) - confirmadas,
            }
        )

    def _sugerir_correspondencias(
        self,
        nova: ImportacaoSiscorCandidata,
        anterior: ImportacaoSiscorCandidata | None,
    ) -> None:
        if anterior is None:
            return
        indice_anterior = {
            (l.segurado, l.nascimento, l.plano): l.id
            for l in anterior.linhas
            if l.segurado and l.nascimento and l.plano
        }
        sugestoes: list[CorrespondenciaSugeridaSiscor] = []
        for linha in nova.linhas:
            chave = (linha.segurado, linha.nascimento, linha.plano)
            if chave in indice_anterior:
                sugestoes.append(
                    CorrespondenciaSugeridaSiscor(
                        linha_nova_id=linha.id,
                        linha_anterior_id=indice_anterior[chave],
                        motivo="Mesmo nome, nascimento e plano na importação anterior.",
                        confianca="baixa",
                    )
                )
        nova.correspondencias_sugeridas = sugestoes

    def _obter_ou_criar_rascunho(self, estudo_id: str, titulo: str | None) -> RascunhoEstudo:
        existente = self._estudos.obter_rascunho(estudo_id)
        if existente is not None:
            return existente
        return rascunho_vazio(estudo_id, titulo or f"Estudo {estudo_id}")

    def _registrar_edicao(
        self,
        linha: LinhaSiscorCandidata,
        campo: str,
        anterior: Any,
        novo: Any,
        *,
        editado_por: str,
    ) -> None:
        if str(anterior) == str(novo):
            return
        linha.historico_edicoes.append(
            EdicaoManualSiscor(
                campo=campo,
                valor_anterior=None if anterior is None else str(anterior),
                valor_novo=None if novo is None else str(novo),
                editado_em=datetime.now(timezone.utc),
                editado_por=editado_por,
            )
        )
        linha.editado_manualmente = True

    def _reset_confirmacao(self, linha: LinhaSiscorCandidata) -> None:
        linha.registro_confirmado = False
        linha.valor_confirmado = False
        linha.confirmado_em = None
        linha.confirmado_por = None

    def importar_planilha(
        self,
        estudo_id: str,
        conteudo: bytes,
        *,
        titulo: str | None = None,
        modo: str | None = None,
        criado_por: str = "analista-local",
    ) -> ResultadoImportacaoSiscorResponse:
        if modo is not None and modo not in MODOS_REIMPORTACAO_VALIDOS:
            raise ModoImportacaoInvalidoError(modo)

        rascunho = self._obter_ou_criar_rascunho(estudo_id, titulo)
        candidata_ativa = self._importacoes.obter_ativa(estudo_id)
        possui_dados = estudo_possui_dados(rascunho) or candidata_ativa is not None

        if possui_dados and modo is None:
            opcoes = (
                ["nova_versao"]
                if self._importacoes.possui_confirmacoes(estudo_id)
                else ["substituir"]
            )
            raise ImportacaoRequerDecisaoError(opcoes)

        documento_id = str(uuid.uuid4())
        versao = 1
        anterior: ImportacaoSiscorCandidata | None = None
        if candidata_ativa is not None:
            if modo == "nova_versao":
                versao = candidata_ativa.versao + 1
                anterior = candidata_ativa
            elif modo == "substituir":
                versao = candidata_ativa.versao + 1

        resultado = parse_planilha_siscor(
            conteudo,
            estudo_id=estudo_id,
            documento_id=documento_id,
            versao=versao,
            criado_por=criado_por,
        )
        if not resultado.sucesso or resultado.candidata is None:
            return ResultadoImportacaoSiscorResponse(
                sucesso=False,
                erros_arquivo=resultado.erros_arquivo,
            )

        self._salvar_arquivo(documento_id, conteudo)

        if candidata_ativa is not None and modo == "substituir":
            candidata_ativa.estado = "substituida"
            self._importacoes.salvar(candidata_ativa, ativa=False)

        self._sugerir_correspondencias(resultado.candidata, anterior)
        self._importacoes.salvar(resultado.candidata, ativa=True)

        if modo == "substituir" or not possui_dados:
            rascunho = rascunho_vazio(rascunho.id, rascunho.titulo)

        if self._estudos.obter_rascunho(estudo_id) is None:
            self._persistir_rascunho(rascunho, motivo_invalidacao="Criação de estudo via SISCOR")
        elif modo == "substituir" or not possui_dados:
            self._persistir_rascunho(rascunho, motivo_invalidacao="Substituição via SISCOR")

        resumo = ResumoImportacaoSiscor(
            estudo_id=estudo_id,
            importacao_id=resultado.candidata.id,
            versao=resultado.candidata.versao,
            empresa_sugerida=resultado.candidata.empresa_sugerida,
            estatisticas=resultado.candidata.estatisticas,
        )
        return ResultadoImportacaoSiscorResponse(
            sucesso=True,
            resumo=resumo,
            candidata=resultado.candidata,
        )

    def obter_conferencia(self, estudo_id: str) -> ConferenciaSiscorResponse:
        candidata = self._importacoes.obter_ativa(estudo_id)
        if candidata is None:
            raise EstudoNaoEncontradoError(estudo_id)
        return ConferenciaSiscorResponse(
            estudo_id=estudo_id,
            importacao_id=candidata.id,
            versao=candidata.versao,
            estado=candidata.estado,
            estatisticas=candidata.estatisticas,
            linhas=[linha.model_dump(mode="json") for linha in candidata.linhas],
            subgrupos_sugeridos=[
                sg.model_dump(mode="json") for sg in candidata.subgrupos_sugeridos
            ],
            correspondencias_sugeridas=[
                c.model_dump(mode="json") for c in candidata.correspondencias_sugeridas
            ],
        )

    def confirmar_lote(
        self,
        estudo_id: str,
        *,
        confirmado_por: str = "analista-local",
    ) -> ConfirmacaoLoteResponse:
        candidata = self._importacoes.obter_ativa(estudo_id)
        if candidata is None:
            raise EstudoNaoEncontradoError(estudo_id)

        if self._historico is not None:
            existente = self._historico.obter_posicao_por_importacao(estudo_id, candidata.id)
            if existente is not None:
                return self._resposta_confirmacao_idempotente(estudo_id, candidata, existente)

        agora = datetime.now(timezone.utc)
        confirmadas = 0
        for linha in candidata.linhas:
            if linha.excluida or not linha.confirmavel:
                continue
            linha.registro_confirmado = True
            linha.valor_confirmado = (
                linha.valor_fatura is not None and linha.valor_centavos is not None
            )
            linha.confirmado_em = agora
            linha.confirmado_por = confirmado_por
            confirmadas += 1
        self._recalcular_estatisticas(candidata)

        rascunho = self._obter_ou_criar_rascunho(estudo_id, None)
        rascunho = aplicar_candidata_ao_rascunho(rascunho, candidata)

        erros_estrutura = validar_estrutura(rascunho)
        if erros_estrutura:
            raise HistoricoPersistenciaError(
                "Não foi possível aplicar a base confirmada — revise pendências na conferência."
            )

        posicao = None
        if self._historico is not None and rascunho.vidas:
            posicao = self._persistir_confirmacao_transacional(candidata, rascunho)
        else:
            self._persistir_rascunho(rascunho, motivo_invalidacao="Confirmação em lote SISCOR")

        self._importacoes.salvar(candidata)
        if self._on_rascunho_alterado:
            self._on_rascunho_alterado(rascunho.id, "Confirmação em lote SISCOR")

        excecoes = sum(1 for l in candidata.linhas if l.tem_excecao and not l.excluida)
        participacoes = 0
        posicoes = 0
        if self._historico:
            posicoes = self._historico.contar_posicoes(estudo_id)
            if posicao:
                participacoes = self._historico.contar_participacoes(
                    estudo_id, posicao_id=posicao.id
                )

        return ConfirmacaoLoteResponse(
            confirmadas=confirmadas,
            excecoes_restantes=excecoes,
            vidas_no_rascunho=len(rascunho.vidas),
            base_aplicada=True,
            historico_registrado=posicao is not None,
            repeticao=False,
            mensagem="Base confirmada e histórico registrado.",
            posicoes_cadastrais=posicoes,
            participacoes_historicas=participacoes,
        )

    def atualizar_linha(
        self,
        estudo_id: str,
        linha_id: str,
        *,
        segurado: str | None = None,
        nascimento: str | None = None,
        parentesco_texto: str | None = None,
        plano: str | None = None,
        operadora: str | None = None,
        status_texto: str | None = None,
        valor_centavos: int | None = None,
        incluida: bool | None = None,
        excluida: bool | None = None,
        motivo_exclusao: str | None = None,
        confirmar: bool = False,
        editado_por: str = "analista-local",
        confirmado_por: str = "analista-local",
    ) -> LinhaSiscorCandidata:
        candidata = self._importacoes.obter_ativa(estudo_id)
        if candidata is None:
            raise EstudoNaoEncontradoError(estudo_id)
        linha = next((l for l in candidata.linhas if l.id == linha_id), None)
        if linha is None:
            raise LinhaNaoEncontradaError(linha_id)

        if excluida is True and not (motivo_exclusao or linha.motivo_exclusao):
            raise ExclusaoSemMotivoError()

        houve_edicao = False

        if segurado is not None:
            self._registrar_edicao(linha, "segurado", linha.segurado, segurado, editado_por=editado_por)
            linha.segurado = segurado
            houve_edicao = True
        if nascimento is not None:
            self._registrar_edicao(linha, "nascimento", linha.nascimento, nascimento, editado_por=editado_por)
            linha.nascimento = nascimento
            houve_edicao = True
        if parentesco_texto is not None:
            self._registrar_edicao(
                linha, "parentesco", linha.parentesco_texto, parentesco_texto, editado_por=editado_por
            )
            linha.parentesco_texto = parentesco_texto
            linha.parentesco = None
            houve_edicao = True
        if plano is not None:
            self._registrar_edicao(linha, "plano", linha.plano, plano, editado_por=editado_por)
            linha.plano = plano
            houve_edicao = True
        if operadora is not None:
            self._registrar_edicao(linha, "operadora", linha.operadora, operadora, editado_por=editado_por)
            linha.operadora = operadora
            houve_edicao = True
        if status_texto is not None:
            self._registrar_edicao(linha, "status", linha.status_texto, status_texto, editado_por=editado_por)
            linha.status_texto = status_texto
            linha.status_normalizado = None
            houve_edicao = True
        if valor_centavos is not None:
            self._registrar_edicao(
                linha, "valor_centavos", linha.valor_centavos, valor_centavos, editado_por=editado_por
            )
            linha.valor_centavos = valor_centavos
            if linha.valor_fatura is None:
                linha.valor_fatura = ComponenteFinanceiroRascunho(
                    centavos=valor_centavos,
                    price_basis=PriceBasisRascunho.DESCONHECIDO,
                    proveniencia=ProvenienciaRascunho(
                        origem=OrigemValorRascunho.MANUAL,
                        documento_id=candidata.documento_id,
                        extrator_versao=IMPORTADOR_SISCOR_VERSAO,
                        confirmado=False,
                    ),
                )
            else:
                linha.valor_fatura = linha.valor_fatura.model_copy(
                    update={
                        "centavos": valor_centavos,
                        "proveniencia": ProvenienciaRascunho(
                            origem=OrigemValorRascunho.MANUAL,
                            documento_id=candidata.documento_id,
                            extrator_versao=IMPORTADOR_SISCOR_VERSAO,
                            confirmado=False,
                        ),
                    }
                )
            houve_edicao = True
        if incluida is not None:
            self._registrar_edicao(
                linha, "incluida", linha.incluida_sugerida, incluida, editado_por=editado_por
            )
            linha.incluida_sugerida = incluida
            houve_edicao = True
        if excluida is not None:
            self._registrar_edicao(linha, "excluida", linha.excluida, excluida, editado_por=editado_por)
            linha.excluida = excluida
            houve_edicao = True
        if motivo_exclusao is not None:
            self._registrar_edicao(
                linha, "motivo_exclusao", linha.motivo_exclusao, motivo_exclusao, editado_por=editado_por
            )
            linha.motivo_exclusao = motivo_exclusao
            houve_edicao = True

        if houve_edicao:
            self._reset_confirmacao(linha)

        revalidar_linha(linha, documento_id=candidata.documento_id)
        recalcular_duplicidades(candidata.linhas)
        remontar_subgrupos_candidata(candidata)

        if confirmar:
            if not linha.confirmavel:
                raise LinhaIncompletaConfirmacaoError()
            linha.registro_confirmado = True
            linha.valor_confirmado = (
                linha.valor_fatura is not None and linha.valor_centavos is not None
            )
            linha.confirmado_em = datetime.now(timezone.utc)
            linha.confirmado_por = confirmado_por

        self._recalcular_estatisticas(candidata)
        rascunho = aplicar_candidata_ao_rascunho(
            self._obter_ou_criar_rascunho(estudo_id, None), candidata
        )
        self._importacoes.salvar(candidata)
        self._persistir_rascunho(rascunho, motivo_invalidacao="Edição de linha SISCOR")
        return linha
