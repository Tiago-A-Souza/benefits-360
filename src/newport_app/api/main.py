"""FastAPI — walking skeleton + compilador + importação SISCOR."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from newport_app.api.middleware import ModoRealLocalMiddleware
from newport_app.api.validation_handlers import resposta_validacao_sanitizada
from newport_app.config.paths import (
    caminho_banco_cotacoes,
    caminho_banco_estudos,
    caminho_banco_importacoes,
    diretorio_entregaveis,
    diretorio_uploads,
    diretorio_uploads_cotacao,
    garantir_diretorios,
)
from newport_app.config.runtime import (
    LIMITE_UPLOAD_BYTES,
    ModoExecucao,
    ModoExecucaoInvalidoError,
    exigir_host_local_modo_real,
    modo_execucao,
)
from newport_app.draft_compiler.structural import RascunhoEstruturalInvalidoError
from newport_app.models.draft import PriceBasisRascunho, RascunhoEstudo
from newport_app.models.historico import (
    BeneficiarioParticipacao,
    CicloRenovacao,
    Cliente,
    ConfirmarVinculoLoteRequest,
    ConfirmarVinculoRequest,
    HistoricoEstudoResponse,
    PlanoContratadoVersao,
    PosicaoCadastralVersao,
    RegistrarPlanoContratadoRequest,
    VincularEstudoRequest,
)
from newport_app.models.presentation import PresentationViewModel
from newport_app.models.snapshot import (
    AprovarSnapshotRequest,
    AprovarSnapshotResponse,
    GerarApresentacaoRequest,
    GerarApresentacaoResponse,
    GerarSnapshotResponse,
    SnapshotCalculo,
)
from newport_app.models.responses import (
    ComparativoComExibicao,
    ComparativoResponse,
    ConfirmarComparativoRequest,
    ConfirmarComparativoResponse,
    EstudoResumo,
    PendenciaItem,
    ResumoPlanoAtualResponse,
    SalvarSelecaoApresentacaoRequest,
    SalvarSelecaoApresentacaoResponse,
    SugestaoReajustePmeItem,
    SugestaoReajustePmeResponse,
)
from newport_app.models.responses_cotacao import (
    AplicarExtracaoResponse,
    ConfirmacaoExtracaoResponse,
    DescartarExtracaoRequest,
    DescartarExtracaoResponse,
    EstimarPropostasRequest,
    EstimarPropostasResponse,
    ListaExtracaoCotacaoResponse,
    RemoverExtracaoResponse,
    ResultadoImportacaoCotacaoResponse,
)
from newport_app.models.cotacao_pdf import ExtracaoCotacaoCandidata
from newport_app.models.responses_siscor import (
    ConfirmacaoLoteResponse,
    ConferenciaSiscorResponse,
    ResultadoImportacaoSiscorResponse,
)
from newport_app.repository.extracao_cotacao import ExtracaoCotacaoRepository
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.importacao_siscor import ImportacaoSiscorRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas, rascunho_demo_41_vidas
from newport_app.services.apresentacao import ApresentacaoService
from newport_app.services.calculo import (
    CalculoService,
    EstudoNaoEncontradoError,
    RascunhoNaoCompilavelError,
)
from newport_app.services.opcao_proposta import (
    OpcaoPropostaDeExtracaoError,
    OpcaoPropostaNaoEncontradaError,
)
from newport_app.services.comparativo_confirmacao import ConfirmacaoComparativoInvalidaError
from newport_app.services.comparativo_ui import (
    SelecaoApresentacaoInvalidaError,
    resolver_propostas_apresentacao_snapshot,
    salvar_selecao_apresentacao,
)
from newport_app.services.extracao_cotacao import (
    CampoNaoEncontradoError,
    CotacaoDescartadaError,
    EstudoNaoEncontradoError as EstudoCotacaoNaoEncontradoError,
    AplicacaoExtracaoError,
    ExtracaoCotacaoService,
    ExtracaoNaoEncontradaError,
    MotivoDescarteObrigatorioError,
    OpcaoNaoEncontradaError,
)
from newport_app.services.resumo_plano_atual import montar_resumo_plano_atual
from newport_app.services.pendencias import pendencias_compilacao
from newport_app.services.importacao_siscor import (
    ExclusaoSemMotivoError,
    HistoricoPersistenciaError,
    ImportacaoRequerDecisaoError,
    ImportacaoSiscorService,
    LinhaIncompletaConfirmacaoError,
    LinhaNaoEncontradaError,
    ModoImportacaoInvalidoError,
)
from newport_app.services.snapshot import (
    AprovacaoInvalidaError,
    SnapshotBloqueadoError,
    SnapshotFormatoIncompativelError,
    SnapshotNaoEncontradoError,
    SnapshotService,
)
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.motor_por_proposta import PropostaNaoCalculavelError
from newport_app.siscor_mapper.apply import rascunho_vazio

API_VERSAO = "2.8.2"

ROOT = Path(__file__).resolve().parents[3]
WEB_DIST = ROOT / "web" / "dist"


def _criar_repo() -> SQLiteStudyRepository:
    garantir_diretorios()
    exigir_host_local_modo_real()
    return SQLiteStudyRepository(caminho_banco_estudos())


def _criar_import_repo() -> ImportacaoSiscorRepository:
    return ImportacaoSiscorRepository(caminho_banco_importacoes())


def _seed_inicial(service: CalculoService) -> None:
    service.garantir_rascunho(rascunho_demo_12_vidas())
    service.garantir_rascunho(rascunho_demo_41_vidas())


class NovoEstudoRequest(BaseModel):
    titulo: str
    nome_empresa: str
    id: str | None = None
    formato: Literal["renovacao", "novo"] = "renovacao"


class RegistrarDiagnosticoRequest(BaseModel):
    estudo_id: str | None = None
    etapa: str
    evento: str
    detalhe: dict | None = None


class AtualizarLinhaSiscorRequest(BaseModel):
    segurado: str | None = None
    nascimento: str | None = None
    parentesco_texto: str | None = None
    plano: str | None = None
    operadora: str | None = None
    status_texto: str | None = None
    valor_centavos: int | None = None
    incluida: bool | None = None
    excluida: bool | None = None
    motivo_exclusao: str | None = None
    confirmar: bool = False


class AtualizarCampoExtracaoRequest(BaseModel):
    centavos: int | None = None
    texto: str | None = None
    inteiro: int | None = None
    data: str | None = None
    price_basis: PriceBasisRascunho | None = None
    confirmado: bool | None = None


class SelecionarOpcaoExtracaoRequest(BaseModel):
    selecionada: bool = True


def create_app(
    repo: SQLiteStudyRepository | None = None,
    import_repo: ImportacaoSiscorRepository | None = None,
    cotacao_repo: ExtracaoCotacaoRepository | None = None,
    uploads_dir: Path | None = None,
    uploads_cotacao_dir: Path | None = None,
    *,
    seed_demos: bool | None = None,
) -> FastAPI:
    if seed_demos is None:
        seed_demos = modo_execucao() == ModoExecucao.DEMO

    repository = repo or _criar_repo()
    db_path = repository._db_path  # noqa: SLF001 — wiring piloto local
    importacoes = import_repo or _criar_import_repo()
    extracoes_cotacao = cotacao_repo or ExtracaoCotacaoRepository(caminho_banco_cotacoes())
    uploads = uploads_dir or diretorio_uploads()
    uploads_cotacao = uploads_cotacao_dir or diretorio_uploads_cotacao()
    historico = HistoricoRepository(db_path)
    snap_repo = SnapshotRepository(db_path)
    snapshot_service = SnapshotService(repository, snap_repo, historico)

    def _invalidar(estudo_id: str, motivo: str) -> None:
        snapshot_service.invalidar_por_alteracao(estudo_id, motivo)

    service = CalculoService(
        repository,
        on_rascunho_alterado=_invalidar,
        snapshot_service=snapshot_service,
    )
    siscor = ImportacaoSiscorService(
        repository,
        importacoes,
        uploads_dir=uploads,
        historico=historico,
        on_rascunho_alterado=_invalidar,
    )
    cotacao = ExtracaoCotacaoService(
        repository,
        extracoes_cotacao,
        uploads_dir=uploads_cotacao,
        on_rascunho_alterado=_invalidar,
    )
    apresentacao = ApresentacaoService(
        snapshot_service,
        snap_repo,
        diretorio_entregaveis(),
    )
    if seed_demos:
        _seed_inicial(service)

    app = FastAPI(title="Newport Estudos", version=API_VERSAO)
    app.state.calculo_service = service
    app.state.siscor_service = siscor
    app.state.cotacao_service = cotacao
    app.state.snapshot_service = snapshot_service
    app.state.apresentacao_service = apresentacao
    app.state.historico_repo = historico
    app.state.snapshot_repo = snap_repo
    app.state.repository = repository
    app.state.modo = modo_execucao().value

    @app.exception_handler(RequestValidationError)
    async def validacao_sanitizada(_request, exc: RequestValidationError):
        return resposta_validacao_sanitizada(exc)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(ModoRealLocalMiddleware)

    @app.get("/api/config")
    def obter_config() -> dict[str, str | int]:
        return {
            "modo": modo_execucao().value,
            "versao": API_VERSAO,
            "limite_upload_bytes": LIMITE_UPLOAD_BYTES,
        }

    @app.post("/api/diagnostico")
    def registrar_diagnostico_api(body: RegistrarDiagnosticoRequest) -> dict:
        from newport_app.diagnostico import registrar_evento

        registrar_evento(
            estudo_id=body.estudo_id,
            etapa=body.etapa,
            evento=body.evento,
            detalhe=body.detalhe or {},
        )
        return {"ok": True}

    @app.get("/api/estudos", response_model=list[EstudoResumo])
    def listar_estudos() -> list[EstudoResumo]:
        resumos = service.listar_resumos()
        enriquecidos: list[EstudoResumo] = []
        for resumo in resumos:
            if snap_repo.snapshot_aprovado_atual(resumo.id):
                enriquecidos.append(
                    resumo.model_copy(
                        update={"status": "aprovado", "status_exibicao": "Aprovado"}
                    )
                )
            else:
                enriquecidos.append(resumo)
        return enriquecidos

    @app.post("/api/estudos", response_model=EstudoResumo)
    def criar_estudo_vazio(body: NovoEstudoRequest) -> EstudoResumo:
        import uuid

        estudo_id = body.id or f"est-{uuid.uuid4().hex[:10]}"
        if repository.obter_rascunho(estudo_id) is not None:
            raise HTTPException(status_code=409, detail="Estudo já existe.")
        rascunho = rascunho_vazio(
            estudo_id,
            body.titulo.strip(),
            nome_empresa=body.nome_empresa.strip(),
            formato=body.formato,
        )
        repository.salvar_rascunho(rascunho)
        return service.obter_resumo(estudo_id)

    @app.get("/api/estudos/{estudo_id}", response_model=EstudoResumo)
    def obter_estudo(estudo_id: str) -> EstudoResumo:
        try:
            return service.obter_resumo(estudo_id)
        except EstudoNaoEncontradoError:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None

    @app.get("/api/estudos/{estudo_id}/rascunho", response_model=RascunhoEstudo)
    def obter_rascunho(estudo_id: str) -> RascunhoEstudo:
        rascunho = repository.obter_rascunho(estudo_id)
        if rascunho is None:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None
        return rascunho

    @app.get(
        "/api/estudos/{estudo_id}/sugestao-reajuste-pme",
        response_model=SugestaoReajustePmeResponse,
    )
    def obter_sugestao_reajuste_pme(
        estudo_id: str,
        data_referencia_idade: str | None = Query(default=None),
    ) -> SugestaoReajustePmeResponse:
        """Sugestão da tabela PME. Não grava no rascunho nem no snapshot."""
        from datetime import date as date_type

        from newport_app.reajuste_pme import (
            LIMIAR_VIDAS_PME,
            periodo_da_data,
            sugestoes_do_rascunho,
            vidas_incluidas_estudo,
        )

        rascunho = repository.obter_rascunho(estudo_id)
        if rascunho is None:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None
        data_ref = rascunho.escolhas.data_referencia_idade
        if data_referencia_idade:
            try:
                data_ref = date_type.fromisoformat(data_referencia_idade)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="data_referencia_idade inválida.",
                ) from None
            rascunho = rascunho.model_copy(deep=True)
            rascunho.escolhas.data_referencia_idade = data_ref
        sugestoes = sugestoes_do_rascunho(rascunho)
        periodo = periodo_da_data(data_ref)
        return SugestaoReajustePmeResponse(
            vidas_incluidas=vidas_incluidas_estudo(rascunho),
            limiar_vidas=LIMIAR_VIDAS_PME,
            periodo=periodo,
            data_referencia_idade=data_ref.isoformat() if data_ref else None,
            formato=rascunho.formato,
            por_plano=[
                SugestaoReajustePmeItem(
                    subgrupo_id=s.subgrupo_id,
                    periodo=s.periodo,
                    reajuste_bps=s.reajuste_bps,
                    reajuste_pct_exibicao=s.reajuste_pct_exibicao,
                    origem=s.origem,
                    operadora_canonica=s.operadora_canonica,
                )
                for s in sugestoes
            ],
        )

    @app.get("/api/estudos/{estudo_id}/pendencias", response_model=list[PendenciaItem])
    def listar_pendencias_estudo(estudo_id: str) -> list[PendenciaItem]:
        rascunho = repository.obter_rascunho(estudo_id)
        if rascunho is None:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None
        return pendencias_compilacao(rascunho)

    @app.put("/api/estudos/{estudo_id}", response_model=EstudoResumo)
    def salvar_estudo(estudo_id: str, rascunho: RascunhoEstudo) -> EstudoResumo:
        if rascunho.id != estudo_id:
            raise HTTPException(
                status_code=400,
                detail="O identificador do corpo não corresponde ao da URL.",
            )
        try:
            service.salvar_rascunho(rascunho)
        except RascunhoEstruturalInvalidoError as exc:
            raise HTTPException(
                status_code=400,
                detail={"erros": [e.model_dump() for e in exc.erros]},
            ) from None
        return service.obter_resumo(estudo_id)

    @app.delete(
        "/api/estudos/{estudo_id}/opcoes-proposta/{opcao_id}",
        response_model=RascunhoEstudo,
    )
    def excluir_opcao_proposta_manual(estudo_id: str, opcao_id: str) -> RascunhoEstudo:
        try:
            return service.excluir_opcao_proposta_manual(estudo_id, opcao_id)
        except EstudoNaoEncontradoError:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None
        except OpcaoPropostaNaoEncontradaError:
            raise HTTPException(status_code=404, detail="Cotação não encontrada") from None
        except OpcaoPropostaDeExtracaoError:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Cotação importada de PDF não pode ser excluída por este caminho. "
                    "Remova a extração correspondente."
                ),
            ) from None
        except RascunhoEstruturalInvalidoError as exc:
            raise HTTPException(
                status_code=400,
                detail={"erros": [e.model_dump() for e in exc.erros]},
            ) from None

    @app.post(
        "/api/estudos/{estudo_id}/importar-siscor",
        response_model=ResultadoImportacaoSiscorResponse,
    )
    async def importar_siscor(
        estudo_id: str,
        arquivo: UploadFile = File(...),
        modo: str | None = Query(default=None),
        titulo: str | None = Query(default=None),
    ) -> ResultadoImportacaoSiscorResponse:
        conteudo = await arquivo.read()
        if len(conteudo) > LIMITE_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Arquivo excede o limite permitido para upload.",
            )
        try:
            return siscor.importar_planilha(
                estudo_id,
                conteudo,
                titulo=titulo,
                modo=modo,
            )
        except ImportacaoRequerDecisaoError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "mensagem": "Escolha como tratar a reimportação.",
                    "opcoes": exc.opcoes,
                },
            ) from None
        except ModoImportacaoInvalidoError:
            raise HTTPException(
                status_code=400,
                detail="Modo de reimportação inválido. Use substituir ou nova_versao.",
            ) from None

    @app.get(
        "/api/estudos/{estudo_id}/conferencia-siscor",
        response_model=ConferenciaSiscorResponse,
    )
    def conferencia_siscor(estudo_id: str) -> ConferenciaSiscorResponse:
        try:
            return siscor.obter_conferencia(estudo_id)
        except EstudoNaoEncontradoError:
            raise HTTPException(status_code=404, detail="Importação não encontrada") from None

    @app.post(
        "/api/estudos/{estudo_id}/conferencia-siscor/confirmar-lote",
        response_model=ConfirmacaoLoteResponse,
    )
    def confirmar_lote_siscor(estudo_id: str) -> ConfirmacaoLoteResponse:
        try:
            return siscor.confirmar_lote(estudo_id)
        except EstudoNaoEncontradoError:
            raise HTTPException(status_code=404, detail="Importação não encontrada") from None
        except HistoricoPersistenciaError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "codigo": "historico_persistencia_falhou",
                    "mensagem": exc.mensagem_operacional,
                },
            ) from None

    @app.patch("/api/estudos/{estudo_id}/conferencia-siscor/linhas/{linha_id}")
    def atualizar_linha_siscor(
        estudo_id: str,
        linha_id: str,
        body: AtualizarLinhaSiscorRequest,
    ):
        try:
            campos = body.model_dump(exclude_unset=True)
            confirmar = campos.pop("confirmar", False)
            limpar_valor = "valor_centavos" in campos and campos["valor_centavos"] is None
            if limpar_valor:
                campos.pop("valor_centavos")
            linha = siscor.atualizar_linha(
                estudo_id,
                linha_id,
                confirmar=confirmar,
                limpar_valor=limpar_valor,
                **campos,
            )
            return {"linha": linha.model_dump(mode="json")}
        except EstudoNaoEncontradoError:
            raise HTTPException(status_code=404, detail="Importação não encontrada") from None
        except LinhaNaoEncontradaError:
            raise HTTPException(status_code=404, detail="Linha não encontrada") from None
        except ExclusaoSemMotivoError:
            raise HTTPException(
                status_code=400,
                detail="Informe o motivo ao excluir uma vida.",
            ) from None
        except LinhaIncompletaConfirmacaoError:
            raise HTTPException(
                status_code=422,
                detail="Linha incompleta ou com exceções — não pode ser confirmada.",
            ) from None

    @app.get("/api/estudos/{estudo_id}/resumo-plano-atual", response_model=ResumoPlanoAtualResponse)
    def resumo_plano_atual(estudo_id: str) -> ResumoPlanoAtualResponse:
        rascunho = repository.obter_rascunho(estudo_id)
        if rascunho is None:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None
        return montar_resumo_plano_atual(rascunho)

    @app.post(
        "/api/estudos/{estudo_id}/importar-cotacao-pdf",
        response_model=ResultadoImportacaoCotacaoResponse,
    )
    async def importar_cotacao_pdf(
        estudo_id: str,
        arquivo: UploadFile = File(...),
    ) -> ResultadoImportacaoCotacaoResponse:
        conteudo = await arquivo.read()
        if len(conteudo) > LIMITE_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Arquivo excede o limite permitido.")
        if not conteudo.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="Envie um arquivo PDF de cotação.")
        try:
            return cotacao.importar_pdf(
                estudo_id,
                conteudo,
                arquivo.filename or "cotacao.pdf",
            )
        except EstudoCotacaoNaoEncontradoError:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None

    @app.get(
        "/api/estudos/{estudo_id}/extracao-cotacao",
        response_model=ListaExtracaoCotacaoResponse,
    )
    def listar_extracao_cotacao(estudo_id: str) -> ListaExtracaoCotacaoResponse:
        return ListaExtracaoCotacaoResponse(extracoes=cotacao.listar_extracoes(estudo_id))

    @app.get(
        "/api/estudos/{estudo_id}/extracao-cotacao/{extracao_id}",
        response_model=ExtracaoCotacaoCandidata,
    )
    def obter_extracao_cotacao(estudo_id: str, extracao_id: str) -> ExtracaoCotacaoCandidata:
        try:
            ext = cotacao.obter_extracao(extracao_id)
        except ExtracaoNaoEncontradaError:
            raise HTTPException(status_code=404, detail="Extração não encontrada") from None
        if ext.estudo_id != estudo_id:
            raise HTTPException(status_code=404, detail="Extração não encontrada") from None
        return ext

    @app.post(
        "/api/estudos/{estudo_id}/extracao-cotacao/{extracao_id}/estimar",
        response_model=EstimarPropostasResponse,
    )
    def estimar_propostas_extracao(
        estudo_id: str,
        extracao_id: str,
        body: EstimarPropostasRequest,
    ) -> EstimarPropostasResponse:
        try:
            ext = cotacao.obter_extracao(extracao_id)
        except ExtracaoNaoEncontradaError:
            raise HTTPException(status_code=404, detail="Extração não encontrada") from None
        if ext.estudo_id != estudo_id:
            raise HTTPException(status_code=404, detail="Extração não encontrada") from None
        return cotacao.estimar_propostas(extracao_id, body.quantidades_por_faixa)

    @app.patch(
        "/api/estudos/{estudo_id}/extracao-cotacao/{extracao_id}/campos/{campo_id}",
    )
    def atualizar_campo_extracao(
        estudo_id: str,
        extracao_id: str,
        campo_id: str,
        body: AtualizarCampoExtracaoRequest,
    ):
        from datetime import date as date_type

        data_campo = None
        if body.data:
            try:
                data_campo = date_type.fromisoformat(body.data)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Data inválida.") from exc
        try:
            campo = cotacao.atualizar_campo(
                extracao_id,
                campo_id,
                centavos=body.centavos,
                texto=body.texto,
                inteiro=body.inteiro,
                data=data_campo,
                price_basis=body.price_basis,
                confirmado=body.confirmado,
            )
            return {"campo": campo.model_dump(mode="json")}
        except ExtracaoNaoEncontradaError:
            raise HTTPException(status_code=404, detail="Extração não encontrada") from None
        except CampoNaoEncontradoError:
            raise HTTPException(status_code=404, detail="Campo não encontrado") from None

    @app.post(
        "/api/estudos/{estudo_id}/extracao-cotacao/{extracao_id}/opcoes/{opcao_id}/excluir",
    )
    def excluir_opcao_extracao(estudo_id: str, extracao_id: str, opcao_id: str):
        try:
            ext = cotacao.obter_extracao(extracao_id)
            if ext.estudo_id != estudo_id:
                raise HTTPException(status_code=404, detail="Extração não encontrada") from None
            cotacao.excluir_opcao(extracao_id, opcao_id)
            return {"ok": True}
        except ExtracaoNaoEncontradaError:
            raise HTTPException(status_code=404, detail="Extração não encontrada") from None

    @app.post(
        "/api/estudos/{estudo_id}/extracao-cotacao/{extracao_id}/opcoes/{opcao_id}/selecionar",
    )
    def selecionar_opcao_extracao(
        estudo_id: str,
        extracao_id: str,
        opcao_id: str,
        body: SelecionarOpcaoExtracaoRequest,
    ):
        from newport_app.diagnostico import registrar_evento

        def _falha(status: int, mensagem: str, *, codigo: str) -> None:
            registrar_evento(
                estudo_id=estudo_id,
                etapa="cotacao_pdf",
                evento="selecao_opcao_falhou",
                detalhe={
                    "extracao_id": extracao_id,
                    "opcao_id": opcao_id,
                    "selecionada": body.selecionada,
                    "status_http": status,
                    "codigo": codigo,
                    "mensagem": mensagem,
                },
            )
            raise HTTPException(
                status_code=status,
                detail={"codigo": codigo, "mensagem": mensagem},
            ) from None

        try:
            ext = cotacao.obter_extracao(extracao_id)
            if ext.estudo_id != estudo_id:
                _falha(
                    404,
                    "Cotação não encontrada neste estudo. Recarregue a lista de PDFs.",
                    codigo="PDF-SEL-001",
                )
            opcao = cotacao.selecionar_opcao(
                extracao_id,
                opcao_id,
                selecionada=body.selecionada,
            )
            return {"opcao": opcao.model_dump(mode="json")}
        except HTTPException:
            raise
        except ExtracaoNaoEncontradaError:
            _falha(
                404,
                "Cotação não encontrada (pode ter sido removida). Recarregue a lista de PDFs.",
                codigo="PDF-SEL-001",
            )
        except OpcaoNaoEncontradaError:
            _falha(
                404,
                (
                    "Plano não encontrado nesta cotação — a extração pode ter sido "
                    "removida ou o plano excluído. Recarregue a cotação."
                ),
                codigo="PDF-SEL-002",
            )
        except CotacaoDescartadaError:
            _falha(
                409,
                "Esta cotação foi marcada como não utilizada. Reverta o descarte para selecionar planos.",
                codigo="PDF-SEL-003",
            )
        except Exception as exc:  # noqa: BLE001 — devolver motivo legível ao operador
            registrar_evento(
                estudo_id=estudo_id,
                etapa="cotacao_pdf",
                evento="selecao_opcao_falhou",
                detalhe={
                    "extracao_id": extracao_id,
                    "opcao_id": opcao_id,
                    "selecionada": body.selecionada,
                    "status_http": 500,
                    "codigo": "PDF-SEL-500",
                    "mensagem": f"{type(exc).__name__}: {exc}",
                },
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "codigo": "PDF-SEL-500",
                    "mensagem": (
                        f"Falha ao atualizar a seleção ({type(exc).__name__}: {exc}). "
                        "Consulte o diagnóstico ou tente novamente."
                    ),
                },
            ) from None

    @app.post(
        "/api/estudos/{estudo_id}/extracao-cotacao/{extracao_id}/confirmar-lote",
        response_model=ConfirmacaoExtracaoResponse,
    )
    def confirmar_lote_extracao(
        estudo_id: str,
        extracao_id: str,
    ) -> ConfirmacaoExtracaoResponse:
        try:
            return cotacao.confirmar_lote_sem_alerta(extracao_id)
        except ExtracaoNaoEncontradaError:
            raise HTTPException(status_code=404, detail="Extração não encontrada") from None

    @app.post(
        "/api/estudos/{estudo_id}/extracao-cotacao/{extracao_id}/aplicar",
        response_model=AplicarExtracaoResponse,
    )
    def aplicar_extracao(estudo_id: str, extracao_id: str) -> AplicarExtracaoResponse:
        try:
            ext = cotacao.obter_extracao(extracao_id)
            if ext.estudo_id != estudo_id:
                raise HTTPException(status_code=404, detail="Extração não encontrada") from None
            return cotacao.aplicar_ao_rascunho(extracao_id)
        except ExtracaoNaoEncontradaError:
            raise HTTPException(status_code=404, detail="Extração não encontrada") from None
        except CotacaoDescartadaError:
            raise HTTPException(
                status_code=409,
                detail={
                    "codigo": "PDF-DESC-002",
                    "mensagem": (
                        "Esta cotação foi marcada como não utilizada. "
                        "Reverta o descarte antes de adicionar planos ao comparativo."
                    ),
                },
            ) from None
        except AplicacaoExtracaoError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "mensagem": str(exc),
                    "bloqueios": [b.model_dump(mode="json") for b in exc.bloqueios],
                },
            ) from None

    @app.delete(
        "/api/estudos/{estudo_id}/extracao-cotacao/{extracao_id}",
        response_model=RemoverExtracaoResponse,
    )
    def remover_extracao_cotacao(
        estudo_id: str,
        extracao_id: str,
    ) -> RemoverExtracaoResponse:
        try:
            return cotacao.remover_extracao(estudo_id, extracao_id)
        except ExtracaoNaoEncontradaError:
            raise HTTPException(status_code=404, detail="Extração não encontrada") from None

    @app.post(
        "/api/estudos/{estudo_id}/extracao-cotacao/{extracao_id}/descartar",
        response_model=DescartarExtracaoResponse,
    )
    def descartar_extracao_cotacao(
        estudo_id: str,
        extracao_id: str,
        body: DescartarExtracaoRequest,
    ) -> DescartarExtracaoResponse:
        try:
            return cotacao.descartar_extracao(
                estudo_id,
                extracao_id,
                motivo=body.motivo,
            )
        except MotivoDescarteObrigatorioError:
            raise HTTPException(
                status_code=422,
                detail={
                    "codigo": "PDF-DESC-001",
                    "mensagem": "Informe o motivo para não usar esta cotação.",
                },
            ) from None
        except ExtracaoNaoEncontradaError:
            raise HTTPException(status_code=404, detail="Extração não encontrada") from None

    @app.post(
        "/api/estudos/{estudo_id}/extracao-cotacao/{extracao_id}/reverter-descarte",
        response_model=ExtracaoCotacaoCandidata,
    )
    def reverter_descarte_extracao_cotacao(
        estudo_id: str,
        extracao_id: str,
    ) -> ExtracaoCotacaoCandidata:
        try:
            return cotacao.reverter_descarte_extracao(estudo_id, extracao_id)
        except ExtracaoNaoEncontradaError:
            raise HTTPException(status_code=404, detail="Extração não encontrada") from None

    @app.get("/api/estudos/{estudo_id}/documentos-cotacao/{documento_id}/pdf")
    def baixar_pdf_cotacao(estudo_id: str, documento_id: str):
        from fastapi.responses import Response

        caminho = cotacao.caminho_pdf(documento_id)
        if caminho is None:
            raise HTTPException(status_code=404, detail="PDF não encontrado") from None
        return Response(
            content=caminho.read_bytes(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'inline; filename="cotacao.pdf"',
                "Cache-Control": "private, max-age=3600",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.post("/api/estudos/{estudo_id}/calcular", response_model=ComparativoComExibicao)
    def calcular_estudo(estudo_id: str) -> ComparativoComExibicao:
        try:
            comparativo = service.calcular(estudo_id)
            rascunho = repository.obter_rascunho(estudo_id)
            if rascunho is None:
                raise EstudoNaoEncontradoError(estudo_id)
            from newport_app.presentation.reajuste import anexar_exibicao_reajuste

            return anexar_exibicao_reajuste(comparativo, rascunho)
        except EstudoNaoEncontradoError:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None
        except RascunhoNaoCompilavelError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "erros": [e.model_dump() for e in exc.resultado.erros],
                    "compiler_versao": exc.resultado.compiler_versao,
                },
            ) from None

    @app.put(
        "/api/estudos/{estudo_id}/comparativo/selecao-apresentacao",
        response_model=SalvarSelecaoApresentacaoResponse,
    )
    def salvar_selecao_apresentacao_estudo(
        estudo_id: str,
        body: SalvarSelecaoApresentacaoRequest,
    ) -> SalvarSelecaoApresentacaoResponse:
        rascunho = repository.obter_rascunho(estudo_id)
        if rascunho is None:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None
        try:
            resp = salvar_selecao_apresentacao(rascunho, body.opcao_ids)
        except SelecaoApresentacaoInvalidaError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        service.salvar_rascunho(rascunho)
        return resp

    @app.post(
        "/api/estudos/{estudo_id}/comparativo/confirmar",
        response_model=ConfirmarComparativoResponse,
    )
    def confirmar_comparativo_estudo(
        estudo_id: str,
        body: ConfirmarComparativoRequest,
    ) -> ConfirmarComparativoResponse:
        try:
            return service.confirmar_comparativo(
                estudo_id, body.hash_comparativo, body.opcao_ids
            )
        except EstudoNaoEncontradoError:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None
        except ConfirmacaoComparativoInvalidaError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except SnapshotBloqueadoError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except RascunhoNaoCompilavelError as exc:
            titulos = [e.mensagem or e.codigo for e in exc.resultado.erros]
            mensagem = (
                "Não é possível confirmar — " + "; ".join(titulos)
                if titulos
                else "Não é possível confirmar — rascunho não compilável."
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "mensagem": mensagem,
                    "erros": [e.model_dump() for e in exc.resultado.erros],
                    "compiler_versao": exc.resultado.compiler_versao,
                },
            ) from None

    @app.post(
        "/api/estudos/{estudo_id}/snapshot",
        response_model=GerarSnapshotResponse,
    )
    def gerar_snapshot(estudo_id: str) -> GerarSnapshotResponse:
        rascunho = repository.obter_rascunho(estudo_id)
        if rascunho is None:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None
        try:
            return snapshot_service.gerar_snapshot_candidato(estudo_id)
        except SnapshotBloqueadoError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except RascunhoNaoCompilavelError as exc:
            titulos = [e.mensagem or e.codigo for e in exc.resultado.erros]
            mensagem = (
                "Não é possível congelar o comparativo — " + "; ".join(titulos)
                if titulos
                else "Não é possível congelar o comparativo — rascunho não compilável."
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "mensagem": mensagem,
                    "erros": [e.model_dump() for e in exc.resultado.erros],
                    "compiler_versao": exc.resultado.compiler_versao,
                },
            ) from None

    @app.get(
        "/api/estudos/{estudo_id}/snapshots",
        response_model=list[SnapshotCalculo],
    )
    def listar_snapshots(estudo_id: str) -> list[SnapshotCalculo]:
        if repository.obter_rascunho(estudo_id) is None:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None
        return snapshot_service.listar_snapshots(estudo_id)

    @app.get(
        "/api/estudos/{estudo_id}/snapshots/{snapshot_id}",
        response_model=SnapshotCalculo,
    )
    def obter_snapshot(estudo_id: str, snapshot_id: str) -> SnapshotCalculo:
        try:
            snap = snapshot_service.obter_snapshot(snapshot_id)
        except SnapshotNaoEncontradoError:
            raise HTTPException(status_code=404, detail="Snapshot não encontrado") from None
        if snap.estudo_id != estudo_id:
            raise HTTPException(status_code=404, detail="Snapshot não encontrado") from None
        return snap

    @app.get(
        "/api/estudos/{estudo_id}/snapshots/{snapshot_id}/comparativo",
        response_model=ComparativoComExibicao,
    )
    def comparativo_do_snapshot(estudo_id: str, snapshot_id: str) -> ComparativoComExibicao:
        try:
            snap = snapshot_service.obter_snapshot(snapshot_id)
        except SnapshotNaoEncontradoError:
            raise HTTPException(status_code=404, detail="Snapshot não encontrado") from None
        if snap.estudo_id != estudo_id:
            raise HTTPException(status_code=404, detail="Snapshot não encontrado") from None
        try:
            from newport_app.presentation.reajuste import anexar_exibicao_reajuste

            comparativo = snapshot_service.comparativo_do_snapshot(snapshot_id)
            rascunho = RascunhoEstudo.model_validate(snap.payload["rascunho"])
            return anexar_exibicao_reajuste(comparativo, rascunho)
        except SnapshotFormatoIncompativelError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    @app.post(
        "/api/estudos/{estudo_id}/snapshots/{snapshot_id}/aprovar",
        response_model=AprovarSnapshotResponse,
    )
    def aprovar_snapshot(
        estudo_id: str,
        snapshot_id: str,
        body: AprovarSnapshotRequest,
    ) -> AprovarSnapshotResponse:
        try:
            return snapshot_service.aprovar_snapshot(estudo_id, snapshot_id, body)
        except SnapshotNaoEncontradoError:
            raise HTTPException(status_code=404, detail="Snapshot não encontrado") from None
        except AprovacaoInvalidaError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    @app.get("/api/estudos/{estudo_id}/snapshot-aprovado")
    def snapshot_aprovado_atual(estudo_id: str):
        if repository.obter_rascunho(estudo_id) is None:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None
        return snapshot_service.status_governanca(estudo_id)

    @app.post(
        "/api/estudos/{estudo_id}/snapshots/{snapshot_id}/apresentacao/preview",
        response_model=PresentationViewModel,
    )
    def preview_apresentacao(
        estudo_id: str,
        snapshot_id: str,
        body: GerarApresentacaoRequest,
    ) -> PresentationViewModel:
        try:
            snap = snapshot_service.obter_snapshot(snapshot_id)
            if snap.estudo_id != estudo_id:
                raise HTTPException(status_code=404, detail="Snapshot não encontrado") from None
            if snap.estado != "aprovado":
                raise HTTPException(
                    status_code=422,
                    detail="Pré-visualização disponível somente para snapshot aprovado.",
                ) from None
            propostas = resolver_propostas_apresentacao_snapshot(
                snap.payload,
                body.propostas_selecionadas or None,
            )
            aprov = snap_repo.obter_aprovacao(snapshot_id)
            if aprov is None or aprov.invalidada_em is not None:
                raise HTTPException(
                    status_code=422,
                    detail="Aprovação inválida ou ausente.",
                ) from None
            modo_vm = "resumo" if body.modo == "completo" else body.modo
            return construir_view_model(
                snap,
                modo=modo_vm,
                propostas_selecionadas=propostas,
                ressalvas=body.ressalvas,
                titulo=body.titulo,
                exibir_todas_faixas=body.exibir_todas_faixas,
                beneficiarios_agregados=body.modo == "completo",
                aprovado_em=aprov.aprovado_em,
            )
        except SnapshotNaoEncontradoError:
            raise HTTPException(status_code=404, detail="Snapshot não encontrado") from None
        except SnapshotFormatoIncompativelError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    @app.post(
        "/api/estudos/{estudo_id}/snapshots/{snapshot_id}/apresentacao/gerar",
        response_model=GerarApresentacaoResponse,
    )
    def gerar_apresentacao_html(
        estudo_id: str,
        snapshot_id: str,
        body: GerarApresentacaoRequest,
    ) -> GerarApresentacaoResponse:
        try:
            return apresentacao.gerar_html(estudo_id, snapshot_id, body)
        except AprovacaoInvalidaError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except SnapshotFormatoIncompativelError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except PropostaNaoCalculavelError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Propostas não calculáveis: {', '.join(exc.opcoes_invalidas)}",
            ) from None

    @app.get(
        "/api/estudos/{estudo_id}/historico",
        response_model=HistoricoEstudoResponse,
    )
    def obter_historico_estudo(estudo_id: str) -> HistoricoEstudoResponse:
        try:
            return historico.obter_historico_estudo(estudo_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None

    @app.post("/api/estudos/{estudo_id}/historico/vincular")
    def vincular_estudo_cliente(estudo_id: str, body: VincularEstudoRequest):
        try:
            return historico.vincular_estudo(estudo_id, body).model_dump(mode="json")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    @app.post("/api/estudos/{estudo_id}/historico/vinculos/confirmar")
    def confirmar_vinculo_beneficiario(estudo_id: str, body: ConfirmarVinculoRequest):
        try:
            p = historico.confirmar_vinculo(body)
            return p.model_dump(mode="json")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    @app.post("/api/estudos/{estudo_id}/historico/vinculos/confirmar-lote")
    def confirmar_vinculo_lote(estudo_id: str, body: ConfirmarVinculoLoteRequest):
        n = historico.confirmar_vinculos_coerentes(body.participacao_ids)
        return {"confirmados": n}

    @app.get("/api/clientes", response_model=list[Cliente])
    def listar_clientes() -> list[Cliente]:
        return historico.listar_clientes()

    @app.post("/api/clientes", response_model=Cliente)
    def criar_cliente(body: dict):
        nome = body.get("nome", "").strip()
        if not nome:
            raise HTTPException(status_code=400, detail="Informe o nome do cliente.")
        return historico.criar_cliente(nome)

    @app.get("/api/clientes/{cliente_id}/ciclos", response_model=list[CicloRenovacao])
    def listar_ciclos_cliente(cliente_id: str) -> list[CicloRenovacao]:
        return historico.listar_ciclos(cliente_id)

    @app.get("/api/estudos/{estudo_id}/entregaveis/{entregavel_id}/html")
    def baixar_entregavel_html(estudo_id: str, entregavel_id: str):
        from fastapi.responses import FileResponse

        entregaveis = snap_repo.listar_entregaveis(estudo_id)
        ent = next((e for e in entregaveis if e.id == entregavel_id), None)
        if ent is None or ent.invalidado:
            raise HTTPException(status_code=404, detail="Entregável não encontrado") from None
        caminho = Path(ent.caminho_arquivo)
        if not caminho.is_file():
            raise HTTPException(status_code=404, detail="Arquivo não encontrado") from None
        return FileResponse(
            caminho,
            media_type="text/html",
            filename=caminho.name,
        )

    @app.post(
        "/api/estudos/{estudo_id}/plano-contratado",
        response_model=PlanoContratadoVersao,
    )
    def registrar_plano_contratado(
        estudo_id: str,
        body: RegistrarPlanoContratadoRequest,
    ) -> PlanoContratadoVersao:
        rascunho = repository.obter_rascunho(estudo_id)
        if rascunho is None:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None
        try:
            return historico.registrar_plano_contratado(rascunho, body)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    @app.get(
        "/api/estudos/{estudo_id}/planos-contratados",
        response_model=list[PlanoContratadoVersao],
    )
    def listar_planos_contratados(estudo_id: str) -> list[PlanoContratadoVersao]:
        if repository.obter_rascunho(estudo_id) is None:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None
        return historico.listar_planos_contratados(estudo_id)

    @app.get(
        "/api/estudos/{estudo_id}/historico/posicoes",
        response_model=list[PosicaoCadastralVersao],
    )
    def listar_posicoes_cadastrais(estudo_id: str) -> list[PosicaoCadastralVersao]:
        if repository.obter_rascunho(estudo_id) is None:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None
        return historico.listar_posicoes(estudo_id)

    if WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="static")

    return app


app = create_app()
