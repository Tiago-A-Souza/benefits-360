"""Orquestração: rascunho → compilador → motor → resposta amigável."""

from __future__ import annotations

from collections.abc import Callable

from newport_app.adapters.motor_out import montar_comparativo, rascunho_para_resumo
from newport_app.diagnostico import registrar_evento
from newport_app.draft_compiler import compile
from newport_app.draft_compiler.structural import RascunhoEstruturalInvalidoError
from newport_app.models.compilation import ResultadoCompilacao
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import ComparativoResponse, EstudoResumo
from newport_app.policy.registry import PolicySetRegistry, default_registry
from newport_app.repository.base import StudyRepository
from newport_app.services.comparativo_confirmacao import (
    confirmar_comparativo_revisao,
    hash_comparativo_atual,
)
from newport_app.services.comparativo_ui import ordem_apresentacao_rascunho
from newport_motor.engine import calcular as calcular_motor


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
        on_rascunho_alterado: Callable[[str, str], None] | None = None,
    ) -> None:
        self._repo = repository
        self._policy_registry = policy_registry or default_registry
        self._on_rascunho_alterado = on_rascunho_alterado

    def obter_resumo(self, estudo_id: str) -> EstudoResumo:
        rascunho = self._repo.obter_rascunho(estudo_id)
        if rascunho is None:
            raise EstudoNaoEncontradoError(estudo_id)
        meta = next(
            ((i, u) for i, u in self._repo.listar_metadados() if i == estudo_id),
            (estudo_id, None),
        )
        return rascunho_para_resumo(rascunho, ultima_alteracao=meta[1])

    def listar_resumos(self) -> list[EstudoResumo]:
        resumos: list[EstudoResumo] = []
        for estudo_id, atualizado_em in self._repo.listar_metadados():
            rascunho = self._repo.obter_rascunho(estudo_id)
            if rascunho is None:
                continue
            resumos.append(
                rascunho_para_resumo(rascunho, ultima_alteracao=atualizado_em)
            )
        return resumos

    def calcular(self, estudo_id: str) -> ComparativoResponse:
        rascunho = self._repo.obter_rascunho(estudo_id)
        if rascunho is None:
            raise EstudoNaoEncontradoError(estudo_id)

        resultado_compilacao = compile(
            rascunho,
            policy_registry=self._policy_registry,
        )
        if not resultado_compilacao.compilavel:
            comparativo = montar_comparativo(
                rascunho,
                erros_compilacao=resultado_compilacao.erros,
            )
            registrar_evento(
                estudo_id=estudo_id,
                etapa="calculo",
                evento="calculo_compilacao_falhou",
                detalhe={
                    "erros": [e.codigo for e in resultado_compilacao.erros],
                },
            )
            return comparativo.model_copy(
                update={
                    "propostas_apresentacao": ordem_apresentacao_rascunho(rascunho),
                }
            )

        assert resultado_compilacao.compilado is not None
        motor_result = calcular_motor(
            resultado_compilacao.compilado.estudo_input,
            resultado_compilacao.compilado.effective_policy,
        )
        comparativo = montar_comparativo(rascunho, motor_result=motor_result)

        try:
            digest, _ = hash_comparativo_atual(
                rascunho, policy_registry=self._policy_registry
            )
        except RascunhoNaoCompilavelError:
            digest = None
        bloqueios = [p for p in comparativo.pendencias if p.tipo == "bloqueio"]
        if bloqueios:
            registrar_evento(
                estudo_id=estudo_id,
                etapa="calculo",
                evento="calculo_bloqueios",
                detalhe={
                    "bloqueios": [
                        {"codigo": p.codigo, "mensagem": p.titulo}
                        for p in bloqueios
                    ],
                },
            )
        if rascunho.confirmacao_comparativo:
            if rascunho.confirmacao_comparativo.hash_comparativo != digest:
                rascunho.confirmacao_comparativo = None
                self._repo.salvar_rascunho(rascunho)
        return comparativo.model_copy(
            update={
                "hash_comparativo": digest,
                "propostas_apresentacao": ordem_apresentacao_rascunho(rascunho),
            }
        )

    def confirmar_comparativo(
        self,
        estudo_id: str,
        hash_informado: str | None,
        opcao_ids: list[str],
    ):
        rascunho = self._repo.obter_rascunho(estudo_id)
        if rascunho is None:
            raise EstudoNaoEncontradoError(estudo_id)
        resp = confirmar_comparativo_revisao(
            rascunho,
            hash_informado,
            opcao_ids,
            policy_registry=self._policy_registry,
        )
        self.salvar_rascunho(rascunho)
        return resp

    def salvar_rascunho(self, rascunho: RascunhoEstudo) -> None:
        self._repo.salvar_rascunho(rascunho)
        if self._on_rascunho_alterado:
            self._on_rascunho_alterado(rascunho.id, "Alteração no rascunho")

    def garantir_rascunho(self, rascunho: RascunhoEstudo) -> None:
        self.salvar_rascunho(rascunho)
