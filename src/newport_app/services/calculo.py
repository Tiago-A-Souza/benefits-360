"""Orquestração: rascunho → motor → resposta amigável."""

from __future__ import annotations

from newport_app.adapters.motor_in import rascunho_para_estudo_input, rascunho_para_policy
from newport_app.adapters.motor_out import motor_result_para_comparativo, rascunho_para_resumo
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import ComparativoResponse, EstudoResumo
from newport_app.repository.base import StudyRepository
from newport_motor.engine import calcular


class EstudoNaoEncontradoError(Exception):
    pass


class CalculoService:
    def __init__(self, repository: StudyRepository) -> None:
        self._repo = repository

    def obter_resumo(self, estudo_id: str) -> EstudoResumo:
        rascunho = self._repo.obter_rascunho(estudo_id)
        if rascunho is None:
            raise EstudoNaoEncontradoError(estudo_id)
        return rascunho_para_resumo(rascunho)

    def calcular(self, estudo_id: str) -> ComparativoResponse:
        rascunho = self._repo.obter_rascunho(estudo_id)
        if rascunho is None:
            raise EstudoNaoEncontradoError(estudo_id)
        estudo_input = rascunho_para_estudo_input(rascunho)
        policy = rascunho_para_policy(rascunho)
        resultado = calcular(estudo_input, policy)
        return motor_result_para_comparativo(rascunho, resultado)

    def garantir_rascunho(self, rascunho: RascunhoEstudo) -> None:
        self._repo.salvar_rascunho(rascunho)
