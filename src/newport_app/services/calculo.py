"""Orquestração: rascunho → compilador → motor → resposta amigável."""

from __future__ import annotations

from newport_app.adapters.motor_out import motor_result_para_comparativo, rascunho_para_resumo
from newport_app.draft_compiler import compile
from newport_app.draft_compiler.structural import RascunhoEstruturalInvalidoError
from newport_app.models.compilation import ResultadoCompilacao
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import ComparativoResponse, EstudoResumo
from newport_app.policy.registry import PolicySetRegistry, default_registry
from newport_app.repository.base import StudyRepository
from newport_motor.engine import calcular


class EstudoNaoEncontradoError(Exception):
    pass


class RascunhoNaoCompilavelError(Exception):
    def __init__(self, resultado: ResultadoCompilacao) -> None:
        self.resultado = resultado
        super().__init__("rascunho não compilável")


class CalculoService:
    def __init__(
        self,
        repository: StudyRepository,
        policy_registry: PolicySetRegistry | None = None,
    ) -> None:
        self._repo = repository
        self._policy_registry = policy_registry or default_registry

    def obter_resumo(self, estudo_id: str) -> EstudoResumo:
        rascunho = self._repo.obter_rascunho(estudo_id)
        if rascunho is None:
            raise EstudoNaoEncontradoError(estudo_id)
        return rascunho_para_resumo(rascunho)

    def calcular(self, estudo_id: str) -> ComparativoResponse:
        rascunho = self._repo.obter_rascunho(estudo_id)
        if rascunho is None:
            raise EstudoNaoEncontradoError(estudo_id)

        resultado_compilacao = compile(rascunho, policy_registry=self._policy_registry)
        if not resultado_compilacao.compilavel:
            raise RascunhoNaoCompilavelError(resultado_compilacao)

        assert resultado_compilacao.compilado is not None
        compilado = resultado_compilacao.compilado
        motor_result = calcular(compilado.estudo_input, compilado.effective_policy)
        return motor_result_para_comparativo(
            rascunho,
            motor_result,
            self._policy_registry,
        )

    def salvar_rascunho(self, rascunho: RascunhoEstudo) -> None:
        self._repo.salvar_rascunho(rascunho)

    def garantir_rascunho(self, rascunho: RascunhoEstudo) -> None:
        self.salvar_rascunho(rascunho)
