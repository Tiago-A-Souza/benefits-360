"""Serviço de importação e conferência de cotações PDF."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from newport_app.config.paths import diretorio_uploads_cotacao
from newport_app.cotacao_pdf.apply import aplicar_extracao_confirmada
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from newport_app.models.cotacao_pdf import ExtracaoCotacaoCandidata, ValorExtraido
from newport_app.models.responses_cotacao import (
    AplicarExtracaoResponse,
    ConfirmacaoExtracaoResponse,
    ResultadoImportacaoCotacaoResponse,
)
from newport_app.repository.extracao_cotacao import ExtracaoCotacaoRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.siscor_mapper.apply import rascunho_vazio


class EstudoNaoEncontradoError(Exception):
    pass


class ExtracaoNaoEncontradaError(Exception):
    pass


class CampoNaoEncontradoError(Exception):
    pass


class ExtracaoCotacaoService:
    def __init__(
        self,
        estudos: SQLiteStudyRepository,
        extracoes: ExtracaoCotacaoRepository,
        *,
        uploads_dir: Path | None = None,
    ) -> None:
        self._estudos = estudos
        self._extracoes = extracoes
        self._uploads_dir = uploads_dir or diretorio_uploads_cotacao()

    def _salvar_pdf(self, documento_id: str, conteudo: bytes) -> Path:
        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        destino = self._uploads_dir / f"{documento_id}.pdf"
        destino.write_bytes(conteudo)
        return destino

    def caminho_pdf(self, documento_id: str) -> Path | None:
        caminho = self._uploads_dir / f"{documento_id}.pdf"
        return caminho if caminho.is_file() else None

    def importar_pdf(
        self,
        estudo_id: str,
        conteudo: bytes,
        nome_arquivo: str,
    ) -> ResultadoImportacaoCotacaoResponse:
        rascunho = self._estudos.obter_rascunho(estudo_id)
        if rascunho is None:
            raise EstudoNaoEncontradoError(estudo_id)

        documento_id = str(uuid.uuid4())
        self._salvar_pdf(documento_id, conteudo)
        versoes = self._extracoes.listar_versoes(estudo_id, documento_id)
        versao = (max(versoes) + 1) if versoes else 1

        extracao = parse_cotacao_pdf(
            conteudo,
            estudo_id=estudo_id,
            documento_id=documento_id,
            nome_arquivo=nome_arquivo,
            versao=versao,
            versoes_anteriores=versoes,
        )
        self._extracoes.salvar(extracao)
        return ResultadoImportacaoCotacaoResponse(
            sucesso=extracao.estado not in ("erro", "nao_reconhecido"),
            extracao_id=extracao.id,
            estado=extracao.estado,
            operadora=extracao.documento.operadora_detectada,
            template_id=extracao.documento.template_id,
            opcoes_encontradas=len(extracao.opcoes),
            alertas=extracao.alertas,
        )

    def listar_extracoes(self, estudo_id: str) -> list[ExtracaoCotacaoCandidata]:
        return self._extracoes.listar_ativas(estudo_id)

    def obter_extracao(self, extracao_id: str) -> ExtracaoCotacaoCandidata:
        extracao = self._extracoes.obter_por_id(extracao_id)
        if extracao is None:
            raise ExtracaoNaoEncontradaError(extracao_id)
        return extracao

    def _iter_campos(self, extracao: ExtracaoCotacaoCandidata):
        for campo in extracao.campos_extraidos:
            yield campo
        for op in extracao.opcoes:
            if op.excluida:
                continue
            for fx in op.tabela:
                yield fx.valor
                yield fx.quantidade

    def atualizar_campo(
        self,
        extracao_id: str,
        campo_id: str,
        *,
        centavos: int | None = None,
        texto: str | None = None,
        inteiro: int | None = None,
        confirmado: bool | None = None,
        editado_por: str = "analista-local",
    ) -> ValorExtraido:
        extracao = self.obter_extracao(extracao_id)
        for campo in self._iter_campos(extracao):
            if campo.id != campo_id:
                continue
            if centavos is not None:
                campo.valor_anterior_centavos = campo.centavos
                campo.centavos = centavos
            if texto is not None:
                campo.valor_anterior_texto = campo.texto
                campo.texto = texto
            if inteiro is not None:
                campo.inteiro = inteiro
            if confirmado is not None:
                campo.confirmado = confirmado
                if confirmado:
                    campo.confirmado_por = editado_por
                    campo.confirmado_em = datetime.now(timezone.utc)
            campo.estado = "revisar"
            self._extracoes.salvar(extracao)
            return campo
        raise CampoNaoEncontradoError(campo_id)

    def confirmar_lote_sem_alerta(
        self,
        extracao_id: str,
        *,
        confirmado_por: str = "analista-local",
    ) -> ConfirmacaoExtracaoResponse:
        extracao = self.obter_extracao(extracao_id)
        confirmados = 0
        agora = datetime.now(timezone.utc)
        for campo in self._iter_campos(extracao):
            if campo.estado == "confirmar" and not campo.confirmado:
                campo.confirmado = True
                campo.confirmado_por = confirmado_por
                campo.confirmado_em = agora
                confirmados += 1
        self._extracoes.salvar(extracao)
        return ConfirmacaoExtracaoResponse(confirmados=confirmados)

    def excluir_opcao(self, extracao_id: str, opcao_id: str) -> None:
        extracao = self.obter_extracao(extracao_id)
        for op in extracao.opcoes:
            if op.id == opcao_id:
                op.excluida = True
                break
        self._extracoes.salvar(extracao)

    def aplicar_ao_rascunho(self, extracao_id: str) -> AplicarExtracaoResponse:
        extracao = self.obter_extracao(extracao_id)
        rascunho = self._estudos.obter_rascunho(extracao.estudo_id)
        if rascunho is None:
            rascunho = rascunho_vazio(extracao.estudo_id, f"Estudo {extracao.estudo_id}")
        antes = len(rascunho.opcoes_proposta)
        rascunho = aplicar_extracao_confirmada(rascunho, extracao)
        self._estudos.salvar_rascunho(rascunho)
        depois = len(rascunho.opcoes_proposta)
        return AplicarExtracaoResponse(
            opcoes_adicionadas=depois - antes,
            total_opcoes=depois,
        )
