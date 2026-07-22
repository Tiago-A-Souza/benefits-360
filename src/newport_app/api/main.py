"""FastAPI — walking skeleton ETAPA 2.1."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from newport_app.models.responses import ComparativoResponse, EstudoResumo
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas, rascunho_demo_41_vidas
from newport_app.services.calculo import CalculoService, EstudoNaoEncontradoError

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / ".data" / "newport_app.db"
WEB_DIST = ROOT / "web" / "dist"


def _criar_repo() -> SQLiteStudyRepository:
    return SQLiteStudyRepository(DB_PATH)


def _seed_inicial(service: CalculoService) -> None:
    service.garantir_rascunho(rascunho_demo_12_vidas())
    service.garantir_rascunho(rascunho_demo_41_vidas())


def create_app(repo: SQLiteStudyRepository | None = None) -> FastAPI:
    repository = repo or _criar_repo()
    service = CalculoService(repository)
    _seed_inicial(service)

    app = FastAPI(title="Newport Estudos — Walking Skeleton", version="2.1.0")
    app.state.calculo_service = service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/estudos", response_model=list[str])
    def listar_estudos() -> list[str]:
        return repository.listar_ids()

    @app.get("/api/estudos/{estudo_id}", response_model=EstudoResumo)
    def obter_estudo(estudo_id: str) -> EstudoResumo:
        try:
            return service.obter_resumo(estudo_id)
        except EstudoNaoEncontradoError:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None

    @app.post("/api/estudos/{estudo_id}/calcular", response_model=ComparativoResponse)
    def calcular_estudo(estudo_id: str) -> ComparativoResponse:
        try:
            return service.calcular(estudo_id)
        except EstudoNaoEncontradoError:
            raise HTTPException(status_code=404, detail="Estudo não encontrado") from None

    if WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="static")

    return app


app = create_app()
