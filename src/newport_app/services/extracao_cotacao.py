"""Serviço de importação e conferência de cotações PDF."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from collections.abc import Callable

from newport_app.config.paths import diretorio_uploads_cotacao
from newport_app.diagnostico import registrar_evento
from newport_app.cotacao_pdf.estimativa import estimar_opcao_candidata
from newport_app.cotacao_pdf.maturidade import avaliar_maturidade
from newport_app.cotacao_pdf.apply import (
    aplicar_extracao_confirmada,
    impacto_remocao_reaplicacao,
)
from newport_app.cotacao_pdf.confirmacao import (
    confirmar_extracao_selecionadas,
    confirmar_opcao_implicita,
)
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from newport_app.cotacao_pdf.conferencia import normalizar_extracao
from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
from newport_app.cotacao_pdf.validation import pendencias_opcao
from newport_app.models.cotacao_pdf import ExtracaoCotacaoCandidata, OpcaoCotacaoCandidata, ValorExtraido
from newport_app.models.draft import PriceBasisRascunho
from newport_app.models.responses_remocao import ImpactoRemocao
from newport_app.models.responses_cotacao import (
    AplicarExtracaoResponse,
    BloqueioOpcaoExtracao,
    ConfirmacaoExtracaoResponse,
    DescartarExtracaoResponse,
    EstimarPropostasResponse,
    RemoverExtracaoResponse,
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


class OpcaoNaoEncontradaError(Exception):
    pass


class MotivoDescarteObrigatorioError(Exception):
    pass


class CotacaoDescartadaError(Exception):
    pass


class AplicacaoExtracaoError(Exception):
    def __init__(self, mensagem: str, bloqueios: list[BloqueioOpcaoExtracao]) -> None:
        super().__init__(mensagem)
        self.bloqueios = bloqueios


class RemocaoExigeConfirmacaoError(Exception):
    """Re-aplicação que desfaz atribuição de cenário — nada foi gravado ainda."""

    def __init__(self, mensagem: str, impacto: ImpactoRemocao) -> None:
        super().__init__(mensagem)
        self.impacto = impacto


class ExtracaoCotacaoService:
    def __init__(
        self,
        estudos: SQLiteStudyRepository,
        extracoes: ExtracaoCotacaoRepository,
        *,
        uploads_dir: Path | None = None,
        on_rascunho_alterado: Callable[[str, str], None] | None = None,
    ) -> None:
        self._estudos = estudos
        self._extracoes = extracoes
        self._uploads_dir = uploads_dir or diretorio_uploads_cotacao()
        self._on_rascunho_alterado = on_rascunho_alterado

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
        ativas = [o for o in extracao.opcoes if not o.excluida]
        detalhe_log = {
            "estado": extracao.estado,
            "template_id": extracao.documento.template_id,
            "quantidade_opcoes": len(ativas),
            "alertas": [a.codigo for a in extracao.alertas],
            "arquivo": nome_arquivo,
        }
        registrar_evento(
            estudo_id=estudo_id,
            etapa="cotacao_pdf",
            evento="extracao_zero_opcoes" if not ativas else "extracao_pdf",
            detalhe=detalhe_log,
        )
        return ResultadoImportacaoCotacaoResponse(
            sucesso=extracao.estado not in ("erro", "nao_reconhecido"),
            extracao_id=extracao.id,
            estado=extracao.estado,
            operadora=extracao.documento.operadora_detectada,
            template_id=extracao.documento.template_id,
            opcoes_encontradas=len(extracao.opcoes),
            alertas=extracao.alertas,
            maturidade=avaliar_maturidade(extracao),
        )

    def obter_extracao(self, extracao_id: str) -> ExtracaoCotacaoCandidata:
        extracao = self._extracoes.obter_por_id(extracao_id)
        if extracao is None:
            raise ExtracaoNaoEncontradaError(extracao_id)
        normalizada = normalizar_extracao(extracao)
        if normalizada.model_dump() != extracao.model_dump():
            self._extracoes.salvar(normalizada)
        return normalizada

    def listar_extracoes(self, estudo_id: str) -> list[ExtracaoCotacaoCandidata]:
        itens = self._extracoes.listar_ativas(estudo_id)
        return [normalizar_extracao(e) for e in itens]

    def _iter_campos_opcao(self, op: OpcaoCotacaoCandidata):
        for attr in (
            op.operadora,
            op.plano_nome,
            op.tipo_fiscal,
            op.acomodacao,
            op.modalidade,
            op.regime_copart,
            op.copart_percentual,
            op.premio_saude,
            op.iof,
            op.total_recorrente,
            op.total_primeira_parcela,
            op.subtotal_impresso,
            op.validade_oficial,
            op.observacoes,
        ):
            if attr is not None:
                yield attr
        for fx in op.tabela:
            yield fx.valor
            yield fx.quantidade
        for custo in op.custos_unicos:
            yield custo

    def _iter_campos(self, extracao: ExtracaoCotacaoCandidata):
        for campo in extracao.campos_extraidos:
            yield campo
        for op in extracao.opcoes:
            if op.excluida:
                continue
            yield from self._iter_campos_opcao(op)

    def _opcao_do_campo(
        self, extracao: ExtracaoCotacaoCandidata, campo_id: str
    ) -> OpcaoCotacaoCandidata | None:
        for op in extracao.opcoes:
            for campo in self._iter_campos_opcao(op):
                if campo.id == campo_id:
                    return op
        return None

    def _reconciliar_se_financeiro(self, op: OpcaoCotacaoCandidata, campo: ValorExtraido) -> None:
        rotulo = campo.rotulo.lower()
        if any(
            chave in rotulo
            for chave in ("valor faixa", "quantidade faixa", "prêmio", "iof", "total", "subtotal", "parcela", "custo")
        ) or campo.centavos is not None or campo.inteiro is not None:
            reconciliar_opcao(op)

    def _campo_eh_validade(
        self, extracao: ExtracaoCotacaoCandidata, campo: ValorExtraido
    ) -> bool:
        if extracao.validade_oficial is not None and extracao.validade_oficial.id == campo.id:
            return True
        for op in extracao.opcoes:
            if op.validade_oficial is not None and op.validade_oficial.id == campo.id:
                return True
        return False

    def _gravar_validade_em_campo(
        self,
        campo: ValorExtraido | None,
        data: date,
        *,
        confirmado: bool,
        editado_por: str,
        agora: datetime,
    ) -> None:
        if campo is None:
            return
        campo.data = data
        campo.estado = "confirmar" if confirmado else "revisar"
        if confirmado:
            campo.confirmado = True
            campo.confirmado_por = editado_por
            campo.confirmado_em = agora
        else:
            campo.confirmado = False
            campo.confirmado_por = None
            campo.confirmado_em = None

    def _propagar_validade_selecionadas(
        self,
        extracao: ExtracaoCotacaoCandidata,
        data: date,
        *,
        confirmado: bool,
        editado_por: str,
    ) -> None:
        """Validade é do documento — grava no nível da cotação e em todos os planos selecionados."""
        from newport_app.cotacao_pdf.parsers.base import novo_campo

        agora = datetime.now(timezone.utc)
        if extracao.validade_oficial is None:
            extracao.validade_oficial = novo_campo(
                "Validade",
                data=data,
                parser_versao=extracao.documento.parser_versao,
                documento_hash=extracao.documento.hash_sha256,
            )
        self._gravar_validade_em_campo(
            extracao.validade_oficial,
            data,
            confirmado=confirmado,
            editado_por=editado_por,
            agora=agora,
        )
        for op in extracao.opcoes:
            if op.excluida or not op.selecionada_para_comparativo:
                continue
            if op.validade_oficial is None:
                continue
            self._gravar_validade_em_campo(
                op.validade_oficial,
                data,
                confirmado=confirmado,
                editado_por=editado_por,
                agora=agora,
            )

    def atualizar_campo(
        self,
        extracao_id: str,
        campo_id: str,
        *,
        centavos: int | None = None,
        texto: str | None = None,
        inteiro: int | None = None,
        data: date | None = None,
        price_basis: PriceBasisRascunho | None = None,
        confirmado: bool | None = None,
        editado_por: str = "analista-local",
    ) -> ValorExtraido:
        extracao = self.obter_extracao(extracao_id)
        opcao: OpcaoCotacaoCandidata | None = None
        for campo in self._iter_campos(extracao):
            if campo.id != campo_id:
                continue
            opcao = self._opcao_do_campo(extracao, campo_id)
            if centavos is not None:
                campo.valor_anterior_centavos = campo.centavos
                campo.centavos = centavos
                campo.estado = "revisar"
            if texto is not None:
                campo.valor_anterior_texto = campo.texto
                campo.texto = texto
                campo.estado = "revisar"
            if inteiro is not None:
                campo.inteiro = inteiro
                campo.estado = "revisar"
            if data is not None:
                campo.data = data
                campo.estado = "revisar"
            if price_basis is not None:
                campo.price_basis = price_basis
                campo.estado = "revisar"
            if confirmado is not None:
                campo.confirmado = confirmado
                if confirmado:
                    campo.confirmado_por = editado_por
                    campo.confirmado_em = datetime.now(timezone.utc)
                    campo.estado = "confirmar"
                else:
                    campo.confirmado_por = None
                    campo.confirmado_em = None
            elif any(v is not None for v in (centavos, texto, inteiro, data, price_basis)):
                campo.confirmado = True
                campo.confirmado_por = editado_por
                campo.confirmado_em = datetime.now(timezone.utc)
                campo.estado = "confirmar"
            if opcao is not None:
                self._reconciliar_se_financeiro(opcao, campo)
            if data is not None and self._campo_eh_validade(extracao, campo):
                self._propagar_validade_selecionadas(
                    extracao,
                    data,
                    confirmado=bool(campo.confirmado),
                    editado_por=editado_por,
                )
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
        for op in extracao.opcoes:
            if op.excluida:
                continue
            for campo in self._iter_campos_opcao(op):
                if campo.estado == "confirmar" and not campo.confirmado:
                    campo.confirmado = True
                    campo.confirmado_por = confirmado_por
                    campo.confirmado_em = agora
                    confirmados += 1
            reconciliar_opcao(op)
        self._extracoes.salvar(extracao)
        return ConfirmacaoExtracaoResponse(confirmados=confirmados)

    def excluir_opcao(self, extracao_id: str, opcao_id: str) -> None:
        extracao = self.obter_extracao(extracao_id)
        for op in extracao.opcoes:
            if op.id == opcao_id:
                op.excluida = True
                op.selecionada_para_comparativo = False
                break
        else:
            raise OpcaoNaoEncontradaError(opcao_id)
        self._extracoes.salvar(extracao)

    def selecionar_opcao(
        self,
        extracao_id: str,
        opcao_id: str,
        *,
        selecionada: bool,
    ) -> OpcaoCotacaoCandidata:
        if not self._extracoes.esta_ativa(extracao_id):
            raise ExtracaoNaoEncontradaError(extracao_id)
        extracao = self.obter_extracao(extracao_id)
        if extracao.descartada and selecionada:
            raise CotacaoDescartadaError(extracao_id)
        for op in extracao.opcoes:
            if op.id == opcao_id:
                if op.excluida:
                    raise OpcaoNaoEncontradaError(opcao_id)
                op.selecionada_para_comparativo = selecionada
                if selecionada:
                    confirmar_opcao_implicita(op, confirmado_por="selecao")
                self._extracoes.salvar(extracao)
                return op
        raise OpcaoNaoEncontradaError(opcao_id)

    def aplicar_ao_rascunho(
        self,
        extracao_id: str,
        *,
        confirmar_remocoes: bool = False,
        subgrupo_id: str | None = None,
    ) -> AplicarExtracaoResponse:
        extracao = self.obter_extracao(extracao_id)
        if extracao.descartada:
            raise CotacaoDescartadaError(extracao_id)

        rascunho = self._estudos.obter_rascunho(extracao.estudo_id)
        if rascunho is None:
            rascunho = rascunho_vazio(extracao.estudo_id, f"Estudo {extracao.estudo_id}")

        from newport_app.cotacao_pdf.maturidade import opcoes_ativas
        from newport_app.rascunho.selecao_grupo import (
            atribui_planos_do_pdf_ao_grupo,
            ids_extracao_protegidos_por_outros_grupos,
        )

        protegidos: set[str] = set()
        if subgrupo_id:
            protegidos = ids_extracao_protegidos_por_outros_grupos(
                rascunho, extracao.id, subgrupo_id
            )

        # Pré-voo antes de qualquer escrita: o operador ainda pode desistir.
        impacto = impacto_remocao_reaplicacao(
            rascunho,
            extracao,
            ids_extracao_protegidos=protegidos or None,
            selecao_vazia_nao_leva_todos=bool(subgrupo_id),
        )
        if impacto.exige_confirmacao and not confirmar_remocoes:
            raise RemocaoExigeConfirmacaoError(
                "Esta aplicação remove planos que estão em uso na etapa 4.",
                impacto,
            )

        confirmar_extracao_selecionadas(extracao, confirmado_por="aplicacao")
        self._extracoes.salvar(extracao)

        antes_ids = {
            op.extracao_opcao_id
            for op in rascunho.opcoes_proposta
            if op.extracao_id == extracao.id and op.extracao_opcao_id
        }
        rascunho, bloqueios_brutos = aplicar_extracao_confirmada(
            rascunho,
            extracao,
            ids_extracao_protegidos=protegidos or None,
            selecao_vazia_nao_leva_todos=bool(subgrupo_id),
        )

        depois_ids = {
            op.extracao_opcao_id
            for op in rascunho.opcoes_proposta
            if op.extracao_id == extracao.id and op.extracao_opcao_id
        }
        aplicadas = len(depois_ids - antes_ids)
        atualizadas = len(depois_ids & antes_ids)

        bloqueios = [
            BloqueioOpcaoExtracao(
                opcao_id=str(b["opcao_id"]),
                plano=str(b["plano"]),
                motivos=[str(m) for m in b["motivos"]],  # type: ignore[arg-type]
            )
            for b in bloqueios_brutos
        ]

        if aplicadas == 0 and atualizadas == 0 and bloqueios:
            raise AplicacaoExtracaoError(
                "Nenhuma proposta pôde ser aplicada — confira os campos pendentes.",
                bloqueios,
            )

        if subgrupo_id:
            ativas = opcoes_ativas(extracao)
            marcadas = {o.id for o in ativas if o.selecionada_para_comparativo}
            ids_rascunho = [
                op.id
                for op in rascunho.opcoes_proposta
                if op.extracao_id == extracao.id and op.extracao_opcao_id in marcadas
            ]
            atribui_planos_do_pdf_ao_grupo(
                rascunho, subgrupo_id, extracao.id, ids_rascunho
            )

        self._estudos.salvar_rascunho(rascunho)
        if self._on_rascunho_alterado:
            self._on_rascunho_alterado(
                rascunho.id,
                "Aplicação de proposta extraída do PDF",
            )
        return AplicarExtracaoResponse(
            opcoes_adicionadas=aplicadas,
            opcoes_atualizadas=atualizadas,
            total_opcoes=len(rascunho.opcoes_proposta),
            bloqueios=bloqueios,
            impacto_remocao=impacto if impacto.houve_remocao else None,
        )

    def _retirar_planos_do_rascunho(
        self,
        estudo_id: str,
        extracao_id: str,
    ) -> int:
        rascunho = self._estudos.obter_rascunho(estudo_id)
        if rascunho is None:
            return 0
        antes = len(rascunho.opcoes_proposta)
        rascunho.opcoes_proposta = [
            op for op in rascunho.opcoes_proposta if op.extracao_id != extracao_id
        ]
        removidos = antes - len(rascunho.opcoes_proposta)
        if removidos:
            opcoes_validas = {op.id for op in rascunho.opcoes_proposta}
            for cenario in rascunho.cenarios:
                cenario.atribuicoes = [
                    atr
                    for atr in cenario.atribuicoes
                    if atr.opcao_plano_id in opcoes_validas
                ]
            self._estudos.salvar_rascunho(rascunho)
            if self._on_rascunho_alterado:
                self._on_rascunho_alterado(
                    estudo_id,
                    "Retirada de planos de cotação descartada do comparativo",
                )
        return removidos

    def descartar_extracao(
        self,
        estudo_id: str,
        extracao_id: str,
        *,
        motivo: str,
        descartada_por: str = "analista-local",
    ) -> DescartarExtracaoResponse:
        motivo_limpo = (motivo or "").strip()
        if not motivo_limpo:
            raise MotivoDescarteObrigatorioError("motivo")
        extracao = self.obter_extracao(extracao_id)
        if extracao.estudo_id != estudo_id:
            raise ExtracaoNaoEncontradaError(extracao_id)
        for op in extracao.opcoes:
            op.selecionada_para_comparativo = False
        extracao.descartada = True
        extracao.motivo_descarte = motivo_limpo
        extracao.descartada_em = datetime.now(timezone.utc)
        extracao.descartada_por = descartada_por
        self._extracoes.salvar(extracao)
        planos_removidos = self._retirar_planos_do_rascunho(estudo_id, extracao_id)
        registrar_evento(
            estudo_id=estudo_id,
            etapa="cotacao_pdf",
            evento="cotacao_descartada",
            detalhe={
                "extracao_id": extracao_id,
                "motivo": motivo_limpo[:200],
                "planos_removidos": planos_removidos,
            },
        )
        return DescartarExtracaoResponse(
            descartada=True,
            motivo=motivo_limpo,
            planos_removidos=planos_removidos,
            mensagem=(
                f"Cotação marcada como não utilizada ({motivo_limpo})."
                + (
                    f" {planos_removidos} plano(s) retirado(s) do comparativo."
                    if planos_removidos
                    else ""
                )
            ),
        )

    def reverter_descarte_extracao(
        self,
        estudo_id: str,
        extracao_id: str,
    ) -> ExtracaoCotacaoCandidata:
        extracao = self.obter_extracao(extracao_id)
        if extracao.estudo_id != estudo_id:
            raise ExtracaoNaoEncontradaError(extracao_id)
        extracao.descartada = False
        extracao.motivo_descarte = None
        extracao.descartada_em = None
        extracao.descartada_por = None
        self._extracoes.salvar(extracao)
        return extracao

    def remover_extracao(self, estudo_id: str, extracao_id: str) -> RemoverExtracaoResponse:
        extracao = self.obter_extracao(extracao_id)
        if extracao.estudo_id != estudo_id:
            raise ExtracaoNaoEncontradaError(extracao_id)

        rascunho = self._estudos.obter_rascunho(estudo_id)
        planos_removidos = 0
        if rascunho is not None:
            antes = len(rascunho.opcoes_proposta)
            doc_id = extracao.documento.id
            rascunho.opcoes_proposta = [
                op for op in rascunho.opcoes_proposta if op.extracao_id != extracao.id
            ]
            planos_removidos = antes - len(rascunho.opcoes_proposta)
            opcoes_validas = {op.id for op in rascunho.opcoes_proposta}
            for cenario in rascunho.cenarios:
                cenario.atribuicoes = [
                    atr
                    for atr in cenario.atribuicoes
                    if atr.opcao_plano_id in opcoes_validas
                ]
            if not any(op.documento_cotacao_id == doc_id for op in rascunho.opcoes_proposta):
                rascunho.documentos_cotacao = [
                    doc for doc in rascunho.documentos_cotacao if doc.id != doc_id
                ]
            self._estudos.salvar_rascunho(rascunho)

        self._extracoes.desativar_por_documento(estudo_id, extracao.documento.id)
        caminho = self.caminho_pdf(extracao.documento.id)
        if caminho is not None and caminho.is_file():
            caminho.unlink()

        if self._on_rascunho_alterado:
            self._on_rascunho_alterado(
                estudo_id,
                f"Remoção da cotação PDF «{extracao.documento.nome_arquivo}»",
            )

        if planos_removidos:
            msg = (
                f"Cotação removida. {planos_removidos} plano(s) e associações derivadas "
                "também foram retirados do comparativo."
            )
        else:
            msg = "Cotação removida do estudo."

        return RemoverExtracaoResponse(
            removido=True,
            planos_removidos=planos_removidos,
            aprovacao_invalidada=planos_removidos > 0,
            mensagem=msg,
        )

    def estimar_propostas(
        self,
        extracao_id: str,
        quantidades_por_faixa: dict[int, int],
    ) -> EstimarPropostasResponse:
        extracao = self._extracoes.obter(extracao_id)
        if extracao is None:
            raise ExtracaoNaoEncontradaError(extracao_id)
        totais: dict[str, int | None] = {}
        for opcao in extracao.opcoes:
            if opcao.excluida:
                continue
            totais[opcao.id] = estimar_opcao_candidata(opcao, quantidades_por_faixa)
        return EstimarPropostasResponse(totais=totais)
