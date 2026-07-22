"""Serviço de importação e conferência SISCOR."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from newport_app.config.paths import diretorio_runtime_privado
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses_siscor import (
    ConfirmacaoLoteResponse,
    ConferenciaSiscorResponse,
    ResumoImportacaoSiscor,
    ResultadoImportacaoSiscorResponse,
)
from newport_app.models.siscor_import import (
    CorrespondenciaSugeridaSiscor,
    ImportacaoSiscorCandidata,
    LinhaSiscorCandidata,
)
from newport_app.repository.importacao_siscor import ImportacaoSiscorRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.siscor_importer.parser import parse_planilha_siscor
from newport_app.siscor_importer.revalidate import revalidar_linha
from newport_app.siscor_mapper.apply import (
    aplicar_candidata_ao_rascunho,
    estudo_possui_dados,
    rascunho_vazio,
)


class EstudoNaoEncontradoError(Exception):
    pass


class ImportacaoRequerDecisaoError(Exception):
    def __init__(self, opcoes: list[str]) -> None:
        self.opcoes = opcoes
        super().__init__("reimportação requer decisão do usuário")


class LinhaNaoEncontradaError(Exception):
    pass


class ImportacaoSiscorService:
    def __init__(
        self,
        estudos: SQLiteStudyRepository,
        importacoes: ImportacaoSiscorRepository,
        *,
        uploads_dir: Path | None = None,
    ) -> None:
        self._estudos = estudos
        self._importacoes = importacoes
        self._uploads_dir = uploads_dir or (diretorio_runtime_privado() / "uploads")

    def _salvar_arquivo(self, documento_id: str, conteudo: bytes) -> Path:
        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        destino = self._uploads_dir / f"{documento_id}.xlsx"
        destino.write_bytes(conteudo)
        return destino

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

    def importar_planilha(
        self,
        estudo_id: str,
        conteudo: bytes,
        *,
        titulo: str | None = None,
        modo: str | None = None,
        criado_por: str = "analista-local",
    ) -> ResultadoImportacaoSiscorResponse:
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
        self._salvar_arquivo(documento_id, conteudo)

        versao = 1
        anterior: ImportacaoSiscorCandidata | None = None
        if candidata_ativa is not None:
            if modo == "nova_versao":
                versao = candidata_ativa.versao + 1
                anterior = candidata_ativa
            elif modo == "substituir":
                candidata_ativa.estado = "substituida"
                self._importacoes.salvar(candidata_ativa, ativa=False)
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

        self._sugerir_correspondencias(resultado.candidata, anterior)
        self._importacoes.salvar(resultado.candidata, ativa=True)

        if modo == "substituir" or not possui_dados:
            rascunho = rascunho_vazio(rascunho.id, rascunho.titulo)

        if self._estudos.obter_rascunho(estudo_id) is None:
            self._estudos.salvar_rascunho(rascunho)
        elif modo == "substituir" or not possui_dados:
            self._estudos.salvar_rascunho(rascunho)
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
        agora = datetime.now(timezone.utc)
        confirmadas = 0
        for linha in candidata.linhas:
            if linha.excluida or linha.tem_excecao:
                continue
            linha.registro_confirmado = True
            linha.valor_confirmado = linha.valor_fatura is not None
            linha.confirmado_em = agora
            linha.confirmado_por = confirmado_por
            confirmadas += 1
        self._recalcular_estatisticas(candidata)
        rascunho = self._obter_ou_criar_rascunho(estudo_id, None)
        rascunho = aplicar_candidata_ao_rascunho(rascunho, candidata)
        self._importacoes.salvar(candidata)
        self._estudos.salvar_rascunho(rascunho)
        excecoes = sum(1 for l in candidata.linhas if l.tem_excecao and not l.excluida)
        return ConfirmacaoLoteResponse(
            confirmadas=confirmadas,
            excecoes_restantes=excecoes,
            vidas_no_rascunho=candidata.estatisticas.vidas_no_rascunho,
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
        valor_centavos: int | None = None,
        incluida: bool | None = None,
        excluida: bool | None = None,
        motivo_exclusao: str | None = None,
        confirmar: bool = False,
        confirmado_por: str = "analista-local",
    ) -> LinhaSiscorCandidata:
        candidata = self._importacoes.obter_ativa(estudo_id)
        if candidata is None:
            raise EstudoNaoEncontradoError(estudo_id)
        linha = next((l for l in candidata.linhas if l.id == linha_id), None)
        if linha is None:
            raise LinhaNaoEncontradaError(linha_id)

        linha.editado_manualmente = True
        linha.registro_confirmado = False
        linha.valor_confirmado = False
        linha.confirmado_em = None
        linha.confirmado_por = None

        if segurado is not None:
            linha.segurado = segurado
        if nascimento is not None:
            linha.nascimento = nascimento
        if parentesco_texto is not None:
            linha.parentesco_texto = parentesco_texto
        if plano is not None:
            linha.plano = plano
        if valor_centavos is not None and linha.valor_fatura is not None:
            linha.valor_centavos = valor_centavos
            linha.valor_fatura = linha.valor_fatura.model_copy(
                update={"centavos": valor_centavos}
            )
        if incluida is not None:
            linha.incluida_sugerida = incluida
        if excluida is not None:
            linha.excluida = excluida
        if motivo_exclusao is not None:
            linha.motivo_exclusao = motivo_exclusao

        revalidar_linha(linha)
        if confirmar and not linha.tem_excecao:
            linha.registro_confirmado = True
            linha.valor_confirmado = linha.valor_fatura is not None
            linha.confirmado_em = datetime.now(timezone.utc)
            linha.confirmado_por = confirmado_por

        self._recalcular_estatisticas(candidata)
        rascunho = self._obter_ou_criar_rascunho(estudo_id, None)
        rascunho = aplicar_candidata_ao_rascunho(rascunho, candidata)
        self._importacoes.salvar(candidata)
        self._estudos.salvar_rascunho(rascunho)
        return linha
