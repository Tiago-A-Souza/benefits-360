"""FastAPI — walking skeleton + compilador + importação SISCOR."""

from __future__ import annotations

from pathlib import Path

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
from newport_app.models.responses import ComparativoResponse, EstudoResumo, PendenciaItem, ResumoPlanoAtualResponse
from newport_app.models.responses_cotacao import (
    AplicarExtracaoResponse,
    ConfirmacaoExtracaoResponse,
    ListaExtracaoCotacaoResponse,
    ResultadoImportacaoCotacaoResponse,
)
from newport_app.models.cotacao_pdf import ExtracaoCotacaoCandidata
from newport_app.models.responses_siscor import (
    ConfirmacaoLoteResponse,
    ConferenciaSiscorResponse,
    ResultadoImportacaoSiscorResponse,
)
from newport_app.repository.extracao_cotacao import ExtracaoCotacaoRepository
from newport_app.repository.importacao_siscor import ImportacaoSiscorRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas, rascunho_demo_41_vidas
from newport_app.services.calculo import (
    CalculoService,
    EstudoNaoEncontradoError,
    RascunhoNaoCompilavelError,
)
from newport_app.services.extracao_cotacao import (
    CampoNaoEncontradoError,
    EstudoNaoEncontradoError as EstudoCotacaoNaoEncontradoError,
    AplicacaoExtracaoError,
    ExtracaoCotacaoService,
    ExtracaoNaoEncontradaError,
)
from newport_app.services.resumo_plano_atual import montar_resumo_plano_atual
from newport_app.services.pendencias import pendencias_compilacao
from newport_app.services.importacao_siscor import (
    ExclusaoSemMotivoError,
    ImportacaoRequerDecisaoError,
    ImportacaoSiscorService,
    LinhaIncompletaConfirmacaoError,
    LinhaNaoEncontradaError,
    ModoImportacaoInvalidoError,
)
from newport_app.siscor_mapper.apply import rascunho_vazio

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
    id: str
    titulo: str


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
    importacoes = import_repo or _criar_import_repo()
    extracoes_cotacao = cotacao_repo or ExtracaoCotacaoRepository(caminho_banco_cotacoes())
    uploads = uploads_dir or diretorio_uploads()
    uploads_cotacao = uploads_cotacao_dir or diretorio_uploads_cotacao()

    service = CalculoService(repository)
    siscor = ImportacaoSiscorService(
        repository,
        importacoes,
        uploads_dir=uploads,
    )
    cotacao = ExtracaoCotacaoService(
        repository,
        extracoes_cotacao,
        uploads_dir=uploads_cotacao,
    )
    if seed_demos:
        _seed_inicial(service)

    app = FastAPI(title="Newport Estudos", version="2.5.5")
    app.state.calculo_service = service
    app.state.siscor_service = siscor
    app.state.cotacao_service = cotacao
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
            "versao": "2.5.5",
            "limite_upload_bytes": LIMITE_UPLOAD_BYTES,
        }

    @app.get("/api/estudos", response_model=list[str])
    def listar_estudos() -> list[str]:
        return repository.listar_ids()

    @app.post("/api/estudos", response_model=EstudoResumo)
    def criar_estudo_vazio(body: NovoEstudoRequest) -> EstudoResumo:
        if repository.obter_rascunho(body.id) is not None:
            raise HTTPException(status_code=409, detail="Estudo já existe.")
        rascunho = rascunho_vazio(body.id, body.titulo)
        repository.salvar_rascunho(rascunho)
        return service.obter_resumo(body.id)

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

    @app.patch("/api/estudos/{estudo_id}/conferencia-siscor/linhas/{linha_id}")
    def atualizar_linha_siscor(
        estudo_id: str,
        linha_id: str,
        body: AtualizarLinhaSiscorRequest,
    ):
        try:
            linha = siscor.atualizar_linha(
                estudo_id,
                linha_id,
                segurado=body.segurado,
                nascimento=body.nascimento,
                parentesco_texto=body.parentesco_texto,
                plano=body.plano,
                operadora=body.operadora,
                status_texto=body.status_texto,
                valor_centavos=body.valor_centavos,
                incluida=body.incluida,
                excluida=body.excluida,
                motivo_exclusao=body.motivo_exclusao,
                confirmar=body.confirmar,
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
        except AplicacaoExtracaoError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "mensagem": str(exc),
                    "bloqueios": [b.model_dump(mode="json") for b in exc.bloqueios],
                },
            ) from None

    @app.get("/api/estudos/{estudo_id}/documentos-cotacao/{documento_id}/pdf")
    def baixar_pdf_cotacao(estudo_id: str, documento_id: str):
        from fastapi.responses import FileResponse

        caminho = cotacao.caminho_pdf(documento_id)
        if caminho is None:
            raise HTTPException(status_code=404, detail="PDF não encontrado") from None
        return FileResponse(
            caminho,
            media_type="application/pdf",
            filename="cotacao.pdf",
        )

    @app.post("/api/estudos/{estudo_id}/calcular", response_model=ComparativoResponse)
    def calcular_estudo(estudo_id: str) -> ComparativoResponse:
        try:
            return service.calcular(estudo_id)
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

    if WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="static")

    return app


app = create_app()
