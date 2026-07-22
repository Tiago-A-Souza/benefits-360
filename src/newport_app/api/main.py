"""FastAPI — walking skeleton + compilador + importação SISCOR."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from newport_app.api.validation_handlers import resposta_validacao_sanitizada
from newport_app.config.paths import diretorio_runtime_privado, garantir_diretorios
from newport_app.draft_compiler.structural import RascunhoEstruturalInvalidoError
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import ComparativoResponse, EstudoResumo
from newport_app.models.responses_siscor import (
    ConfirmacaoLoteResponse,
    ConferenciaSiscorResponse,
    ResultadoImportacaoSiscorResponse,
)
from newport_app.repository.importacao_siscor import ImportacaoSiscorRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas, rascunho_demo_41_vidas
from newport_app.services.calculo import (
    CalculoService,
    EstudoNaoEncontradoError,
    RascunhoNaoCompilavelError,
)
from newport_app.services.importacao_siscor import (
    ImportacaoRequerDecisaoError,
    ImportacaoSiscorService,
    LinhaNaoEncontradaError,
)
from newport_app.siscor_mapper.apply import rascunho_vazio

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / ".data" / "newport_app.db"
WEB_DIST = ROOT / "web" / "dist"


def _criar_repo() -> SQLiteStudyRepository:
    garantir_diretorios()
    return SQLiteStudyRepository(DB_PATH)


def _criar_import_repo(db_path: Path | None = None) -> ImportacaoSiscorRepository:
    path = db_path or (diretorio_runtime_privado() / "importacoes.db")
    return ImportacaoSiscorRepository(path)


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
    valor_centavos: int | None = None
    incluida: bool | None = None
    excluida: bool | None = None
    motivo_exclusao: str | None = None
    confirmar: bool = False


def create_app(
    repo: SQLiteStudyRepository | None = None,
    import_repo: ImportacaoSiscorRepository | None = None,
    uploads_dir: Path | None = None,
    *,
    seed_demos: bool = True,
) -> FastAPI:
    repository = repo or _criar_repo()
    if import_repo is not None:
        importacoes = import_repo
    elif repo is not None:
        importacoes = ImportacaoSiscorRepository(
            repository._db_path.parent / "importacoes.db"
        )
    else:
        importacoes = _criar_import_repo()

    service = CalculoService(repository)
    siscor = ImportacaoSiscorService(
        repository,
        importacoes,
        uploads_dir=uploads_dir,
    )
    if seed_demos:
        _seed_inicial(service)

    app = FastAPI(title="Newport Estudos", version="2.3.0")
    app.state.calculo_service = service
    app.state.siscor_service = siscor
    app.state.repository = repository

    @app.exception_handler(RequestValidationError)
    async def validacao_sanitizada(_request, exc: RequestValidationError):
        return resposta_validacao_sanitizada(exc)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
